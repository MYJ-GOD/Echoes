"""记忆仓储（memory_fact + memory_vec）：取代 / 删除 / 向量检索语义。

为什么要锁这么细：vec0 不支持外键，`memory_fact` 与 `memory_vec` 是两份真相，
任何一边单独落库都会留「检索得到但读不出」的幽灵行；而 5.2 的隐私红线要求
「删除即不可检索」——这两点都只能靠仓储层的事务与成对写保证。
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db.memory_repo import EMBEDDING_DIM, MemoryRepo, serialize_vector
from echoes_sidecar.db.repo import Storage

pytest.importorskip("sqlite_vec", reason="记忆向量表需要 sqlite-vec（0002 迁移 -- requires）")


def _vec(*head: float) -> list[float]:
    """构造一个 512 维向量：前几维按语义手摆，其余补 0。"""
    values = list(head) + [0.0] * (EMBEDDING_DIM - len(head))
    assert len(values) == EMBEDDING_DIM
    return values


def _storage(tmp_path: Path) -> Storage:
    return Storage.open(tmp_path / "db" / "echoes.db")


def _insert(repo: MemoryRepo, fact_id: str, text: str, *, category: str = "event", vec=None):
    return repo.insert(
        fact_id=fact_id,
        fact=text,
        category=category,
        embedding=vec if vec is not None else _vec(1.0),
        now=100.0,
        source_session_id="s1",
        source_turn=1,
    )


def test_insert_writes_fact_and_vector_together(tmp_path: Path) -> None:
    """成对写：读得到事实，检索也命中（不是只写了一张表）。"""
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "m1", "用户下周有面试")

    assert repo.get("m1") is not None
    hits = repo.search(_vec(1.0), k=5)
    assert [f.id for f in hits] == ["m1"]


def test_vector_dimension_is_checked_before_write(tmp_path: Path) -> None:
    """维度不符 → 写入前报错（否则会写进 vec0 后变成不可解释的脏行）。"""
    storage = _storage(tmp_path)
    with pytest.raises(EchoesError) as exc_info:
        storage.memories.insert(
            fact_id="bad", fact="x", category="event", embedding=[1.0, 0.0], now=1.0
        )
    assert exc_info.value.code is ErrorCode.STORAGE_ERROR
    assert "嵌入维度不符" in exc_info.value.message
    assert storage.memories.get("bad") is None


def test_unknown_category_is_rejected(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    with pytest.raises(EchoesError) as exc_info:
        _insert(storage.memories, "m1", "x", category="mood")
    assert exc_info.value.code is ErrorCode.STORAGE_ERROR


def test_supersede_keeps_history_but_hides_from_search(tmp_path: Path) -> None:
    """被取代的旧事实：仍可读、标了 superseded_by，但不再参与召回（13.3）。"""
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "old", "用户下周有面试", vec=_vec(1.0))
    repo.supersede(
        "old",
        fact_id="new",
        fact="面试改到周四",
        category="event",
        embedding=_vec(1.0, 0.0, 1.0),
        now=200.0,
        source_session_id="s1",
        source_turn=3,
    )

    assert repo.get("old") is not None
    assert repo.get("old").superseded_by == "new"  # type: ignore[union-attr]
    assert [f.id for f in repo.list_active()] == ["new"]
    assert [f.id for f in repo.search(_vec(1.0), k=5)] == ["new"]


def test_supersede_rejects_missing_or_already_superseded(tmp_path: Path) -> None:
    """取代只对活跃事实生效：不存在的 id 要报错，不能静默「什么也没发生」。"""
    storage = _storage(tmp_path)
    repo = storage.memories
    with pytest.raises(EchoesError):
        repo.supersede(
            "ghost",
            fact_id="x",
            fact="x",
            category="event",
            embedding=_vec(1.0),
            now=1.0,
        )

    _insert(repo, "old", "a")
    repo.supersede(
        "old", fact_id="new", fact="b", category="event", embedding=_vec(1.0), now=2.0
    )
    with pytest.raises(EchoesError):
        repo.supersede(
            "old", fact_id="new2", fact="c", category="event", embedding=_vec(1.0), now=3.0
        )


def test_delete_removes_vector_so_it_cannot_be_retrieved(tmp_path: Path) -> None:
    """16.2 隐私红线：删除后向量同步真删，检索不到（软删标记 + 向量真删）。"""
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "m1", "用户住在杭州")
    repo.delete("m1")

    row = repo.get("m1")
    assert row is not None and row.deleted is True
    assert repo.search(_vec(1.0), k=5) == []
    assert repo.list_active() == []


def test_search_orders_by_distance_and_respects_k(tmp_path: Path) -> None:
    """近邻顺序即语义顺序；k 截断生效。"""
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "near", "用户喜欢喝咖啡", vec=_vec(1.0))
    _insert(repo, "mid", "用户偶尔喝茶", vec=_vec(0.7, 0.7))
    _insert(repo, "far", "用户住在杭州", vec=_vec(0.0, 1.0))

    hits = repo.search(_vec(1.0), k=2)
    assert [f.id for f in hits] == ["near", "mid"]


def test_search_is_profile_scoped(tmp_path: Path) -> None:
    """多 profile 隔离：检索不能跨 profile 串味。"""
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "mine", "我的事")
    repo.insert(
        fact_id="other",
        fact="别人的事",
        category="event",
        embedding=_vec(1.0),
        now=1.0,
        profile_id="guest",
    )

    assert [f.id for f in repo.search(_vec(1.0), k=5)] == ["mine"]
    assert [f.id for f in repo.search(_vec(1.0), k=5, profile_id="guest")] == ["other"]


def test_touch_refreshes_last_seen_without_new_row(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "m1", "用户养了一只猫")
    repo.touch("m1", now=999.0)

    row = repo.get("m1")
    assert row is not None
    assert row.last_seen_at == 999.0
    assert len(repo.list_active()) == 1


def test_serialize_vector_is_little_endian_float32() -> None:
    """格式自检：512 个 float32 小端 = 2048 字节，首值按 `<f` 解得回（vec0 口径）。"""
    payload = serialize_vector([0.5] * EMBEDDING_DIM)
    assert len(payload) == EMBEDDING_DIM * 4
    assert math.isclose(struct.unpack("<f", payload[:4])[0], 0.5, rel_tol=1e-6)


def test_memory_survives_reopen(tmp_path: Path) -> None:
    """WAL 落盘 + 向量持久化：关连接再开，检索仍命中。"""
    db_file = tmp_path / "db" / "echoes.db"
    storage = Storage.open(db_file)
    _insert(storage.memories, "m1", "用户下周有面试")
    storage.close()

    reopened = Storage.open(db_file)
    try:
        assert [f.id for f in reopened.memories.search(_vec(1.0), k=5)] == ["m1"]
    finally:
        reopened.close()


def test_purge_deleted_vectors_removes_only_deleted(tmp_path: Path) -> None:
    """壳侧软删（只标 deleted=1）后，sidecar 启动清洗把向量真删。"""
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "keep", "保留")
    _insert(repo, "gone", "删除")
    # 模拟壳侧删除：只改标记，不动 memory_vec（Rust 连接没有 sqlite-vec）
    storage.conn.execute("UPDATE memory_fact SET deleted = 1 WHERE id = 'gone'")
    storage.conn.commit()

    assert repo.purge_deleted_vectors() == 1
    # 幂等：第二次没有可删的向量
    assert repo.purge_deleted_vectors() == 0
    assert [f.id for f in repo.search(_vec(1.0), k=5)] == ["keep"]


def test_merge_supersedes_all_old_and_keeps_history(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "m1", "喜欢猫")
    _insert(repo, "m2", "喜欢狗")

    merged = repo.merge(
        ["m1", "m2"],
        fact_id="m3",
        fact="喜欢小动物",
        category="preference",
        embedding=_vec(1.0),
        now=200.0,
    )

    assert merged.id == "m3"
    assert [f.id for f in repo.list_active()] == ["m3"]
    assert repo.get("m1").superseded_by == "m3"
    assert repo.get("m2").superseded_by == "m3"
    assert repo.get("m1").deleted is False, "合并是取代，不是删除"


def test_merge_rolls_back_when_any_id_is_missing(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "m1", "喜欢猫")

    with pytest.raises(EchoesError):
        repo.merge(
            ["m1", "ghost"],
            fact_id="m3",
            fact="喜欢小动物",
            category="preference",
            embedding=_vec(1.0),
            now=200.0,
        )

    assert repo.get("m3") is None
    assert repo.get("m1").superseded_by is None, "失败必须整笔回滚"
    assert [f.id for f in repo.list_active()] == ["m1"]


def test_merge_requires_two_ids(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    repo = storage.memories
    _insert(repo, "m1", "喜欢猫")
    with pytest.raises(EchoesError):
        repo.merge(
            ["m1"],
            fact_id="m2",
            fact="喜欢小动物",
            category="preference",
            embedding=_vec(1.0),
            now=200.0,
        )
