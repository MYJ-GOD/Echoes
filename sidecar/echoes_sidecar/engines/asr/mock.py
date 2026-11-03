"""mock ASR：契约测试与无模型开发基础设施（文档 §12 步骤 2 要求骨架内建 mock 引擎）。"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.engines.asr.base import ASREngine


class MockASREngine(ASREngine):
    """恒定产出一句 final 转写；不携带任何模型依赖（13.1-L2 的 orchestration 全流程底座）。"""

    @property
    def current(self) -> tuple[str, str]:
        """(provider, model)：hello 里回报 active_*（R2a 2.5）。"""
        return "mock", ""

    async def transcribe(self, audio: AudioInputStream) -> AsyncIterator[dict[str, Any]]:
        yield {"text": "（mock）今天有点累，陪我聊聊", "is_final": True, "start_ms": 0, "end_ms": 0}


__all__ = ["MockASREngine"]
