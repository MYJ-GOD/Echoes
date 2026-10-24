"""SessionSummarizer（5.2）：触发条件、合并 prompt、落库与失败边界。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from echoes_sidecar.core.errors import EchoesError
from echoes_sidecar.db.repo import SessionSummary
from echoes_sidecar.session.summary import (
    MAX_SUMMARY_CHARS,
    SessionSummarizer,
    SummaryState,
    SummaryTurn,
)


class FakeRepo:
    def __init__(self, row: SessionSummary | None = None) -> None:
        self.row = row
        self.saved: list[dict[str, Any]] = []

    def get_summary(self, session_id: str) -> SessionSummary | None:
        _ = session_id
        return self.row

    def save_summary(
        self, session_id: str, *, summary: str, up_to_turn: int, now: float
    ) -> SessionSummary:
        self.saved.append(
            {"session_id": session_id, "summary": summary, "up_to_turn": up_to_turn, "now": now}
        )
        self.row = SessionSummary(session_id, summary, up_to_turn, now)
        return self.row


class FakeLLM:
    def __init__(self, reply: str = "用户喜欢猫，下周去上海。", *, name: str = "scripted") -> None:
        self.reply = reply
        self._name = name
        self.calls: list[list[dict[str, str]]] = []

    @property
    def name(self) -> str:
        return self._name

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
        yield self.reply


def _summarizer(
    repo: FakeRepo, llm: FakeLLM, *, interval_turns: int = 10
) -> SessionSummarizer:
    return SessionSummarizer(
        llm, repo, interval_turns=interval_turns, interval_seconds=1800  # type: ignore[arg-type]
    )


def test_load_maps_row() -> None:
    row = SessionSummary("s1", "用户喜欢猫", 10, 2.0)
    state = _summarizer(FakeRepo(row), FakeLLM()).load("s1")
    assert state == SummaryState("用户喜欢猫", 10, 2.0)


def test_should_update_first_summary_at_interval() -> None:
    summarizer = _summarizer(FakeRepo(), FakeLLM())
    assert not summarizer.should_update(None, turn_seq=9, now=0.0)
    assert summarizer.should_update(None, turn_seq=10, now=0.0)


def test_should_update_by_turn_or_time() -> None:
    summarizer = _summarizer(FakeRepo(), FakeLLM(), interval_turns=10)
    state = SummaryState("旧摘要", up_to_turn=10, updated_at=100.0)

    assert summarizer.should_update(state, turn_seq=20, now=110.0)
    assert summarizer.should_update(state, turn_seq=11, now=100.0 + 1800)
    assert not summarizer.should_update(state, turn_seq=11, now=100.0 + 1799)


def test_should_not_update_without_new_turns() -> None:
    summarizer = _summarizer(FakeRepo(), FakeLLM())
    state = SummaryState("旧摘要", up_to_turn=10, updated_at=100.0)
    assert not summarizer.should_update(state, turn_seq=10, now=99999.0)


async def test_update_merges_previous_and_pending_turns() -> None:
    repo = FakeRepo(SessionSummary("s1", "旧摘要：用户喜欢猫", 10, 1.0))
    llm = FakeLLM("用户喜欢猫；下周去上海。")
    summarizer = _summarizer(repo, llm)
    turns = [
        SummaryTurn(9, "第九轮", "旧回复"),
        SummaryTurn(10, "第十轮", "旧回复"),
        SummaryTurn(11, "我下周去上海", "好的"),
        SummaryTurn(12, "我养了猫", "记住了"),
    ]

    state = await summarizer.update("s1", turns, turn_seq=12, now=2.0)

    assert state == SummaryState("用户喜欢猫；下周去上海。", 12, 2.0)
    assert repo.saved == [
        {"session_id": "s1", "summary": "用户喜欢猫；下周去上海。", "up_to_turn": 12, "now": 2.0}
    ]
    user_prompt = llm.calls[0][1]["content"]
    assert "旧摘要：用户喜欢猫" in user_prompt
    assert "第 11 轮" in user_prompt and "第 12 轮" in user_prompt
    assert "第 9 轮" not in user_prompt and "第 10 轮" not in user_prompt


async def test_update_without_pending_returns_none_and_skips_llm() -> None:
    repo = FakeRepo(SessionSummary("s1", "旧摘要", 12, 1.0))
    llm = FakeLLM()
    summarizer = _summarizer(repo, llm)

    state = await summarizer.update(
        "s1", [SummaryTurn(12, "重复轮", "回复")], turn_seq=12, now=2.0
    )

    assert state is None
    assert llm.calls == []
    assert repo.saved == []


async def test_privacy_mode_skips_cloud_provider() -> None:
    repo = FakeRepo()
    llm = FakeLLM(name="cloud:deepseek")
    summarizer = _summarizer(repo, llm)

    state = await summarizer.update(
        "s1", [SummaryTurn(1, "你好", "你好")], turn_seq=1, now=2.0
    )

    assert state is None
    assert llm.calls == []
    assert repo.saved == []


async def test_empty_summary_is_an_error() -> None:
    repo = FakeRepo()
    summarizer = _summarizer(repo, FakeLLM("   "))
    with pytest.raises(EchoesError):
        await summarizer.update(
            "s1", [SummaryTurn(1, "你好", "你好")], turn_seq=1, now=2.0
        )
    assert repo.saved == []


async def test_summary_is_truncated_to_max_chars() -> None:
    repo = FakeRepo()
    summarizer = _summarizer(repo, FakeLLM("字" * (MAX_SUMMARY_CHARS + 50)))
    state = await summarizer.update(
        "s1", [SummaryTurn(1, "你好", "你好")], turn_seq=1, now=2.0
    )
    assert state is not None
    assert len(state.text) == MAX_SUMMARY_CHARS
