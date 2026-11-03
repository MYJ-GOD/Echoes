"""R3b 3.3b：原文 chunk 向量仓储（成对写、归并、孤儿清理）。"""

from __future__ import annotations

import time
from pathlib import Path

from echoes_sidecar.db.memory_repo import serialize_vector
from echoes_sidecar.db.repo import Storage


def _setup(tmp_path: Path) -> tuple[Storage, str]:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    now = time.time()
    persona = storage.personas.sync(
        persona_id="default", name="人设", system_prompt="s", now=now
    )
    storage.sessions.create(session_id="s1", persona_id=persona.id, now=now)
    turn = storage.turns.insert(session_id="s1", user_text="我在学吉他", now=now)
    storage.turns.finish(
        turn.turn_id, assistant_text="那很好", status="complete", now=now
    )
    return storage, turn.turn_id


def _vec(head: float) -> list[float]:
    return [head, 1.0 - head] + [0.0] * 510


def test_upsert_writes_both_tables_and_search_merges_by_turn(tmp_path: Path) -> None:
    storage, turn_id = _setup(tmp_path)
    repo = storage.chunks
    assert repo.upsert(
        turn_id,
        [("第一块：我在学吉他", _vec(1.0)), ("第二块：那很好", _vec(0.0))],
        model="bge-small-zh-v1.5",
        now=1.0,
    ) == 2

    hits = repo.search(_vec(1.0), k=5)
    assert len(hits) == 1, "同一 turn 的多个 chunk 归并成一条"
    assert hits[0].turn_id == turn_id
    assert hits[0].text.startswith("第一块")
    assert hits[0].seq == 1

    count = storage.conn.execute("SELECT count(*) FROM turn_chunk").fetchone()
    assert count is not None and int(count[0]) == 2


def test_reindex_replaces_old_chunks(tmp_path: Path) -> None:
    storage, turn_id = _setup(tmp_path)
    repo = storage.chunks
    repo.upsert(turn_id, [("旧", _vec(1.0)), ("旧2", _vec(0.0))], model="bge", now=1.0)
    repo.upsert(turn_id, [("新", _vec(1.0))], model="bge", now=2.0)

    rows = storage.conn.execute(
        "SELECT chunk_id FROM turn_chunk WHERE turn_id = ?", (turn_id,)
    ).fetchall()
    assert [row[0] for row in rows] == [f"{turn_id}#0"]
    # 旧向量一起清掉：否则 KNN 会命中已经不存在的 chunk
    vec_rows = storage.conn.execute(
        "SELECT count(*) FROM turn_chunk_vec WHERE chunk_id = ?",
        (f"{turn_id}#1",),
    ).fetchone()
    assert vec_rows is not None and int(vec_rows[0]) == 0


def test_purge_orphans_removes_vectors_without_chunks(tmp_path: Path) -> None:
    storage, turn_id = _setup(tmp_path)
    repo = storage.chunks
    repo.upsert(turn_id, [("原文", _vec(1.0))], model="bge", now=1.0)

    # 模拟 turn 级联删除后残留的 vec 行
    storage.conn.execute("DELETE FROM turn WHERE turn_id = ?", (turn_id,))
    storage.conn.commit()
    assert storage.conn.execute("SELECT count(*) FROM turn_chunk").fetchone()[0] == 0
    assert repo.purge_orphans() == 1
    assert repo.purge_orphans() == 0


def test_search_filters_pending_and_superseded_turns(tmp_path: Path) -> None:
    storage, turn_id = _setup(tmp_path)
    repo = storage.chunks
    repo.upsert(turn_id, [("原文", _vec(1.0))], model="bge", now=1.0)

    # superseded_by 有外键：指向一个真实存在的 turn
    newer = storage.turns.insert(session_id="s1", user_text="重说版本", now=2.0)
    storage.conn.execute(
        "UPDATE turn SET superseded_by = ? WHERE turn_id = ?",
        (newer.turn_id, turn_id),
    )
    storage.conn.commit()
    assert repo.search(_vec(1.0), k=5) == []


def test_vector_serialization_is_dim_checked(tmp_path: Path) -> None:
    storage, turn_id = _setup(tmp_path)
    import pytest

    from echoes_sidecar.core.errors import EchoesError, ErrorCode

    with pytest.raises(EchoesError) as err:
        storage.chunks.upsert(turn_id, [("短", [1.0])], model="bge", now=1.0)
    assert err.value.code is ErrorCode.STORAGE_ERROR
    # 维度不符时不能留下半截业务行
    assert storage.conn.execute("SELECT count(*) FROM turn_chunk").fetchone()[0] == 0


def test_serialize_vector_used_consistently(tmp_path: Path) -> None:
    storage, turn_id = _setup(tmp_path)
    payload = serialize_vector(_vec(1.0))
    assert len(payload) == 512 * 4
    storage.chunks.upsert(turn_id, [("原文", _vec(1.0))], model="bge", now=1.0)
    assert storage.chunks.search(_vec(1.0), k=1)
