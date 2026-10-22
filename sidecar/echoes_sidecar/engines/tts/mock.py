"""mock TTS：契约测试与无模型开发基础设施（文档 §12 步骤 2）。"""
from __future__ import annotations

from collections.abc import AsyncIterator

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.tts.base import TTSEngine


class MockTTSEngine(TTSEngine):
    """恒定合成一个 1 帧静音 chunk；clone 恒返回内置音色（骨架闭环用）。"""

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        yield AudioChunk(data=b"\x00\x00", seq=0, is_final=True)

    async def clone(self, sample: AudioInputStream) -> str:
        _ = sample
        return "builtin:default"


__all__ = ["MockTTSEngine"]
