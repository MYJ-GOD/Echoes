"""turn 原文 chunk 向量仓储（R3b 3.3b）。

**两份真相成对维护**：`turn_chunk`（业务列 + BLOB）与 `turn_chunk_vec`（vec0）
必须同事务写/删，否则会出现「向量命中但读不出原文」或反过来。`turn_chunk`
可被 `turn` 级联删除，vec0 没有外键——孤儿行由启动清洗 `purge_orphans` 兜底，
检索侧 JOIN `turn_chunk` 也不会把它们漏出来。

**chunk_id 口径**：`<turn_id>#<idx>`，重建同一 turn 的索引时按前缀先删，
避免「编辑上一条」类操作留下新旧两份向量（R4 会用到）。
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db.memory_repo import serialize_vector


@dataclass(frozen=True)
class ChunkHit:
    chunk_id: str
    turn_id: str
    session_id: str
    seq: int
    text: str
    distance: float


class ChunkRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # ------------------------------ 写 ------------------------------

    def upsert(
        self,
        turn_id: str,
        chunks: Sequence[tuple[str, Sequence[float]]],
        *,
        model: str,
        now: float | None = None,
    ) -> int:
        """重建一个 turn 的全部 chunk（先删旧索引，再成对写两张表）。"""
        created = time.time() if now is None else now
        payloads = [serialize_vector(vector) for _, vector in chunks]
        with _guard(self._conn, "写入原文向量"):
            old_ids = [
                str(row[0])
                for row in self._conn.execute(
                    "SELECT chunk_id FROM turn_chunk WHERE turn_id = ?", (turn_id,)
                ).fetchall()
            ]
            if old_ids:
                self._conn.executemany(
                    "DELETE FROM turn_chunk_vec WHERE chunk_id = ?",
                    [(chunk_id,) for chunk_id in old_ids],
                )
                self._conn.execute(
                    "DELETE FROM turn_chunk WHERE turn_id = ?", (turn_id,)
                )
            for index, (text, _) in enumerate(chunks):
                chunk_id = f"{turn_id}#{index}"
                self._conn.execute(
                    "INSERT INTO turn_chunk"
                    " (chunk_id, turn_id, chunk_idx, text, embedding,"
                    "  embedding_model, embedding_dim, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        chunk_id,
                        turn_id,
                        index,
                        text,
                        payloads[index],
                        model,
                        len(chunks[index][1]),
                        created,
                    ),
                )
                self._conn.execute(
                    "INSERT INTO turn_chunk_vec (chunk_id, embedding) VALUES (?, ?)",
                    (chunk_id, payloads[index]),
                )
            self._conn.commit()
        return len(chunks)

    def purge_orphans(self) -> int:
        """清掉 turn 已删除后遗留的向量行（vec0 无外键，启动清洗兜底）。"""
        with _guard(self._conn, "清理孤儿原文向量"):
            vec_ids = {
                str(row[0])
                for row in self._conn.execute(
                    "SELECT chunk_id FROM turn_chunk_vec"
                ).fetchall()
            }
            chunk_ids = {
                str(row[0])
                for row in self._conn.execute("SELECT chunk_id FROM turn_chunk").fetchall()
            }
            orphans = vec_ids - chunk_ids
            if orphans:
                self._conn.executemany(
                    "DELETE FROM turn_chunk_vec WHERE chunk_id = ?",
                    [(chunk_id,) for chunk_id in orphans],
                )
            self._conn.commit()
        return len(orphans)

    # ------------------------------ 读 ------------------------------

    def search(
        self,
        embedding: Sequence[float],
        *,
        k: int = 30,
        profile_id: str = "default",
    ) -> list[ChunkHit]:
        """KNN → 归并回 turn（同一 turn 只留最近的 chunk）。"""
        if k <= 0:
            return []
        payload = serialize_vector(embedding)
        rows = self._conn.execute(
            "SELECT c.chunk_id, c.turn_id, t.session_id, t.seq, c.text, v.distance"
            " FROM turn_chunk_vec v"
            " JOIN turn_chunk c ON c.chunk_id = v.chunk_id"
            " JOIN turn t ON t.turn_id = c.turn_id"
            " WHERE v.embedding MATCH ? AND k = ?"
            "   AND t.status IN ('complete', 'cancelled')"
            "   AND t.superseded_by IS NULL AND t.profile_id = ?"
            " ORDER BY v.distance LIMIT ?",
            (payload, k * 4, profile_id, k),
        ).fetchall()
        best: dict[str, ChunkHit] = {}
        for row in rows:
            hit = ChunkHit(
                chunk_id=str(row[0]),
                turn_id=str(row[1]),
                session_id=str(row[2]),
                seq=int(row[3]),
                text=str(row[4]),
                distance=float(row[5]),
            )
            # rows 已按距离升序：同一 turn 的第一个就是最相关的 chunk
            best.setdefault(hit.turn_id, hit)
        return list(best.values())


@contextmanager
def _guard(conn: sqlite3.Connection, action: str) -> Iterator[None]:
    """sqlite3 错误 → STORAGE_ERROR（含回滚），上层不见裸异常。"""
    try:
        yield
    except sqlite3.Error as exc:
        conn.rollback()
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"{action}失败：{exc}") from exc


__all__ = ["ChunkHit", "ChunkRepo"]
