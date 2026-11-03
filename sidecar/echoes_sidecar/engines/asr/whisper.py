"""WhisperASREngine（4.5 契约实现；faster-whisper 搬运，阶段 0 第二周-4）。

形态决策（tier_matrix 回填点）：
- PTT 整段：壳侧按住说话 → WS 分帧推送 → 松开（IS_FINAL）= 流结束 →
  本引擎整段转写（asyncio.to_thread，3.2 事件循环内禁长阻塞）。
  流式 partial（VAD 逐片出字）为后续增强，非阶段 0 范围。
- 默认 CPU + int8：8GB 显存档 qwen3:8b 已占 5-6GB（ADR-001 二轮判定），
  ASR 不入显存竞争；device/compute_type 留构造参数，按实测驱动 tier 决策。
- 权重：faster-whisper 模型经 HF cache 运行时下载（7.1 边界内；禁入安装器 ADR-011）。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.engines.asr.base import ASREngine


class WhisperASREngine(ASREngine):
    """faster-whisper 整段转写引擎（lazy 加载； PCM16 16k mono 输入口径 = 3.4 WS 帧）。"""

    def __init__(
        self,
        model_size: str = "small",
        *,
        model_path: str | None = None,
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "zh",
    ) -> None:
        self._model_size = model_size
        self._model_path = model_path
        self._device = device
        self._compute_type = compute_type
        self._language = language
        self._model: Any | None = None

    @property
    def current(self) -> tuple[str, str]:
        """(provider, model)：hello 里回报 active_*（R2a 2.5）。"""
        return "whisper", self._model_size

    async def warmup(self) -> None:
        """组合根装配期预热（重模型加载在线程里，不阻塞 booting 其余装配）。"""
        if self._model is None:
            await asyncio.to_thread(self._load_model)

    def preload(self) -> None:
        """主线程预载（同 CosyVoice2TtsEngine.preload：Windows loader-lock 死锁规避，R20）。

        只 import faster-whisper/ctranslate2 全链与 numpy（OpenBLAS 初始化留
        主线程）；模型权重仍归 warmup 分级就绪（3.4 v1.4），幂等。
        """
        import numpy  # noqa: F401  主线程完成 OpenBLAS 初始化
        from faster_whisper import WhisperModel  # noqa: F401  ctranslate2 全链

    def _load_model(self) -> None:
        import os

        # 7.3 运行时下载路径（国内分发 fallback；不覆盖用户显式配置）：
        # HF_ENDPOINT 默认镜像；仅在用户无任何显式代理配置时强制直连
        # （实测：注册表残留假代理 127.0.0.1:7890 无监听时，出网请求会被打挂）。
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        if not (
            os.environ.get("HTTP_PROXY")
            or os.environ.get("HTTPS_PROXY")
            or os.environ.get("NO_PROXY")
        ):
            os.environ.setdefault("NO_PROXY", "*")
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            model_size_or_path=self._model_path or self._model_size,
            device=self._device,
            compute_type=self._compute_type,
        )

    def _transcribe_sync(
        self, pcm: bytes
    ) -> list[tuple[str, int, int]]:
        """整段 PCM16 LE → float32 归一 → 逐段转写（线程池内同步执行）。"""
        import numpy as np

        assert self._model is not None, "warmup()/transcribe() 应先完成模型加载"
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        segments, _info = self._model.transcribe(audio, language=self._language)
        return [
            (seg.text.strip(), int(seg.start * 1000), int(seg.end * 1000))
            for seg in segments
        ]

    async def transcribe(self, audio: AudioInputStream) -> AsyncIterator[dict[str, Any]]:
        """消费输入流到流尾（PTT 整段形态）→ 转写 → 逐段产出 final 帧（4.5）。

        模型须先经 warmup()（组合根装配期显式预热）；未加载即调用在
        _transcribe_sync 里 assert 爆出（引擎错误不静默）。
        """
        parts: list[bytes] = []
        async for chunk in audio:
            parts.append(chunk.data)
        pcm = b"".join(parts)
        if not pcm:
            return
        for text, start_ms, end_ms in await asyncio.to_thread(self._transcribe_sync, pcm):
            if text:
                yield {
                    "text": text,
                    "is_final": True,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                }


__all__ = ["WhisperASREngine"]
