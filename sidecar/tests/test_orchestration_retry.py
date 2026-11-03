"""R4 4.4/4.5：重说/编辑 = 新 turn 取代旧 turn（append-only）。"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path

from echoes_sidecar.db.repo import Storage
from echoes_sidecar.engines.llm.base import LLMProvider
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
        yield "新回复。"


def _setup(tmp_path: Path) -> tuple[Storage, Session]:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    now = time.time()
    persona = storage.personas.sync(
        persona_id="default", name="默认人设", system_prompt="s", now=now
    )
    row = storage.sessions.create(session_id="s1", persona_id=persona.id, now=now)
    session = Session(
        session_id=row.id,
        profile_id=row.profile_id,
        persona=persona,
        created_at=row.started_at,
    )
    return storage, session


async def test_successful_retry_supersedes_old_turn(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    graph = make_graph(llm=CaptureLLM(), storage=storage)

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "我在学吉他"})
    old = storage.turns.last_finished("s1")
    assert old is not None

    outcome = await graph.run_turn(
        session,
        TriggerSource.USER_INPUT,
        {"text": "我在学吉他"},
        supersede=old.turn_id,
    )

    assert outcome.status == "SUCCESS"
    new = storage.turns.last_finished("s1")
    assert new is not None and new.turn_id != old.turn_id
    assert storage.turns.get(old.turn_id).superseded_by == new.turn_id
    assert [row.turn_id for row in storage.turns.list_session("s1")] == [new.turn_id]


async def test_failed_retry_keeps_old_turn_visible(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    graph = make_graph(llm=CaptureLLM(), storage=storage)
    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "我在学吉他"})
    old = storage.turns.last_finished("s1")
    assert old is not None

    boom = make_graph(tts=BoomTTS(), storage=storage)
    outcome = await boom.run_turn(
        session,
        TriggerSource.USER_INPUT,
        {"text": "我在学吉他"},
        supersede=old.turn_id,
    )

    assert outcome.status == "FAILED"
    assert storage.turns.get(old.turn_id).superseded_by is None, "失败不得取代旧 turn"
    visible = [row.turn_id for row in storage.turns.list_session("s1")]
    assert old.turn_id in visible


async def test_edited_text_is_what_gets_persisted(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    graph = make_graph(llm=CaptureLLM(), storage=storage)
    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "我在学吉他"})
    old = storage.turns.last_finished("s1")
    assert old is not None

    await graph.run_turn(
        session,
        TriggerSource.USER_INPUT,
        {"text": "我在学钢琴"},
        supersede=old.turn_id,
    )

    new = storage.turns.last_finished("s1")
    assert new is not None
    assert new.user_text == "我在学钢琴"
    assert storage.turns.get(old.turn_id).user_text == "我在学吉他", "旧原文一字不差"
