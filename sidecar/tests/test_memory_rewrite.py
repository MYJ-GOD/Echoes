"""R3a Query Rewrite（3.2）：条件触发、失败/超时原样返回。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.memory.rewrite import QueryRewriter, needs_rewrite
from echoes_sidecar.session.summary import SummaryTurn


class FakeLLM(LLMProvider):
    def __init__(
        self, reply: str = "改写后的查询", *, delay: float = 0.0, name: str = "fake"
    ) -> None:
        self.reply = reply
        self.delay = delay
        self._name = name
        self.calls: list[list[dict[str, str]]] = []

    @property
    def name(self) -> str:
        return self._name

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
        _ = (stream, max_tokens, temperature)
        self.calls.append(messages)
        if self.delay:
            await asyncio.sleep(self.delay)
        yield self.reply


RECENT = [SummaryTurn(turn=3, user="我在读《小王子》", assistant="那本书不错")]


def test_gate_matches_pronouns_and_followups() -> None:
    assert needs_rewrite("它怎么样")
    assert needs_rewrite("上次说的那本书叫什么")
    assert needs_rewrite("后来呢")
    assert not needs_rewrite("今天天气不错")
    assert not needs_rewrite("")


async def test_rewrites_only_when_gate_matches() -> None:
    llm = FakeLLM("你上次说的《小王子》怎么样")
    rewriter = QueryRewriter(llm)  # type: ignore[arg-type]

    assert await rewriter.rewrite("它怎么样", RECENT) == "你上次说的《小王子》怎么样"
    assert len(llm.calls) == 1
    prompt = llm.calls[0][1]["content"]
    assert "《小王子》" in prompt and "它怎么样" in prompt

    assert await rewriter.rewrite("今天天气不错", RECENT) == "今天天气不错"
    assert len(llm.calls) == 1, "未命中门控不应发请求"


async def test_empty_or_overlong_reply_falls_back() -> None:
    for reply in ("", "   ", "长" * 500):
        llm = FakeLLM(reply)
        rewriter = QueryRewriter(llm)  # type: ignore[arg-type]
        assert await rewriter.rewrite("它呢", RECENT) == "它呢"


async def test_timeout_falls_back_to_original() -> None:
    llm = FakeLLM("慢", delay=0.2)
    rewriter = QueryRewriter(llm, timeout=0.01)  # type: ignore[arg-type]
    assert await rewriter.rewrite("它怎么样", RECENT) == "它怎么样"


async def test_mock_llm_never_rewrites() -> None:
    llm = FakeLLM("mock 台词", name="mock")
    rewriter = QueryRewriter(llm)  # type: ignore[arg-type]
    assert await rewriter.rewrite("它怎么样", RECENT) == "它怎么样"
    assert llm.calls == []


async def test_force_bypasses_the_gate() -> None:
    """memory_recall 意图即使没有指代词也改写。"""
    llm = FakeLLM("独立检索查询")
    rewriter = QueryRewriter(llm)  # type: ignore[arg-type]

    assert await rewriter.rewrite("继续讲讲吧", RECENT) == "继续讲讲吧"
    assert llm.calls == []

    assert await rewriter.rewrite("继续讲讲吧", RECENT, force=True) == "独立检索查询"
    assert len(llm.calls) == 1
