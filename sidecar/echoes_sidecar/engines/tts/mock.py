"""mock TTS：契约测试与无模型开发基础设施（文档 §12 步骤 2）。"""
from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import uuid4

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.tts.base import TTSEngine


class MockTTSEngine(TTSEngine):
    """恒定合成一个 1 帧静音 chunk；clone 恒返回内置音色（骨架闭环用）。"""

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        yield AudioChunk(data=b"\x00\x00", seq=0, is_final=True)

    async def clone(self, sample: AudioInputStream) -> str:
        """克隆语义闭环（4.5 mocked）：返回**非保留 ID**（builtin:default 是 2.5
        none 保留 ID 且不落库，5.1）——否则「克隆成功」与「从未克隆」不可区分。
        voice:mock-<短尾> 仅骨架内可识别，不暗示资产文件存在。"""
        _ = sample
        return f"voice:mock-{uuid4().hex[:8]}"


__all__ = ["MockTTSEngine"]
