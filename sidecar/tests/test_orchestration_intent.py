"""R4 4.2 意图分流：不同意图的注入量与改写策略。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.memory.recall import RecallItem, RecallResult
from echoes_sidecar.orchestration.graph import TriggerSource
from tests.conftest import make_graph, make_session


class CaptureLLM(LLMProvider):
    def __init__(self) -> None:
        self.messages: list[list[dict[str, str]]] = []

    @property
    def name(self) -> str:
        return "capture"

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
        self.messages.append(messages)
        yield "嗯。"


class FakeRecall:
    def __init__(self, result: RecallResult) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def recall(self, **kwargs: Any) -> RecallResult:
        self.calls.append(kwargs)
        return self.result


class FakeRewriter:
    def __init__(self) -> None:
        self.calls: list[bool] = []

    async def rewrite(self, question: str, recent: Any, *, force: bool = False) -> str:
        _ = recent
        self.calls.append(force)
        return question


def _result() -> RecallResult:
    return RecallResult(
        facts=tuple(RecallItem("fact", f"f{i}", f"事实{i}") for i in range(12)),
        turns=tuple(
            RecallItem("turn", f"t{i}", f"原文{i}", title=f"第 {i} 轮")
            for i in range(12)
        ),
        summaries=tuple(
            RecallItem("summary", f"s{i}", f"摘要{i}", title=f"会话{i}")
            for i in range(5)
        ),
    )


async def _system_for(text: str, *, rewriter: FakeRewriter | None = None) -> str:
    llm = CaptureLLM()
    graph = make_graph(
        llm=llm,
        recall=FakeRecall(_result()),  # type: ignore[arg-type]
        rewriter=rewriter,  # type: ignore[arg-type]
    )
    await graph.run_turn(make_session(), TriggerSource.USER_INPUT, {"text": text})
    return llm.messages[0][0]["content"]


async def test_chat_uses_default_budget() -> None:
    system = await _system_for("在吗")
    assert system.count("- 事实") == 5
    assert system.count("- [第") == 3
    assert system.count("- [会话") == 2


async def test_memory_recall_widens_injection_and_forces_rewrite() -> None:
    rewriter = FakeRewriter()
    system = await _system_for("还记得上次说的那本书吗", rewriter=rewriter)
    assert system.count("- 事实") == 8
    assert system.count("- [第") == 10
    assert system.count("- [会话") == 3
    assert rewriter.calls == [True]


async def test_profile_query_is_facts_only() -> None:
    system = await _system_for("我是谁")
    assert system.count("- 事实") == 10
    assert "可能相关的历史原话" not in system
    assert "其他会话的相关摘要" not in system


async def test_emotional_support_injects_hint_and_limits_facts() -> None:
    system = await _system_for("今天好累")
    assert "用户此刻情绪不好" in system
    assert system.count("- 事实") == 3
    assert "可能相关的历史原话" not in system
    assert "其他会话的相关摘要" not in system


async def test_plain_chat_does_not_force_rewrite() -> None:
    rewriter = FakeRewriter()
    await _system_for("在吗", rewriter=rewriter)
    assert rewriter.calls == [False]
