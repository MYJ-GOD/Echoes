"""R5 数据导出 / 导入（单文件 JSON）。

**为什么放在 sidecar**：`memory_vec` / `turn_chunk_vec` 是 sqlite-vec 虚表，壳的
只读连接不加载扩展（`voices.rs` / `memory.rs` 同款口径）。导出要带上向量、导入要
写回向量，只能在 Python 侧做。壳只负责起一次性进程、拿一行 JSON 结果。

**范围**：persona / voice 元数据 / session / turn / session_summary /
memory_fact + 向量 / turn_chunk + 向量 / turn_memory_ref。
**不含**：`setting`（导入不该覆盖当前引擎配置）、凭据（在 Windows 凭据管理器）、
音色音频文件（只导元数据，样本路径按原样保留）。

**导入语义**：同一个 id 已存在则保留现有（`INSERT OR IGNORE`），不覆盖、不合并；
整包一个事务，外键检查延迟到 commit；FTS 由 `turn` 触发器自动重建，收尾做一次
`integrity-check`。向量维度与当前库不一致（导出包来自别的嵌入档位）时整包失败，
不做「只导文本」的静默降级。
"""
from __future__ import annotations

import json
import re
import sqlite3
import struct
import time
from pathlib import Path
from typing import Any

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db import Storage
from echoes_sidecar.db.paths import resolve as resolve_paths

FORMAT = "echoes-export/1"
# 单包上限：防止误选一个巨大/损坏文件把内存吃满（个人库远到不了这个量级）
MAX_ROWS = 200_000

_TURN_COLUMNS = (
    "turn_id, session_id, profile_id, seq, user_text, assistant_text, tokens,"
    " status, fail_reason, voice_id, model, persona_id, latency_ms,"
    " started_at, ended_at, superseded_by, grounding_score, grounding_verdict,"
    " grounding_claims, grounding_checked_at, emotion"
)


# ------------------------------ 导出 ------------------------------


def export_bundle(
    dest: Path | str,
    *,
    storage: Storage | None = None,
    data_root: Path | None = None,
) -> dict[str, Any]:
    """把业务库写成 JSON；返回 `{path, sessions, turns, memories, chunks, bytes}`。"""
    paths = resolve_paths(data_root)
    own = storage is None
    store = storage or Storage.open(paths.db_file)
    try:
        conn = store.conn
        personas = _dicts(
            conn,
            "SELECT id, name, system_prompt, created_at, updated_at FROM persona",
        )
        voices = _dicts(
            conn,
            "SELECT id, display_name, sample_path, model_path, status,"
            " quality_score, created_at, kind, provider, engine FROM voice",
        )
        sessions = _dicts(
            conn,
            "SELECT id, profile_id, persona_id, voice_id, started_at,"
            " last_active_at, title, archived_at FROM session",
        )
        turns = _dicts(
            conn,
            f"SELECT {_TURN_COLUMNS} FROM turn ORDER BY session_id, seq",
        )
        summaries = _dicts(
            conn,
            "SELECT session_id, summary, up_to_turn, updated_at FROM session_summary",
        )
        memories = _memory_rows(conn)
        chunks = _chunk_rows(conn)
        refs = _dicts(
            conn, "SELECT turn_id, fact_id, weight FROM turn_memory_ref"
        )
        payload = {
            "format": FORMAT,
            "exportedAt": time.time(),
            "schemaVersion": int(conn.execute("PRAGMA user_version").fetchone()[0]),
            "personas": personas,
            "voices": voices,
            "sessions": sessions,
            "turns": turns,
            "summaries": summaries,
            "memories": memories,
            "chunks": chunks,
            "turnMemoryRefs": refs,
        }
        text = json.dumps(payload, ensure_ascii=False)
    finally:
        if own:
            store.close()

    target = Path(dest)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return {
        "path": str(target),
        "sessions": len(sessions),
        "turns": len(turns),
        "memories": len(memories),
        "chunks": len(chunks),
        "bytes": len(text.encode("utf-8")),
    }


def _memory_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT m.id, m.profile_id, m.fact, m.category, m.source_session_id,"
        " m.source_turn, m.created_at, m.last_seen_at, m.superseded_by, m.deleted,"
        " v.embedding AS vec"
        " FROM memory_fact m LEFT JOIN memory_vec v ON v.fact_id = m.id"
        " ORDER BY m.created_at"
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["embedding"] = _unpack(item.pop("vec", None))
        result.append(item)
    return result


