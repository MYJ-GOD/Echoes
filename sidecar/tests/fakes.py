"""编排层测试用的「坏引擎 / 慢引擎」（契约实现，行为刻意可控）。

集中放这里而不是各测试文件各写一份：三跳打断与 turn 收尾的用例都要能精确
控制"第几片之后卡住 / 抛什么错"，重复实现容易把断言写歪。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.tts.base import TTSEngine


class BoomLLM(LLMProvider):
    """恒抛 EchoesError 的 LLM（turn FAILED + error 事件，3.4.1）。"""

    def __init__(self, code: ErrorCode = ErrorCode.LLM_PROVIDER_UNAVAILABLE) -> None:
        self.code = code

    @property
    def name(self) -> str:
        return "boom"

    async def health(self) -> bool:
        return False

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        _ = (messages, stream, max_tokens, temperature)  # 参数面同 4.4 契约
        raise EchoesError(self.code, "boom")
        yield ""  # async generator 语法要求（不可达）


class SlowLLM(LLMProvider):
    """首片后长时间阻塞的 LLM（验证令牌能插队到 pending 取项之前）。"""

    def __init__(self, delay: float = 30.0, first: str = "第一片") -> None:
        self.delay = delay
        self.first = first

    @property
    def name(self) -> str:
        return "slow"

    async def health(self) -> bool:
        return True

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        import asyncio

        _ = (messages, stream, max_tokens, temperature)
        yield self.first
        await asyncio.sleep(self.delay)
        yield "不该产出"


class FixedLLM(LLMProvider):
    """按给定片段流式产出（断言 assistant_text 的全量递增语义）。"""

    def __init__(self, pieces: list[str]) -> None:
        self.pieces = pieces

    @property
    def name(self) -> str:
        return "fixed"

    async def health(self) -> bool:
        return True

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        _ = (messages, stream, max_tokens, temperature)
        for piece in self.pieces:
            yield piece


class BoomTTS(TTSEngine):
    """恒抛 EchoesError 的 TTS（turn FAILED，状态机照常回 ready）。"""

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        raise EchoesError(ErrorCode.TTS_ENGINE_ERROR, "boom")
        yield AudioChunk(data=b"", seq=0)  # async generator 语法要求（不可达）

    async def clone(self, sample: Any) -> str:  # noqa: ARG002  test-only stub
        raise NotImplementedError


class EndlessTTS(TTSEngine):
    """永不结束的 TTS（验证取消后立刻断流，而不是跑完再看标志）。"""

    def __init__(self) -> None:
        self.produced = 0

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        while True:
            yield AudioChunk(data=b"\x00\x00", seq=self.produced)
            self.produced += 1

    async def clone(self, sample: Any) -> str:  # noqa: ARG002  test-only stub
        raise NotImplementedError


class CountingTTS(TTSEngine):
    """记录收到的文本（断言分句在引擎侧、编排层只吃 chunk 流）。"""

    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self.texts: list[tuple[str, str]] = []
        self._chunks = chunks if chunks is not None else [b"\x01\x00", b"\x02\x00"]

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        self.texts.append((text, voice_id))
        total = len(self._chunks)
        for index, payload in enumerate(self._chunks):
            yield AudioChunk(data=payload, seq=index, is_final=index == total - 1)

    async def clone(self, sample: Any) -> str:  # noqa: ARG002  test-only stub
        raise NotImplementedError


__all__ = [
    "BoomLLM",
    "BoomTTS",
    "CountingTTS",
    "EndlessTTS",
    "FixedLLM",
    "SlowLLM",
]
