"""R1a 编排接入：原文落盘、seq 来自 DB、摘要补偿。"""
from __future__ import annotations

from pathlib import Path

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db.repo import Storage
from echoes_sidecar.orchestration.graph import TriggerSource
from echoes_sidecar.session.session import Session
from echoes_sidecar.session.summary import SummaryState
from tests.conftest import RecordingTransport, make_graph
from tests.test_orchestration_summary import FakeSummarizer


def _open(tmp_path: Path) -> Storage:
    return Storage.open(tmp_path / "db" / "echoes.db")


def _session(storage: Storage, session_id: str = "s1") -> Session:
    persona = storage.personas.sync(
        persona_id="default", name="默认人设", system_prompt="s", now=1.0
    )
    storage.sessions.create(session_id=session_id, persona_id=persona.id, now=1.0)
    return Session(session_id=session_id, profile_id="default", persona=persona)


async def test_turn_is_persisted_and_seq_survives_restart(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        session = _session(storage)
        graph = make_graph(storage=storage)
        await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "第一句"})

        rows = storage.turns.recent("s1", limit=10)
        assert [(row.seq, row.user_text, row.status) for row in rows] == [
            (1, "第一句", "complete")
        ]
        assert rows[0].assistant_text is not None
        assert rows[0].assistant_text.strip()
        assert storage.sessions.get("s1").title == "第一句"  # type: ignore[union-attr]

        # 新图 = 进程重启；seq 必须从 DB 继续
        restarted = make_graph(storage=storage)
        await restarted.run_turn(session, TriggerSource.USER_INPUT, {"text": "第二句"})
        assert [row.seq for row in storage.turns.recent("s1", limit=10)] == [1, 2]
    finally:
        storage.close()


async def test_turn_complete_is_sent_after_db_finish(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        session = _session(storage)

        class CheckingTransport(RecordingTransport):
            def __init__(self) -> None:
                super().__init__()
                self.seen_statuses: list[str] = []

            async def send(self, msg: dict[str, object]) -> None:
                if msg.get("type") == "turn_complete":
                    rows = storage.turns.recent("s1", limit=10)
                    self.seen_statuses.extend(row.status for row in rows)
                await super().send(msg)

        transport = CheckingTransport()
        graph = make_graph(transport, storage=storage)
        await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "检查顺序"})

        assert transport.seen_statuses == ["complete"]
    finally:
        storage.close()


async def test_summary_reads_unsummarized_turns_from_db(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        session = _session(storage)
        for index in range(1, 51):
            turn = storage.turns.insert(
                session_id="s1", user_text=f"第{index}轮", now=float(index)
            )
            storage.turns.finish(
                turn.turn_id,
                assistant_text=f"答{index}",
                status="complete",
                now=float(index) + 0.5,
            )
        storage.sessions.save_summary(
            "s1", summary="旧摘要", up_to_turn=30, now=60.0
        )

        summarizer = FakeSummarizer(
            state=SummaryState("旧摘要", 30, 60.0), should=True
        )
        graph = make_graph(storage=storage, summarizer=summarizer)  # type: ignore[arg-type]
        await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "第51轮"})
        await graph.wait_summary_idle()

        assert len(summarizer.updates) == 1
        seqs = [turn.turn for turn in summarizer.updates[0]["turns"]]
        assert seqs == list(range(31, 52))  # 31..51，不能漏 31..39
    finally:
        storage.close()


async def test_history_write_failure_does_not_kill_turn(
    tmp_path: Path, monkeypatch
) -> None:
    storage = _open(tmp_path)
    try:
        session = _session(storage)
        transport = RecordingTransport()

        def boom(**_: object) -> None:
            raise EchoesError(ErrorCode.STORAGE_ERROR, "disk full")

        monkeypatch.setattr(storage.turns, "insert", boom)
        graph = make_graph(transport, storage=storage)
        outcome = await graph.run_turn(
            session, TriggerSource.USER_INPUT, {"text": "写不进去也要能说完"}
        )

        assert outcome.status == "SUCCESS"
        assert transport.only_turn_complete()["status"] == "SUCCESS"
        errors = transport.of_type("error")
        assert [error["code"] for error in errors] == ["HISTORY_WRITE_FAILED"]
        assert storage.turns.recent("s1", limit=10) == []
    finally:
        storage.close()
