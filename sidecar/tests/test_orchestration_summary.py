"""编排层会话摘要（5.2）：摘要注入、最近 N 轮历史、预算裁剪与后台更新。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.orchestration.graph import MAX_CONTEXT_CHARS, TriggerSource
from echoes_sidecar.session.summary import SummaryState, SummaryTurn
from tests.conftest import RecordingTransport, make_graph, make_session
from tests.fakes import BoomTTS


class CaptureLLM(LLMProvider):
    def __init__(self, pieces: list[str] | None = None) -> None:
        self.pieces = pieces or ["好的。"]
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
        for piece in self.pieces:
            yield piece


class FakeSummarizer:
    def __init__(
        self,
        state: SummaryState | None = None,
        *,
        should: bool = True,
        fail: bool = False,
    ) -> None:
        self.state = state
        self.should = should
        self.fail = fail
        self.load_calls = 0
        self.updates: list[dict[str, Any]] = []

    def load(self, session_id: str) -> SummaryState | None:
        _ = session_id
        self.load_calls += 1
        return self.state

    def should_update(
        self, state: SummaryState | None, *, turn_seq: int, now: float
    ) -> bool:
        _ = (state, turn_seq, now)
        return self.should

    async def update(
        self,
        session_id: str,
        turns: list[SummaryTurn],
        *,
        turn_seq: int,
        now: float,
    ) -> SummaryState | None:
        self.updates.append(
            {
                "session_id": session_id,
                "turns": list(turns),
                "turn_seq": turn_seq,
                "now": now,
            }
        )
        if self.fail:
            raise RuntimeError("summary boom")
        self.state = SummaryState("滚动摘要", turn_seq, now)
        return self.state


async def test_summary_is_injected_into_system_prompt() -> None:
    llm = CaptureLLM()
    summarizer = FakeSummarizer(SummaryState("用户喜欢猫", 1, 1.0), should=False)
    graph = make_graph(llm=llm, summarizer=summarizer)  # type: ignore[arg-type]

    await graph.run_turn(make_session(), TriggerSource.USER_INPUT, {"text": "你好"})

    system = llm.messages[0][0]["content"]
    assert "此前对话摘要" in system
    assert "用户喜欢猫" in system


async def test_history_is_used_on_next_turn() -> None:
    llm = CaptureLLM(["第一轮回复"])
    graph = make_graph(llm=llm)

    await graph.run_turn(make_session(), TriggerSource.USER_INPUT, {"text": "第一句"})
    await graph.run_turn(make_session(), TriggerSource.USER_INPUT, {"text": "第二句"})

    second = llm.messages[1]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert second[1]["content"] == "第一句"
    assert second[2]["content"] == "第一轮回复"
    assert second[3]["content"] == "第二句"


async def test_summary_update_runs_after_turn_and_feeds_next_turn() -> None:
    llm = CaptureLLM()
    summarizer = FakeSummarizer()
    graph = make_graph(llm=llm, summarizer=summarizer)  # type: ignore[arg-type]
    session = make_session()

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "我养了猫"})
    await graph.wait_summary_idle()

    assert len(summarizer.updates) == 1
    assert summarizer.updates[0]["turn_seq"] == 1
    assert summarizer.updates[0]["turns"] == [
        SummaryTurn(1, "我养了猫", "好的。")
    ]

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "它叫什么"})
    assert "滚动摘要" in llm.messages[1][0]["content"]


async def test_summary_failure_does_not_affect_turn() -> None:
    transport = RecordingTransport()
    summarizer = FakeSummarizer(fail=True)
    graph = make_graph(transport, summarizer=summarizer)  # type: ignore[arg-type]

    outcome = await graph.run_turn(
        make_session(), TriggerSource.USER_INPUT, {"text": "你好"}
    )
    await graph.wait_summary_idle()

    assert outcome.status == "SUCCESS"
    assert transport.only_turn_complete()["status"] == "SUCCESS"
    assert transport.of_type("error") == []


async def test_failed_turn_does_not_append_history() -> None:
    graph = make_graph(tts=BoomTTS())

    await graph.run_turn(make_session(), TriggerSource.USER_INPUT, {"text": "失败输入"})

    assert graph._history == {}  # noqa: SLF001  test-only 观察点


async def test_budget_drops_oldest_history_pair_and_keeps_current_input() -> None:
    graph = make_graph()
    session = make_session()
    graph._history[session.session_id] = [  # noqa: SLF001  test-only 预置历史
        SummaryTurn(1, "旧" * (MAX_CONTEXT_CHARS // 2), "回" * (MAX_CONTEXT_CHARS // 2)),
        SummaryTurn(2, "新" * 50, "复" * 50),
    ]

    messages = await graph._compose_messages(session, "本" * 100)  # noqa: SLF001

    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "本" * 100}
    assert all("旧" * 10 not in m["content"] for m in messages)
    assert any("新" * 10 in m["content"] for m in messages)
