"""R1a 原文层：0003/0004 schema 与 TurnRepo 行为。"""
from __future__ import annotations

from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError
from echoes_sidecar.db.repo import Storage


def _open(tmp_path: Path) -> Storage:
    return Storage.open(tmp_path / "db" / "echoes.db")


def _session(storage: Storage) -> None:
    storage.personas.sync(
        persona_id="default", name="默认人设", system_prompt="s", now=1.0
    )
    storage.sessions.create(session_id="s1", persona_id="default", now=1.0)


def _columns(storage: Storage, table: str) -> dict[str, tuple[object, ...]]:
    rows = storage.conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]): tuple(row) for row in rows}


def test_0003_and_0004_create_turn_layer_and_voice_engine(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        tables = {
            str(row[0])
            for row in storage.conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
        }
        assert {"turn", "turn_fts", "turn_chunk", "turn_memory_ref"} <= tables

        turn_columns = _columns(storage, "turn")
        assert "rowid" in turn_columns
        assert turn_columns["rowid"][5] == 1  # primary key
        assert "turn_id" in turn_columns
        assert "fail_reason" in turn_columns
        assert "superseded_by" in turn_columns

        fact_columns = _columns(storage, "memory_fact")
        assert "source_turn_id" in fact_columns

        voice_columns = _columns(storage, "voice")
        assert "engine" in voice_columns

        summary_fks = storage.conn.execute(
            "PRAGMA foreign_key_list(session_summary)"
        ).fetchall()
        assert any(
            str(row["table"]) == "session" and str(row["on_delete"]).upper() == "CASCADE"
            for row in summary_fks
        )
    finally:
        storage.close()


def test_turn_insert_finish_and_sequence(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        _session(storage)
        first = storage.turns.insert(
            session_id="s1",
            user_text="我在学吉他",
            now=10.0,
            model="mock",
            persona_id="default",
        )
        assert first.seq == 1
        assert first.status == "pending"
        assert first.assistant_text is None
        assert "吉他" in first.tokens

        storage.turns.finish(
            first.turn_id,
            assistant_text="很好，继续练。",
            status="complete",
            now=11.0,
            latency_ms=1000,
        )
        finished = storage.turns.get(first.turn_id)
        assert finished is not None
        assert finished.status == "complete"
        assert finished.assistant_text == "很好，继续练。"
        assert finished.ended_at == 11.0
        assert finished.latency_ms == 1000
        assert "吉他" in finished.tokens
        assert "继续" in finished.tokens

        second = storage.turns.insert(session_id="s1", user_text="第二句", now=12.0)
        assert second.seq == 2
    finally:
        storage.close()


def test_turn_search_and_recent_order(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        _session(storage)
        ids = []
        for index in range(1, 16):
            turn = storage.turns.insert(
                session_id="s1", user_text=f"第{index}轮 我在学吉他", now=float(index)
            )
            storage.turns.finish(
                turn.turn_id,
                assistant_text=f"回复{index}",
                status="complete",
                now=float(index) + 0.5,
            )
            ids.append(turn.turn_id)

        assert storage.turns.search("吉他")[0].turn_id == ids[-1]
        assert storage.turns.search("不存在的词") == []
        recent = storage.turns.recent("s1", limit=12)
        assert [row.seq for row in recent] == list(range(4, 16))
    finally:
        storage.close()


def test_turn_cleanup_pending_marks_failed(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        _session(storage)
        first = storage.turns.insert(session_id="s1", user_text="崩溃前", now=1.0)
        second = storage.turns.insert(session_id="s1", user_text="也崩溃", now=2.0)
        storage.turns.finish(
            second.turn_id, assistant_text="完成", status="complete", now=3.0
        )

        assert storage.turns.cleanup_pending(now=4.0) == 1
        cleaned = storage.turns.get(first.turn_id)
        assert cleaned is not None
        assert cleaned.status == "failed"
        assert cleaned.fail_reason == "crash_cleanup"
        assert cleaned.ended_at == 4.0
        assert storage.turns.get(second.turn_id).status == "complete"  # type: ignore[union-attr]
    finally:
        storage.close()


def test_unsummarized_returns_gap_after_seq(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        _session(storage)
        for index in range(1, 6):
            turn = storage.turns.insert(
                session_id="s1", user_text=f"第{index}轮", now=float(index)
            )
            storage.turns.finish(
                turn.turn_id, assistant_text=f"答{index}", status="complete", now=float(index) + 0.5
            )
        rows = storage.turns.unsummarized("s1", after_seq=2, limit=10)
        assert [row.seq for row in rows] == [3, 4, 5]
    finally:
        storage.close()


def test_cloud_voice_sample_path_is_none_and_engine_is_kept(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        storage.conn.execute(
            "INSERT INTO voice"
            " (id, display_name, sample_path, model_path, status, quality_score,"
            "  created_at, kind, provider, engine)"
            " VALUES ('cloud:v1', '云端音色', NULL, NULL, 'ready', NULL, 1.0,"
            "         'cloud', 'openai', 'openai')"
        )
        storage.conn.commit()
        row = storage.voices.get("cloud:v1")
        assert row is not None
        assert row.sample_path is None
        assert row.engine == "openai"
    finally:
        storage.close()


def test_delete_session_cascades_summary_and_turns(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        _session(storage)
        turn = storage.turns.insert(session_id="s1", user_text="要删的", now=1.0)
        storage.turns.finish(
            turn.turn_id, assistant_text="回复", status="complete", now=2.0
        )
        storage.sessions.save_summary(
            "s1", summary="摘要", up_to_turn=1, now=3.0
        )
        storage.conn.execute("DELETE FROM session WHERE id = 's1'")
        storage.conn.commit()
        assert storage.conn.execute("SELECT COUNT(*) FROM turn").fetchone()[0] == 0
        assert storage.conn.execute("SELECT COUNT(*) FROM session_summary").fetchone()[0] == 0
    finally:
        storage.close()


def test_last_finished_and_supersede_hide_old_turn(tmp_path: Path) -> None:
    """R4 4.4/4.5：旧 turn 指向新 turn 后，列表/搜索/最近都只剩新 turn。"""
    storage = _open(tmp_path)
    try:
        _session(storage)
        old = storage.turns.insert(session_id="s1", user_text="我在学吉他", now=1.0)
        storage.turns.finish(
            old.turn_id, assistant_text="旧回复", status="complete", now=2.0
        )
        assert storage.turns.last_finished("s1").turn_id == old.turn_id

        new = storage.turns.insert(session_id="s1", user_text="我在学吉他", now=3.0)
        storage.turns.finish(
            new.turn_id, assistant_text="新回复", status="complete", now=4.0
        )
        storage.turns.supersede(old.turn_id, new.turn_id)

        assert storage.turns.last_finished("s1").turn_id == new.turn_id
        assert [row.turn_id for row in storage.turns.list_session("s1")] == [new.turn_id]
        assert [row.turn_id for row in storage.turns.search("吉他")] == [new.turn_id]
        assert [row.turn_id for row in storage.turns.recent("s1")] == [new.turn_id]
        assert storage.turns.get(old.turn_id).superseded_by == new.turn_id
    finally:
        storage.close()


def test_supersede_rejects_already_superseded(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        _session(storage)
        first = storage.turns.insert(session_id="s1", user_text="a", now=1.0)
        storage.turns.finish(
            first.turn_id, assistant_text="b", status="complete", now=2.0
        )
        second = storage.turns.insert(session_id="s1", user_text="c", now=3.0)
        storage.turns.finish(
            second.turn_id, assistant_text="d", status="complete", now=4.0
        )
        storage.turns.supersede(first.turn_id, second.turn_id)
        try:
            storage.turns.supersede(first.turn_id, second.turn_id)
        except Exception as exc:  # noqa: BLE001  EchoesError
            assert "已被取代" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("重复取代应报错")
    finally:
        storage.close()


def test_set_grounding_persists_and_validates(tmp_path: Path) -> None:
    """R4 4.3：质检结果落 turn 列；坏结论/不存在 turn 都报错。"""
    storage = _open(tmp_path)
    try:
        _session(storage)
        turn = storage.turns.insert(session_id="s1", user_text="你好", now=1.0)
        storage.turns.finish(
            turn.turn_id, assistant_text="回复", status="complete", now=2.0
        )

        storage.turns.set_grounding(
            turn.turn_id,
            score=0.7,
            verdict="unfaithful",
            claims=["用户养了狗"],
            now=9.0,
        )
        row = storage.turns.get(turn.turn_id)
        assert row is not None
        assert row.grounding_score == 0.7
        assert row.grounding_verdict == "unfaithful"
        assert "用户养了狗" in (row.grounding_claims or "")
        assert row.grounding_checked_at == 9.0

        with pytest.raises(EchoesError):
            storage.turns.set_grounding(
                turn.turn_id, score=0.1, verdict="maybe", claims=[], now=10.0
            )
        with pytest.raises(EchoesError):
            storage.turns.set_grounding(
                "ghost", score=0.1, verdict="faithful", claims=[], now=10.0
            )
    finally:
        storage.close()
