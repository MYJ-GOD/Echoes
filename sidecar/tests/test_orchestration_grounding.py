"""R4 4.3 编排接线：turn 成功后异步质检、失败/无证据不质检。"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from echoes_sidecar.db.repo import Storage
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.memory.grounding import GroundingResult
from echoes_sidecar.memory.recall import RecallItem, RecallResult
from echoes_sidecar.orchestration.graph import TriggerSource
from echoes_sidecar.session.session import Session
from tests.conftest import make_graph
from tests.fakes import BoomTTS


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
        yield "你养了狗吧。"


class FakeRecall:
    def __init__(self, result: RecallResult) -> None:
        self.result = result

    async def recall(self, **_: Any) -> RecallResult:
        return self.result


class FakeJudge:
    def __init__(self, result: GroundingResult, *, available: bool = True) -> None:
        self.result = result
        self.available = available
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    async def check(self, reply: str, evidence) -> GroundingResult:
        self.calls.append((reply, tuple(evidence)))
        return self.result


def _setup(tmp_path: Path) -> tuple[Storage, Session]:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    now = time.time()
    persona = storage.personas.sync(
        persona_id="default", name="默认人设", system_prompt="s", now=now
    )
    row = storage.sessions.create(session_id="s1", persona_id=persona.id, now=now)
    return storage, Session(
        session_id=row.id,
        profile_id=row.profile_id,
        persona=persona,
        created_at=row.started_at,
    )


def _recall(facts: tuple[RecallItem, ...]) -> FakeRecall:
    return FakeRecall(RecallResult(facts=facts))


async def test_successful_turn_persists_grounding(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    judge = FakeJudge(GroundingResult(False, 0.4, ("用户养了狗",)))
    graph = make_graph(
        llm=CaptureLLM(),
        storage=storage,
        recall=_recall((RecallItem("fact", "f1", "用户喜欢猫"),)),  # type: ignore[arg-type]
        grounding=judge,  # type: ignore[arg-type]
    )

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "我家狗怎么样"}
    )
    await graph.wait_memory_idle()

    assert outcome.status == "SUCCESS"
    assert judge.calls and judge.calls[0][1] == ("用户喜欢猫",)
    turn = storage.turns.last_finished("s1")
    assert turn is not None
    assert turn.grounding_verdict == "unfaithful"
    assert turn.grounding_score == 0.4
    assert "用户养了狗" in (turn.grounding_claims or "")
    assert turn.grounding_checked_at is not None


async def test_no_injected_facts_means_no_grounding(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    judge = FakeJudge(GroundingResult(True, 1.0))
    graph = make_graph(
        llm=CaptureLLM(),
        storage=storage,
        recall=_recall(()),  # type: ignore[arg-type]
        grounding=judge,  # type: ignore[arg-type]
    )

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "在吗"})
    await graph.wait_memory_idle()

    assert judge.calls == []
    turn = storage.turns.last_finished("s1")
    assert turn is not None and turn.grounding_verdict is None


async def test_failed_turn_is_not_grounded(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    judge = FakeJudge(GroundingResult(True, 1.0))
    graph = make_graph(
        tts=BoomTTS(),
        storage=storage,
        recall=_recall((RecallItem("fact", "f1", "用户喜欢猫"),)),  # type: ignore[arg-type]
        grounding=judge,  # type: ignore[arg-type]
    )

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "我家狗怎么样"}
    )
    await graph.wait_memory_idle()

    assert outcome.status == "FAILED"
    assert judge.calls == []
    turn = storage.turns.get(storage.turns.last_finished("s1").turn_id)
    assert turn is not None and turn.grounding_verdict is None
