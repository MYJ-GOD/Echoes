"""ASREngine 契约（文档 4.5 冻结）。

标注说明（契约保真）：文档中的 `async def transcribe(...) -> AsyncIterator[dict]`
按 async generator 实现；ABC 用 `def` 声明返回 AsyncIterator，语义不变（ledger R5）。
推理调用一律 asyncio.to_thread/线程池——事件循环内禁止长阻塞（3.2）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.audio.stream import AudioInputStream


class ASREngine(ABC):
    @abstractmethod
    def transcribe(self, audio: AudioInputStream) -> AsyncIterator[dict[str, Any]]:
        """产出 {"text": str, "is_final": bool, "start_ms": int, "end_ms": int}（4.5）。"""
