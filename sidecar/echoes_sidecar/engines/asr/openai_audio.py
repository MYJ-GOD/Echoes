"""OpenAI 兼容 ASR（R2a 2.1）：`/v1/audio/transcriptions` 整段转写。

口径：
- PTT 是整段形态（3.4 WS 收满再转写），这里把 PCM16 16k mono 包成 WAV 上传，
  与 `whisper-1` / `gpt-4o-transcribe` 的入参一致；不假设端点支持裸 PCM。
- **不复用 `openai_compat` 的 chat 形状**：音频接口是 multipart + `text` 字段，
  只复用 HTTP/auth 口径（ADR/2.1 明确要求）。
- key 在请求时才读（`key_provider`），设置页保存后下一轮生效。
- 云端 ASR 意味着**原始录音出境**（隐私矩阵里门槛最高的一条）；是否允许由
  `AsrRouter` 按 privacy_mode 判定，本模块只负责把错误说清楚。
- 转写结果按 final 帧产出：整段一个 segment（start/end 归 0，时长由壳侧掌握）。
"""

from __future__ import annotations

import io
import wave
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.engines.asr.base import ASREngine

KeyProvider = Callable[[], str | None]

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "whisper-1"
SAMPLE_RATE = 16_000


class OpenAIAudioASREngine(ASREngine):
    """OpenAI 兼容音频转写（整段）。"""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        key_provider: KeyProvider | None = None,
        language: str = "zh",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._key_provider = key_provider
        self._language = language
        self._client = httpx.AsyncClient(
            base_url=base_url.strip().rstrip("/"),
            transport=transport,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )

    @property
    def current(self) -> tuple[str, str]:
        """(provider, model)：hello 里回报 active_*（R2a 2.5）。"""
        return "openai", self.model

    async def warmup(self) -> None:
        """云端引擎没有权重可预热；保留方法让分级就绪逻辑统一。"""

    async def transcribe(self, audio: AudioInputStream) -> AsyncIterator[dict[str, Any]]:
        parts: list[bytes] = []
        async for chunk in audio:
            parts.append(chunk.data)
        pcm = b"".join(parts)
        if not pcm:
            return
        key = self._key()
        if not key:
            raise EchoesError(
                ErrorCode.ASR_ENGINE_ERROR,
                "尚未配置云端 ASR 的 API key（设置 → 引擎 → 语音识别）",
            )
        text = await self._transcribe_wav(_wav_bytes(pcm), key)
        if text:
            yield {"text": text, "is_final": True, "start_ms": 0, "end_ms": 0}

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------ 内部 ------------------------------

    def _key(self) -> str | None:
        if self._api_key:
            return self._api_key
        if self._key_provider is None:
            return None
        return self._key_provider() or None

    async def _transcribe_wav(self, wav: bytes, key: str) -> str:
        files = {"file": ("audio.wav", wav, "audio/wav")}
        data = {
            "model": self.model,
            "language": self._language,
            "response_format": "json",
        }
        try:
            resp = await self._client.post(
                "/audio/transcriptions",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {key}"},
            )
        except httpx.HTTPError as exc:
            raise EchoesError(
                ErrorCode.ASR_ENGINE_ERROR, f"云端 ASR 请求失败：{exc}"
            ) from exc
        if resp.status_code >= 400:
            detail = resp.text[:200]
            if resp.status_code == 401:
                raise EchoesError(
                    ErrorCode.ASR_ENGINE_ERROR,
                    "云端 ASR 鉴权失败（401）：检查 API key 是否正确/过期",
                )
            if resp.status_code == 429:
                raise EchoesError(
                    ErrorCode.ASR_ENGINE_ERROR, "云端 ASR 限流（429）：稍后再试"
                )
            raise EchoesError(
                ErrorCode.ASR_ENGINE_ERROR,
                f"云端 ASR 返回 HTTP {resp.status_code}：{detail}",
            )
        try:
            payload = resp.json()
        except ValueError:
            return resp.text.strip()
        text = payload.get("text") if isinstance(payload, dict) else None
        return text.strip() if isinstance(text, str) else ""


def _wav_bytes(pcm: bytes) -> bytes:
    """PCM16 mono 16k → WAV（转写接口要容器，不接裸 PCM）。"""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm)
    return buffer.getvalue()


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "OpenAIAudioASREngine",
    "SAMPLE_RATE",
]
