"""OpenAI 兼容 TTS（R2a 2.3）：`/v1/audio/speech`，逐句合成、逐句产出。

口径：
- **PCM 直取 + 格式兜底**：优先请求 `response_format="pcm"`（24kHz / 16bit /
  mono / LE），与 `AudioChunk` 口径一致，免解码。端点不支持 PCM 时（400 明确提到
  format/pcm）改用 `mp3`，由 `audio/decode.py` 解码 + 重采样回 PCM16（2.14）。
  这只换编码、不换 provider/模型/隐私——不是「静默降级」。
- **分句归引擎**（4.5）：`split_sentences` 切句后逐句请求；首句短上限沿用
  CosyVoice2 的 20 字（首包优先，ADR-012）。
- **key 在请求时才读**（注入 `key_provider`）：设置页刚保存的 key 下一轮生效。
- **音色**：`builtin:default` → 引擎默认音色；`openai:<name>` → 透传 provider
  音色名；`clone:*` 直接报错——云端没有克隆音色，静默换成默认音色等于骗用户。
- **克隆**：不支持（`clone()` 抛 CloneError）；克隆仍归本地 CosyVoice2（ADR-009）。
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from echoes_sidecar.audio.chunker import split_sentences
from echoes_sidecar.audio.decode import decode_to_pcm16
from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import CloneError, EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.tts.base import TTSEngine

KeyProvider = Callable[[], str | None]

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "tts-1"
DEFAULT_VOICE = "alloy"
BUILTIN_VOICE_ID = "builtin:default"
PROVIDER_VOICE_PREFIX = "openai:"
CLONE_PREFIX = "clone:"

SAMPLE_RATE = 24_000
# 100ms @24k mono PCM16：壳侧缓冲按帧丢弃，10 帧/秒足够平滑又不过碎
_CHUNK_BYTES = SAMPLE_RATE // 10 * 2
# 与 CosyVoice2 同口径：首句 20 字以内先出声（ADR-012 首包优先）
_FIRST_SEGMENT_MAX_CHARS = 20


class OpenAITtsEngine(TTSEngine):
    """`/audio/speech` 流式合成（逐句非流式请求，句子间连续产出）。"""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str | None = None,
        key_provider: KeyProvider | None = None,
        voice: str = DEFAULT_VOICE,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._key_provider = key_provider
        self._voice = voice.strip() or DEFAULT_VOICE
        self._client = httpx.AsyncClient(
            base_url=base_url.strip().rstrip("/"),
            transport=transport,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )

    @property
    def name(self) -> str:
        return "openai"

    async def warmup(self) -> None:
        """云端引擎没有权重可预热；保留方法让分级就绪逻辑统一。"""

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        sentences = split_sentences(text, first_max_chars=_FIRST_SEGMENT_MAX_CHARS)
        if not sentences:
            yield AudioChunk(data=b"", seq=0, is_final=True)
            return
        key = self._key()
        if not key:
            raise EchoesError(
                ErrorCode.TTS_ENGINE_ERROR,
                "尚未配置云端 TTS 的 API key（设置 → 引擎 → 语音合成）",
            )
        voice = self._voice_for(voice_id)
        seq = 0
        for index, sentence in enumerate(sentences):
            last = index == len(sentences) - 1
            pcm = await self._speech(sentence, voice, key)
            if not pcm:
                if last:
                    yield AudioChunk(data=b"", seq=seq, is_final=True)
                continue
            for offset in range(0, len(pcm), _CHUNK_BYTES):
                piece = pcm[offset : offset + _CHUNK_BYTES]
                final = last and offset + _CHUNK_BYTES >= len(pcm)
                yield AudioChunk(data=piece, seq=seq, is_final=final)
                seq += 1

    async def clone(self, sample: AudioInputStream) -> str:
        _ = sample
        raise CloneError(
            ErrorCode.TTS_ENGINE_ERROR,
            "当前 TTS 引擎不支持克隆（云端只提供预置音色）；请切回本地 CosyVoice2",
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------ 内部 ------------------------------

    def _key(self) -> str | None:
        if self._api_key:
            return self._api_key
        if self._key_provider is None:
            return None
        return self._key_provider() or None

    def _voice_for(self, voice_id: str) -> str:
        text = (voice_id or "").strip()
        if not text or text == BUILTIN_VOICE_ID:
            return self._voice
        if text.startswith(CLONE_PREFIX):
            raise EchoesError(
                ErrorCode.TTS_ENGINE_ERROR,
                "云端 TTS 不支持克隆音色：请切回本地 CosyVoice2，或改用内置音色",
            )
        if text.startswith(PROVIDER_VOICE_PREFIX):
            return text[len(PROVIDER_VOICE_PREFIX) :] or self._voice
        return text

    async def _speech(self, sentence: str, voice: str, key: str) -> bytes:
        """一句话 → PCM16 24k（先要 PCM；端点不支持时退 mp3/opus 并本地解码）。"""
        payload = {"model": self.model, "input": sentence, "voice": voice}
        resp = await self._post({**payload, "response_format": "pcm"}, key)
        if resp.status_code == 400 and _format_unsupported(resp.text):
            print(
                "[sidecar] 该端点不支持 response_format=pcm，改用 mp3 并在本地解码"
                "（2.14；不改变 provider/模型/隐私）",
                file=sys.stderr,
            )
            resp = await self._post({**payload, "response_format": "mp3"}, key)
            _raise_for_status(resp)
            return decode_to_pcm16(resp.content, sample_rate=SAMPLE_RATE)
        _raise_for_status(resp)
        return resp.content

    async def _post(self, body: dict[str, Any], key: str) -> httpx.Response:
        try:
            return await self._client.post(
                "/audio/speech",
                json=body,
                headers={"Authorization": f"Bearer {key}"},
            )
        except httpx.HTTPError as exc:
            raise EchoesError(
                ErrorCode.TTS_ENGINE_ERROR, f"云端 TTS 请求失败：{exc}"
            ) from exc


def _format_unsupported(detail: str) -> bool:
    text = detail.lower()
    return "response_format" in text or "pcm" in text or "format is not supported" in text


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    detail = resp.text[:200]
    if resp.status_code == 401:
        raise EchoesError(
            ErrorCode.TTS_ENGINE_ERROR,
            "云端 TTS 鉴权失败（401）：检查 API key 是否正确/过期",
        )
    if resp.status_code == 429:
        raise EchoesError(
            ErrorCode.TTS_ENGINE_ERROR, "云端 TTS 限流（429）：稍后再试"
        )
    raise EchoesError(
        ErrorCode.TTS_ENGINE_ERROR,
        f"云端 TTS 返回 HTTP {resp.status_code}：{detail}",
    )


__all__ = [
    "BUILTIN_VOICE_ID",
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_VOICE",
    "OpenAITtsEngine",
]
