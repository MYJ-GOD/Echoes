"""memory_fact 仓储 + sqlite-vec 向量同步（母文档 5.1/5.2/16.2）。

**为什么成对维护**：`memory_fact`（业务行）与 `memory_vec`（vec0 虚表）是两份真相，
vec0 不支持外键，所以「写事实」与「写向量」必须在同一个事务里成对完成；
删/取代同理。任何一边单独落库都会留下「检索得到但读不出来」的幽灵行。

**取代语义（superseded_by）**：新事实取代旧事实时不删旧行，而是把旧行指向新
id——「用户下周有面试」被「面试改到周四」取代后，历史仍然可追溯（13.3 的
「替代正确率 ≥0.9」判的就是这一步），检索只走 `superseded_by IS NULL AND deleted = 0`。

**删除语义（16.2）**：`deleted = 1` 是软删标记，同时**真的删掉向量行**——隐私
要求「删除即不可检索」，留着向量等于留着语义指纹。
"""
from __future__ import annotations

import sqlite3
import struct
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from echoes_sidecar.core.errors import EchoesError, ErrorCode

# 默认嵌入档 bge-small-zh（ADR-006）；与迁移 0002 的 FLOAT[512] 必须一致。
EMBEDDING_DIM = 512

CATEGORIES = frozenset({"preference", "event", "identity", "other"})


@dataclass(frozen=True)
class MemoryFact:
    """一条记忆事实（5.1 memory_fact 行）。"""

    id: str
    profile_id: str
    fact: str
    category: str
    source_session_id: str | None
    source_turn: int | None
    created_at: float
    last_seen_at: float
    superseded_by: str | None = None
    deleted: bool = False


def serialize_vector(values: Sequence[float]) -> bytes:
    """float 列表 → sqlite-vec 的 raw-bytes 形态（小端 float32，无头）。

    不依赖 `sqlite_vec` 包的这个工具函数：能写就说明扩展在，但序列化是纯格式
    问题，自己实现少一层「功能依赖被测库」的耦合（形状错误在写入前就报）。
    """
    if len(values) != EMBEDDING_DIM:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR,
            f"嵌入维度不符：期望 {EMBEDDING_DIM}，实际 {len(values)}（ADR-006 默认档）",
        )
    return struct.pack(f"<{EMBEDDING_DIM}f", *values)


