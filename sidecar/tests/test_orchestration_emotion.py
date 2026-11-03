"""R4 4.7 情感链路接线：情绪进 prompt、标签落 turn.emotion。"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path

from echoes_sidecar.db.repo import Storage
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.orchestration.graph import TriggerSource
from echoes_sidecar.session.session import Session
from tests.conftest import RecordingTransport, make_graph


class InstructionTTS(MockTTSEngine):
    """记录每轮设置/复位的风格指令。"""

    def __init__(self) -> None:
        self.instructions: list[str | None] = []

    @property
    def supports_instruction(self) -> bool:
        return True

    def set_instruction(self, text: str | None) -> None:
        self.instructions.append(text)


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
        yield "我在。"


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


async def test_emotional_turn_injects_label_and_persists(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    llm = CaptureLLM()
    tts = InstructionTTS()
    graph = make_graph(llm=llm, tts=tts, storage=storage)

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "今天好累"})

    system = llm.messages[0][0]["content"]
    assert "用户此刻情绪：疲惫" in system
    turn = storage.turns.last_finished("s1")
    assert turn is not None and turn.emotion == "tired"
    # R2b 2b.6：情绪 → TTS 指令，合成结束复位（不泄漏到下一轮）
    assert tts.instructions[0] is not None
    assert "温柔" in (tts.instructions[0] or "")
    assert tts.instructions[-1] is None


async def test_neutral_turn_has_no_hint_and_null_emotion(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    llm = CaptureLLM()
    graph = make_graph(llm=llm, storage=storage)

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "今天天气不错"})

    assert "用户此刻情绪" not in llm.messages[0][0]["content"]
    turn = storage.turns.last_finished("s1")
    assert turn is not None and turn.emotion is None


async def test_non_emotional_intent_does_not_inject_label(tmp_path: Path) -> None:
    """「上次说的那本书」命中的是 memory_recall，不注入情绪提示（即使词表有弱命中）。"""
    storage, session = _setup(tmp_path)
    llm = CaptureLLM()
    graph = make_graph(llm=llm, storage=storage)

    await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "上次说的那本书叫什么"}
    )

    assert "用户此刻情绪" not in llm.messages[0][0]["content"]


async def test_three_history_write_failures_escalate_to_read_only(
    tmp_path: Path, monkeypatch
) -> None:
    """§2.7：连续 3 次原文写入失败后报只读，后续仍继续回复（不静默丢输入）。"""
    from echoes_sidecar.core.errors import EchoesError, ErrorCode

    storage, session = _setup(tmp_path)

    def boom(**_kwargs: object) -> object:
        raise EchoesError(ErrorCode.STORAGE_ERROR, "disk full")

    monkeypatch.setattr(storage.turns, "insert", boom)
    transport = RecordingTransport()
    graph = make_graph(transport=transport, storage=storage)

    for _ in range(3):
        await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "你好"})

    errors = [
        item for item in transport.of_type("error")
        if item["code"] == "HISTORY_WRITE_FAILED"
    ]
    assert len(errors) == 3
    assert "连续第 3 次" in errors[-1]["message"]
    assert "只读模式" in errors[-1]["message"]
    # 3.4：写失败也不阻断语音链路，每轮仍正常收尾
    assert [item["status"] for item in transport.of_type("turn_complete")] == [
        "SUCCESS",
        "SUCCESS",
        "SUCCESS",
    ]