def _chunk_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT c.chunk_id, c.turn_id, c.chunk_idx, c.text, c.embedding_model,"
        " c.embedding_dim, c.created_at, v.embedding AS vec"
        " FROM turn_chunk c LEFT JOIN turn_chunk_vec v ON v.chunk_id = c.chunk_id"
        " ORDER BY c.turn_id, c.chunk_idx"
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["embedding"] = _unpack(item.pop("vec", None))
        result.append(item)
    return result


def _unpack(blob: bytes | None) -> list[float] | None:
    if blob is None:
        return None
    if len(blob) % 4:
        raise EchoesError(ErrorCode.STORAGE_ERROR, "向量 BLOB 长度不是 4 的倍数")
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))


def _dicts(conn: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql)]


# ------------------------------ 导入 ------------------------------


def import_bundle(
    src: Path | str,
    *,
    storage: Storage | None = None,
    data_root: Path | None = None,
) -> dict[str, Any]:
    """合并导入；同 id 保留现有记录。返回 `{sessions, turns, memories, chunks}` 统计。"""
    source = Path(src)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"导入文件不可读：{source}（{exc}）") from exc
    except json.JSONDecodeError as exc:
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"导入文件不是合法 JSON：{exc}") from exc
    if not isinstance(raw, dict) or raw.get("format") != FORMAT:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR, f"不是 Echoes 导出文件（期望 format={FORMAT!r}）"
        )

    tables = {
        key: _rows(raw, key)
        for key in (
            "personas",
            "voices",
            "sessions",
            "turns",
            "summaries",
            "memories",
            "chunks",
            "turnMemoryRefs",
        )
    }

    paths = resolve_paths(data_root)
    own = storage is None
    store = storage or Storage.open(paths.db_file)
    counts = {
        "sessions": len(tables["sessions"]),
        "turns": len(tables["turns"]),
        "memories": len(tables["memories"]),
        "chunks": len(tables["chunks"]),
    }
    try:
        conn = store.conn
        fact_dim = _vec_dim(conn, "memory_vec")
        chunk_dim = _vec_dim(conn, "turn_chunk_vec")
        conn.execute("BEGIN IMMEDIATE")
        try:
            # 自引用 superseded_by 的旧 turn 可能比新 turn 后插入：延迟到 commit 校验
            conn.execute("PRAGMA defer_foreign_keys = ON")
            for row in tables["personas"]:
                conn.execute(
                    "INSERT OR IGNORE INTO persona"
                    " (id, name, system_prompt, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    _pick(
                        row,
                        ("id", "name", "system_prompt", "created_at", "updated_at"),
                    ),
                )
            for row in tables["voices"]:
                conn.execute(
                    "INSERT OR IGNORE INTO voice"
                    " (id, display_name, sample_path, model_path, status,"
                    "  quality_score, created_at, kind, provider, engine)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    _pick(
                        row,
                        (
                            "id",
                            "display_name",
                            "sample_path",
                            "model_path",
                            "status",
                            "quality_score",
                            "created_at",
                            "kind",
                            "provider",
                            "engine",
                        ),
                    ),
                )
            for row in tables["sessions"]:
                conn.execute(
                    "INSERT OR IGNORE INTO session"
                    " (id, profile_id, persona_id, voice_id, started_at,"
                    "  last_active_at, title, archived_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    _pick(
                        row,
                        (
                            "id",
                            "profile_id",
                            "persona_id",
                            "voice_id",
                            "started_at",
                            "last_active_at",
                            "title",
                            "archived_at",
                        ),
                    ),
                )
            for row in tables["turns"]:
                if row.get("status") not in {"pending", "complete", "cancelled", "failed"}:
                    raise EchoesError(
                        ErrorCode.STORAGE_ERROR,
                        f"turn {row.get('turn_id')!r} 状态非法：{row.get('status')!r}",
                    )
                conn.execute(
                    f"INSERT OR IGNORE INTO turn ({_TURN_COLUMNS})"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    _pick(row, tuple(name.strip() for name in _TURN_COLUMNS.split(","))),
                )
            for row in tables["summaries"]:
                conn.execute(
                    "INSERT OR IGNORE INTO session_summary"
                    " (session_id, summary, up_to_turn, updated_at)"
                    " VALUES (?, ?, ?, ?)",
                    _pick(row, ("session_id", "summary", "up_to_turn", "updated_at")),
                )
            for row in tables["memories"]:
                conn.execute(
                    "INSERT OR IGNORE INTO memory_fact"
                    " (id, profile_id, fact, category, source_session_id, source_turn,"
                    "  created_at, last_seen_at, superseded_by, deleted)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    _pick(
                        row,
                        (
                            "id",
                            "profile_id",
                            "fact",
                            "category",
                            "source_session_id",
                            "source_turn",
                            "created_at",
                            "last_seen_at",
                            "superseded_by",
                            "deleted",
                        ),
                    ),
                )
                vector = row.get("embedding")
                if vector is not None:
                    _check_dim(vector, fact_dim, f"记忆向量 {row.get('id')!r}")
                    conn.execute(
                        "DELETE FROM memory_vec WHERE fact_id = ?", (row.get("id"),)
                    )
                    conn.execute(
                        "INSERT INTO memory_vec (fact_id, embedding) VALUES (?, ?)",
                        (row.get("id"), _pack(vector, fact_dim)),
                    )
            for row in tables["chunks"]:
                vector = row.get("embedding")
                blob = b""
                if vector is not None:
                    _check_dim(vector, chunk_dim, f"原文向量 {row.get('chunk_id')!r}")
                    blob = _pack(vector, chunk_dim)
                conn.execute(
                    "INSERT OR IGNORE INTO turn_chunk"
                    " (chunk_id, turn_id, chunk_idx, text, embedding,"
                    "  embedding_model, embedding_dim, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row.get("chunk_id"),
                        row.get("turn_id"),
                        row.get("chunk_idx"),
                        row.get("text"),
                        # 业务列 BLOB 与 vec0 同源：存同一份 f32 字节
                        blob,
                        row.get("embedding_model"),
                        row.get("embedding_dim"),
                        row.get("created_at"),
                    ),
                )
                if vector is not None:
                    conn.execute(
                        "DELETE FROM turn_chunk_vec WHERE chunk_id = ?",
                        (row.get("chunk_id"),),
                    )
                    conn.execute(
                        "INSERT INTO turn_chunk_vec (chunk_id, embedding) VALUES (?, ?)",
                        (row.get("chunk_id"), blob),
                    )
            for row in tables["turnMemoryRefs"]:
                conn.execute(
                    "INSERT OR REPLACE INTO turn_memory_ref (turn_id, fact_id, weight)"
                    " VALUES (?, ?, ?)",
                    _pick(row, ("turn_id", "fact_id", "weight")),
                )
            # 触发器已增量维护 FTS；这里只做完整性验收（失败即整包回滚）
            conn.execute("INSERT INTO turn_fts(turn_fts) VALUES('integrity-check')")
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise EchoesError(
                ErrorCode.STORAGE_ERROR, f"导入失败（已回滚）：{exc}"
            ) from exc
        except BaseException:
            conn.rollback()
            raise
    finally:
        if own:
            store.close()
    return counts


