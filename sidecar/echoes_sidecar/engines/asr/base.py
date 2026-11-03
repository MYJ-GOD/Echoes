"""ASREngine 契约（文档 4.5 冻结）。

标注说明（契约保真）：文档中的 `async def transcribe(...) -> AsyncIterator[dict]`
按 async generator 实现；ABC 用 `def` 声明返回 AsyncIterator，语义不变（ledger R5）。
推理调用一律 asyncio.to_thread/线程池——事件循环内禁止长阻塞（3.2）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from echoes_sidecar.audio.stream import AudioInputStream


@runtime_checkable
class AsrRuntimeConfigurable(Protocol):
    """可选能力（R2a 2.5）：PTT 转写前按设置切换 ASR provider。

    与 LLM/TTS 的运行时协议同构：编排层只认 Protocol，不认识 `AsrRouter`。
    """

    async def apply(
        self,
        *,
        provider: str | None,
        model: str | None,
        base_url: str | None = None,
        allow_cloud: bool = True,
    ) -> None: ...

    @property
    def current(self) -> tuple[str, str]: ...


class ASREngine(ABC):
    @abstractmethod
    def transcribe(self, audio: AudioInputStream) -> AsyncIterator[dict[str, Any]]:
        """产出 {"text": str, "is_final": bool, "start_ms": int, "end_ms": int}（4.5）。"""