class MemoryRepo:
    """memory_fact CRUD + 向量同步 + KNN 检索（5.2）。"""

    _COLUMNS = (
        "id, profile_id, fact, category, source_session_id, source_turn,"
        " created_at, last_seen_at, superseded_by, deleted"
    )

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------ 写 ------------------------------

    def insert(
        self,
        *,
        fact_id: str,
        fact: str,
        category: str,
        embedding: Sequence[float],
        now: float,
        profile_id: str = "default",
        source_session_id: str | None = None,
        source_turn: int | None = None,
    ) -> MemoryFact:
        """落一条事实 + 它的向量（同一事务）。"""
        if category not in CATEGORIES:
            raise EchoesError(
                ErrorCode.STORAGE_ERROR,
                f"未知记忆类别 {category!r}（5.1：{'/'.join(sorted(CATEGORIES))}）",
            )
        payload = serialize_vector(embedding)  # 先校形状：别在事务里才发现维度错
        with _guard(self._conn, "写入记忆"):
            self._conn.execute(
                "INSERT INTO memory_fact"
                f" ({self._COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0)",
                (
                    fact_id,
                    profile_id,
                    fact,
                    category,
                    source_session_id,
                    source_turn,
                    now,
                    now,
                ),
            )
            self._conn.execute(
                "INSERT INTO memory_vec (fact_id, embedding) VALUES (?, ?)",
                (fact_id, payload),
            )
            self._conn.commit()
        return MemoryFact(
            id=fact_id,
            profile_id=profile_id,
            fact=fact,
            category=category,
            source_session_id=source_session_id,
            source_turn=source_turn,
            created_at=now,
            last_seen_at=now,
        )

    def supersede(
        self,
        old_id: str,
        *,
        fact_id: str,
        fact: str,
        category: str,
        embedding: Sequence[float],
        now: float,
        profile_id: str = "default",
        source_session_id: str | None = None,
        source_turn: int | None = None,
    ) -> MemoryFact:
        """新事实取代旧事实：旧行标 superseded_by、向量**保留**（历史可追溯）。

        检索面只看 `superseded_by IS NULL`，所以保留旧向量不会污染召回。
        """
        payload = serialize_vector(embedding)
        with _guard(self._conn, "取代记忆"):
            cursor = self._conn.execute(
                "UPDATE memory_fact SET superseded_by = ? WHERE id = ? AND superseded_by IS NULL",
                (fact_id, old_id),
            )
            if cursor.rowcount == 0:
                raise EchoesError(
                    ErrorCode.STORAGE_ERROR,
                    f"记忆 {old_id} 不存在或已被取代（supersede 只对活跃事实生效）",
                )
            self._conn.execute(
                "INSERT INTO memory_fact"
                f" ({self._COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 0)",
                (
                    fact_id,
                    profile_id,
                    fact,
                    category,
                    source_session_id,
                    source_turn,
                    now,
                    now,
                ),
            )
            self._conn.execute(
                "INSERT INTO memory_vec (fact_id, embedding) VALUES (?, ?)",
                (fact_id, payload),
            )
            self._conn.commit()
        return MemoryFact(
            id=fact_id,
            profile_id=profile_id,
            fact=fact,
            category=category,
            source_session_id=source_session_id,
            source_turn=source_turn,
            created_at=now,
            last_seen_at=now,
        )

    def touch(self, fact_id: str, *, now: float) -> None:
        """再次提到同一事实：刷新 last_seen_at（不新增行）。"""
        with _guard(self._conn, "刷新记忆时间"):
            cursor = self._conn.execute(
                "UPDATE memory_fact SET last_seen_at = ? WHERE id = ?", (now, fact_id)
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"记忆不存在：{fact_id}")

    def delete(self, fact_id: str) -> None:
        """软删事实 + 真删向量（16.2：删除即不可检索）。"""
        with _guard(self._conn, "删除记忆"):
            cursor = self._conn.execute(
                "UPDATE memory_fact SET deleted = 1 WHERE id = ?", (fact_id,)
            )
            self._conn.execute("DELETE FROM memory_vec WHERE fact_id = ?", (fact_id,))
            self._conn.commit()
        if cursor.rowcount == 0:
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"记忆不存在：{fact_id}")

    # ------------------------------ 读 ------------------------------

    def get(self, fact_id: str) -> MemoryFact | None:
        row = self._conn.execute(
            f"SELECT {self._COLUMNS} FROM memory_fact WHERE id = ?", (fact_id,)
        ).fetchone()
        return None if row is None else _fact_from_row(row)

    def list_active(self, profile_id: str = "default", *, limit: int = 200) -> list[MemoryFact]:
        """当前有效事实（未删、未被取代），按最近提到排序。"""
        rows = self._conn.execute(
            f"SELECT {self._COLUMNS} FROM memory_fact"
            " WHERE profile_id = ? AND deleted = 0 AND superseded_by IS NULL"
            " ORDER BY last_seen_at DESC LIMIT ?",
            (profile_id, limit),
        ).fetchall()
        return [_fact_from_row(row) for row in rows]

    def search(
        self, embedding: Sequence[float], *, k: int = 5, profile_id: str = "default"
    ) -> list[MemoryFact]:
        """向量近邻检索（5.2：sqlite-vec 暴力扫描，k=5~8）。

        `distance` 是 L2 距离（vec0 默认），调用方只按顺序用，不解读绝对值。
        取 `k*4` 的候选池再按 profile/删除面过滤后截断：vec0 的 `k = ?` 先生效、
        WHERE 里的业务过滤是**后置**的，直接按 k 取会让「被过滤掉几条」变成
        「召回不足 k 条」。
        """
        payload = serialize_vector(embedding)
        columns = ", ".join(f"f.{name.strip()}" for name in self._COLUMNS.split(","))
        rows = self._conn.execute(
            f"SELECT {columns}"
            " FROM memory_vec v JOIN memory_fact f ON f.id = v.fact_id"
            " WHERE v.embedding MATCH ? AND k = ?"
            "   AND f.profile_id = ? AND f.deleted = 0 AND f.superseded_by IS NULL"
            " ORDER BY v.distance LIMIT ?",
            (payload, k * 4, profile_id, k),
        ).fetchall()
        return [_fact_from_row(row) for row in rows]


@contextmanager
def _guard(conn: sqlite3.Connection, action: str) -> Iterator[None]:
    """sqlite3 错误 → STORAGE_ERROR（含回滚），上层不见裸异常（同 repo.py 口径）。"""
    try:
        yield
    except sqlite3.Error as exc:
        conn.rollback()
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"{action}失败：{exc}") from exc


def _fact_from_row(row: sqlite3.Row) -> MemoryFact:
    return MemoryFact(
        id=str(row[0]),
        profile_id=str(row[1]),
        fact=str(row[2]),
        category=str(row[3]),
        source_session_id=None if row[4] is None else str(row[4]),
        source_turn=None if row[5] is None else int(row[5]),
        created_at=float(row[6]),
        last_seen_at=float(row[7]),
        superseded_by=None if row[8] is None else str(row[8]),
        deleted=bool(row[9]),
    )


__all__ = ["CATEGORIES", "EMBEDDING_DIM", "MemoryFact", "MemoryRepo", "serialize_vector"]