def _rows(raw: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"导出文件字段 {key!r} 必须是数组")
    if len(value) > MAX_ROWS:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR, f"导出文件字段 {key!r} 超过 {MAX_ROWS} 行上限"
        )
    for item in value:
        if not isinstance(item, dict):
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"导出文件字段 {key!r} 的行必须是对象")
    return value


def _pick(row: dict[str, Any], keys: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row.get(key) for key in keys)


def _vec_dim(conn: sqlite3.Connection, table: str) -> int | None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = ?", (table,)
    ).fetchone()
    text = str(row[0]) if row is not None else ""
    match = re.search(r"FLOAT\[(\d+)\]", text)
    return int(match.group(1)) if match else None


def _check_dim(vector: Any, expected: int | None, label: str) -> None:
    if not isinstance(vector, list) or not vector:
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"{label} 缺向量或不是数组")
    if expected is not None and len(vector) != expected:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR,
            f"{label} 维度 {len(vector)} 与当前库 {expected} 不一致："
            "导出包来自其它嵌入档位，不能直接导入",
        )
    for value in vector:
        if not isinstance(value, (int, float)):
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"{label} 含非数值元素")


def _pack(vector: list[float], _dim: int | None) -> bytes:
    return struct.pack(f"<{len(vector)}f", *(float(value) for value in vector))


__all__ = ["FORMAT", "MAX_ROWS", "export_bundle", "import_bundle"]
