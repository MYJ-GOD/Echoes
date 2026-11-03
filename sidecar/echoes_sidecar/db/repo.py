"""最小 CRUD（母文档 5.1/14.2）：persona / voice / session / setting。

边界（15.2 依赖分层）：db 只依赖 core，**不 import session 聚合**——返回行对象，
由组合根映射成 `Session`（4.6 聚合归 session 层，反向依赖会破分层）。

事务边界（14.2）：单条状态变更 = 一个事务；写操作由上层串行（单写者）。
全部错误映射 `STORAGE_ERROR`（3.4.1 报错而非降级）。
"""
from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import jieba  # type: ignore[import-untyped]

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import Persona, VoiceStatus
from echoes_sidecar.db.chunk_repo import ChunkRepo
from echoes_sidecar.db.connection import connect
from echoes_sidecar.db.memory_repo import MemoryRepo

jieba.setLogLevel(logging.WARNING)


@contextmanager
def _guard(conn: sqlite3.Connection, action: str) -> Iterator[None]:
    """sqlite3 错误 → STORAGE_ERROR（含回滚），避免上层见到裸 sqlite 异常。"""
    try:
        yield
    except sqlite3.Error as exc:
        conn.rollback()
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"{action}失败：{exc}") from exc


def _text(value: Any) -> str:
    return str(value)


def _opt_text(value: Any) -> str | None:
    return None if value is None else str(value)


def _num(value: Any) -> float:
    return float(value)


def _opt_num(value: Any) -> float | None:
    return None if value is None else float(value)


@dataclass(frozen=True)
class VoiceRow:
    """5.1 voice 表行（sample_path 云端可空；engine 用于本地引擎绑定）。"""

    id: str
    display_name: str
    sample_path: str | None
    model_path: str | None
    status: VoiceStatus
    quality_score: float | None
    created_at: float
    engine: str


@dataclass(frozen=True)
class SessionSummaryRow:
    """会话摘要命中行（R3a 3.3a）：「我们上周在聊什么」的检索出口。"""

    session_id: str
    title: str | None
    summary: str
    updated_at: float


@dataclass(frozen=True)
class SessionRow:
    """5.1 session 表行；组合根据此重建 Session（14.1 v1.4 重启语义）。"""

    id: str
    profile_id: str
    persona_id: str
    voice_id: str | None
    started_at: float
    last_active_at: float
    title: str | None = None
    archived_at: float | None = None


@dataclass(frozen=True)
class SessionSummary:
    """5.1 session_summary 行（滚动摘要；`up_to_turn` 是已摘要到的 turn）。"""

    session_id: str
    summary: str
    up_to_turn: int
    updated_at: float


@dataclass(frozen=True)
class TurnRow:
    """5.1 turn 原文行（R1a；含 pending/终态与 superseded 指针）。"""

    turn_id: str
    session_id: str
    profile_id: str
    seq: int
    user_text: str
    assistant_text: str | None
    tokens: str
    status: str
    fail_reason: str | None
    voice_id: str | None
    model: str | None
    persona_id: str | None
    latency_ms: int | None
    started_at: float
    ended_at: float | None
    superseded_by: str | None
    # R4 4.3 Grounding：NULL = 未质检（无注入记忆/judge 不可用/失败）
    grounding_score: float | None = None
    grounding_verdict: str | None = None
    grounding_claims: str | None = None
    grounding_checked_at: float | None = None
    # R4 4.7：用户情绪标签（NULL/neutral = 未命中）
    emotion: str | None = None


def _voice_status(raw: Any) -> VoiceStatus:
    try:
        return VoiceStatus(str(raw))
    except ValueError as exc:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR, f"voice.status 非法值：{raw!r}（2.5 三态）"
        ) from exc


class PersonaRepo:
    """人设卡（4.6/5.1）：prompt 单一来源在代码（persona.py），DB 只做持久化镜像。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, persona_id: str) -> Persona | None:
        row = self._conn.execute(
            "SELECT id, name, system_prompt, created_at, updated_at"
            " FROM persona WHERE id = ?",
            (persona_id,),
        ).fetchone()
        return None if row is None else _persona_from_row(row)

    def sync(self, *, persona_id: str, name: str, system_prompt: str, now: float) -> Persona:
        """落库并与代码侧 prompt 对齐（改 prompt 即更新，避免 DB 陈旧覆盖代码）。"""
        existing = self.get(persona_id)
        if existing is None:
            with _guard(self._conn, "写入人设"):
                self._conn.execute(
                    "INSERT INTO persona (id, name, system_prompt, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (persona_id, name, system_prompt, now, now),
                )
                self._conn.commit()
            return Persona(
                id=persona_id,
                name=name,
                system_prompt=system_prompt,
                created_at=now,
                updated_at=now,
            )
        if existing.name == name and existing.system_prompt == system_prompt:
            return existing
        with _guard(self._conn, "更新人设"):
            self._conn.execute(
                "UPDATE persona SET name = ?, system_prompt = ?, updated_at = ? WHERE id = ?",
                (name, system_prompt, now, persona_id),
            )
            self._conn.commit()
        return Persona(
            id=persona_id,
            name=name,
            system_prompt=system_prompt,
            created_at=existing.created_at,
            updated_at=now,
        )


def _persona_from_row(row: sqlite3.Row) -> Persona:
    return Persona(
        id=_text(row["id"]),
        name=_text(row["name"]),
        system_prompt=_text(row["system_prompt"]),
        created_at=_num(row["created_at"]),
        updated_at=_num(row["updated_at"]),
    )


class VoiceRepo:
    """音色资产元数据（2.5 三态）：training→ready/failed，禁止静默回退。"""

    _COLUMNS = (
        "id, display_name, sample_path, model_path, status, quality_score,"
        " created_at, engine"
    )

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, voice_id: str) -> VoiceRow | None:
        row = self._conn.execute(
            f"SELECT {self._COLUMNS} FROM voice WHERE id = ?",  # 列名为模块常量，无注入面
            (voice_id,),
        ).fetchone()
        return None if row is None else _voice_from_row(row)

    def list_all(self) -> list[VoiceRow]:
        rows = self._conn.execute(
            f"SELECT {self._COLUMNS} FROM voice ORDER BY created_at ASC"
        ).fetchall()
        return [_voice_from_row(row) for row in rows]

    def insert_training(
        self, *, voice_id: str, display_name: str, sample_path: str, now: float
    ) -> VoiceRow:
        """克隆开工即落行（status=training），崩溃后由 fail_orphans 收敛（14.1）。"""
        with _guard(self._conn, "写入音色"):
            self._conn.execute(
                "INSERT INTO voice"
                " (id, display_name, sample_path, model_path, status, quality_score, created_at)"
                " VALUES (?, ?, ?, NULL, ?, NULL, ?)",
                (voice_id, display_name, sample_path, VoiceStatus.TRAINING.value, now),
            )
            self._conn.commit()
        return VoiceRow(
            id=voice_id,
            display_name=display_name,
            sample_path=sample_path,
            model_path=None,
            status=VoiceStatus.TRAINING,
            quality_score=None,
            created_at=now,
            engine="cosyvoice2",
        )

    def mark_ready(self, voice_id: str, *, model_path: str | None = None) -> None:
        """克隆成功：status=ready 并记产出文件（相对资产目录，3.2）。

        model_path=None 表示引擎未产出独立资产文件（如 mock 引擎、或 zero-shot
        直接复用样本）——此时 ready 态仍成立，不编造路径（5.1 注释：未生成成功为 NULL）。
        """
        with _guard(self._conn, "更新音色状态"):
            cursor = self._conn.execute(
                "UPDATE voice SET status = ?, model_path = ? WHERE id = ?",
                (VoiceStatus.READY.value, model_path, voice_id),
            )
            self._conn.commit()
        self._require_row(cursor, voice_id)

    def mark_failed(self, voice_id: str) -> None:
        """克隆失败：status=failed，model_path 保持原值（失败不抹已有资产，2.5）。"""
        with _guard(self._conn, "更新音色状态"):
            cursor = self._conn.execute(
                "UPDATE voice SET status = ? WHERE id = ?",
                (VoiceStatus.FAILED.value, voice_id),
            )
            self._conn.commit()
        self._require_row(cursor, voice_id)

    @staticmethod
    def _require_row(cursor: sqlite3.Cursor, voice_id: str) -> None:
        if cursor.rowcount == 0:
            raise EchoesError(ErrorCode.VOICE_NOT_AVAILABLE, f"音色不存在：{voice_id}")

    def set_quality(self, voice_id: str, score: float) -> None:
        """阶段 2 质检分（0–1）；失败音色也可以记录分数供 UI 解释。"""
        if not 0.0 <= score <= 1.0:
            raise EchoesError(
                ErrorCode.STORAGE_ERROR, f"音色质量分越界：{score}（应在 0–1）"
            )
        with _guard(self._conn, "写入音色质量分"):
            cursor = self._conn.execute(
                "UPDATE voice SET quality_score = ? WHERE id = ?",
                (score, voice_id),
            )
            self._conn.commit()
        self._require_row(cursor, voice_id)

    def fail_orphans(self) -> int:
        """启动自检（14.1）：上次被 kill/断电遗留的 training 孤儿置 failed。"""
        with _guard(self._conn, "清理孤儿音色"):
            cursor = self._conn.execute(
                "UPDATE voice SET status = ? WHERE status = ?",
                (VoiceStatus.FAILED.value, VoiceStatus.TRAINING.value),
            )
            self._conn.commit()
        return int(cursor.rowcount)

    def adopt_id(self, provisional_id: str, final_id: str) -> None:
        """把开工占位行的 id 改成引擎返回的 voice_id（4.5：资产身份由引擎产出）。

        为什么需要：14.1 要求克隆**开工即落 training 行**（否则 kill/断电无孤儿可扫），
        而 4.5 的 `clone(sample) -> voice_id` 由引擎决定资产 ID，调用前拿不到。
        改主键安全的前提：session.voice_id 尚未指向该行（绑定发生在克隆成功之后），
        故不会触发外键重挂。两者相同时为 no-op。
        """
        if provisional_id == final_id:
            return
        with _guard(self._conn, "改写音色 ID"):
            existing = self._conn.execute(
                "SELECT id FROM voice WHERE id = ?", (final_id,)
            ).fetchone()
            if existing is not None:
                raise EchoesError(
                    ErrorCode.CLONE_ENGINE_FAILED,
                    f"引擎返回的 voice_id 已存在：{final_id}（4.5 资产 ID 冲突）",
                )
            cursor = self._conn.execute(
                "UPDATE voice SET id = ? WHERE id = ?", (final_id, provisional_id)
            )
            self._conn.commit()
        self._require_row(cursor, provisional_id)


def _voice_from_row(row: sqlite3.Row) -> VoiceRow:
    return VoiceRow(
        id=_text(row["id"]),
        display_name=_text(row["display_name"]),
        sample_path=_opt_text(row["sample_path"]),
        model_path=_opt_text(row["model_path"]),
        status=_voice_status(row["status"]),
        quality_score=_opt_num(row["quality_score"]),
        created_at=_num(row["created_at"]),
        engine=_text(row["engine"]),
    )


class SessionRepo:
    """会话行（5.1）：阶段 0 单会话，但路径按 id 查找写（4.6 远程复用）。"""

    _COLUMNS = (
        "id, profile_id, persona_id, voice_id, started_at, last_active_at,"
        " title, archived_at"
    )

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, session_id: str) -> SessionRow | None:
        row = self._conn.execute(
            f"SELECT {self._COLUMNS} FROM session WHERE id = ?",  # 列名为模块常量，无注入面
            (session_id,),
        ).fetchone()
        return None if row is None else _session_from_row(row)

    def latest(self) -> SessionRow | None:
        """14.1 v1.4：重启后依「最近活跃」session 重建（archived 不参与）。"""
        row = self._conn.execute(
            f"SELECT {self._COLUMNS} FROM session"
            " WHERE archived_at IS NULL"
            " ORDER BY last_active_at DESC LIMIT 1"
        ).fetchone()
        return None if row is None else _session_from_row(row)

    def search_summaries(
        self, query: str, *, limit: int = 10, since: float | None = None
    ) -> list[SessionSummaryRow]:
        """按标题 + 摘要检索会话（R3a 3.3a）。

        中文用 LIKE 子串而不是 FTS：`session` 与 `session_summary` 是两张表，
        FTS5 的 external-content 只能指向单表；为几万条以内的会话再建一张
        contentless 镜像并维护双写不划算。命中的是「会话级」候选，量小，
        时间过滤（`since`）才是主要收敛手段。
        """
        text = query.strip()
        if not text or limit <= 0:
            return []
        like = _like_pattern(text)
        where = ["(s.title LIKE ? ESCAPE '\\' OR ss.summary LIKE ? ESCAPE '\\')"]
        params: list[Any] = [like, like]
        if since is not None:
            where.append("ss.updated_at >= ?")
            params.append(since)
        rows = self._conn.execute(
            "SELECT ss.session_id, s.title, ss.summary, ss.updated_at"
            " FROM session_summary ss JOIN session s ON s.id = ss.session_id"
            f" WHERE {' AND '.join(where)}"
            " ORDER BY ss.updated_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [
            SessionSummaryRow(
                session_id=str(row[0]),
                title=None if row[1] is None else str(row[1]),
                summary=str(row[2]),
                updated_at=float(row[3]),
            )
            for row in rows
        ]

    def create(
        self,
        *,
        session_id: str,
        persona_id: str,
        profile_id: str = "default",
        voice_id: str | None = None,
        title: str | None = None,
        now: float,
    ) -> SessionRow:
        with _guard(self._conn, "创建会话"):
            self._conn.execute(
                "INSERT INTO session"
                " (id, profile_id, persona_id, voice_id, started_at, last_active_at, title)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, profile_id, persona_id, voice_id, now, now, title),
            )
            self._conn.commit()
        return SessionRow(
            id=session_id,
            profile_id=profile_id,
            persona_id=persona_id,
            voice_id=voice_id,
            started_at=now,
            last_active_at=now,
            title=title,
            archived_at=None,
        )

    def touch(self, session_id: str, *, now: float) -> None:
        """turn 收尾打点（轮次原文见 0003 turn 表；此处只更新活跃时间）。"""
        with _guard(self._conn, "更新会话活跃时间"):
            self._conn.execute(
                "UPDATE session SET last_active_at = ? WHERE id = ?", (now, session_id)
            )
            self._conn.commit()

    def bind_voice(self, session_id: str, voice_id: str | None) -> None:
        """克隆完成后绑定当前会话（2.5/§12 步骤 5）。"""
        with _guard(self._conn, "绑定音色"):
            cursor = self._conn.execute(
                "UPDATE session SET voice_id = ? WHERE id = ?", (voice_id, session_id)
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"会话不存在：{session_id}")

    def set_title_if_empty(self, session_id: str, title: str) -> None:
        """R1c：首条消息生成标题；已有标题不覆盖。"""
        text = " ".join(title.split())[:40]
        if not text:
            return
        with _guard(self._conn, "写入会话标题"):
            self._conn.execute(
                "UPDATE session SET title = ?"
                " WHERE id = ? AND (title IS NULL OR trim(title) = '')",
                (text, session_id),
            )
            self._conn.commit()

    def get_summary(self, session_id: str) -> SessionSummary | None:
        """读滚动摘要（5.2：每 10 轮/30 分钟更新；重启后仍可注入）。"""
        row = self._conn.execute(
            "SELECT session_id, summary, up_to_turn, updated_at"
            " FROM session_summary WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return None if row is None else _summary_from_row(row)

    def save_summary(
        self, session_id: str, *, summary: str, up_to_turn: int, now: float
    ) -> SessionSummary:
        """upsert 摘要；空摘要视为错误（不能把会话上下文静默清空）。"""
        text = summary.strip()
        if not text:
            raise EchoesError(ErrorCode.STORAGE_ERROR, "会话摘要不能为空")
        with _guard(self._conn, "写入会话摘要"):
            self._conn.execute(
                "INSERT INTO session_summary (session_id, summary, up_to_turn, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(session_id) DO UPDATE SET"
                " summary = excluded.summary,"
                " up_to_turn = excluded.up_to_turn,"
                " updated_at = excluded.updated_at",
                (session_id, text, up_to_turn, now),
            )
            self._conn.commit()
        return SessionSummary(
            session_id=session_id,
            summary=text,
            up_to_turn=up_to_turn,
            updated_at=now,
        )


def _session_from_row(row: sqlite3.Row) -> SessionRow:
    return SessionRow(
        id=_text(row["id"]),
        profile_id=_text(row["profile_id"]),
        persona_id=_text(row["persona_id"]),
        voice_id=_opt_text(row["voice_id"]),
        started_at=_num(row["started_at"]),
        last_active_at=_num(row["last_active_at"]),
        title=_opt_text(row["title"]),
        archived_at=_opt_num(row["archived_at"]),
    )


def _summary_from_row(row: sqlite3.Row) -> SessionSummary:
    return SessionSummary(
        session_id=_text(row["session_id"]),
        summary=_text(row["summary"]),
        up_to_turn=int(row["up_to_turn"]),
        updated_at=_num(row["updated_at"]),
    )


_TURN_STATUSES = frozenset({"pending", "complete", "cancelled", "failed"})
_TURN_COLUMNS = (
    "turn_id, session_id, profile_id, seq, user_text, assistant_text, tokens,"
    " status, fail_reason, voice_id, model, persona_id, latency_ms,"
    " started_at, ended_at, superseded_by,"
    " grounding_score, grounding_verdict, grounding_claims, grounding_checked_at,"
    " emotion"
)
_TURN_QUERY_STOPWORDS = frozenset(
    {"的", "了", "我", "你", "他", "她", "它", "是", "吗", "在", "和", "就", "都", "也", "很"}
)


def _tokenize(text: str) -> str:
    """jieba 预分词；FTS unicode61 以空格识别中文 token。"""
    return " ".join(
        token.strip() for token in jieba.cut(text, cut_all=False) if token.strip()
    )


def _like_pattern(text: str) -> str:
    """LIKE 子串模式：转义 `%` / `_` / `\\`，避免用户输入被当通配符。"""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _fts_query(text: str) -> str:
    """把自然语言 query 变成 FTS5 OR 表达式；中文助词先去掉。"""
    terms = [
        token.strip()
        for token in jieba.cut(text, cut_all=False)
        if token.strip() and token.strip() not in _TURN_QUERY_STOPWORDS
    ]
    if not terms:
        terms = [token.strip() for token in jieba.cut(text, cut_all=False) if token.strip()]
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)


def _turn_from_row(row: sqlite3.Row) -> TurnRow:
    return TurnRow(
        turn_id=_text(row["turn_id"]),
        session_id=_text(row["session_id"]),
        profile_id=_text(row["profile_id"]),
        seq=int(row["seq"]),
        user_text=_text(row["user_text"]),
        assistant_text=_opt_text(row["assistant_text"]),
        tokens=_text(row["tokens"]),
        status=_text(row["status"]),
        fail_reason=_opt_text(row["fail_reason"]),
        voice_id=_opt_text(row["voice_id"]),
        model=_opt_text(row["model"]),
        persona_id=_opt_text(row["persona_id"]),
        latency_ms=None if row["latency_ms"] is None else int(row["latency_ms"]),
        started_at=_num(row["started_at"]),
        ended_at=_opt_num(row["ended_at"]),
        superseded_by=_opt_text(row["superseded_by"]),
        grounding_score=(
            None if row["grounding_score"] is None else float(row["grounding_score"])
        ),
        grounding_verdict=_opt_text(row["grounding_verdict"]),
        grounding_claims=_opt_text(row["grounding_claims"]),
        grounding_checked_at=_opt_num(row["grounding_checked_at"]),
        emotion=_opt_text(row["emotion"]),
    )


class TurnRepo:
    """原文层（R1a）：两段式写入 + 会话内 seq + FTS 检索。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def next_seq(self, session_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 FROM turn WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row[0])

    def insert(
        self,
        *,
        session_id: str,
        user_text: str,
        now: float,
        profile_id: str = "default",
        voice_id: str | None = None,
        model: str | None = None,
        persona_id: str | None = None,
        turn_id: str | None = None,
    ) -> TurnRow:
        """turn 开始：pending + 原文先落盘；seq 在同事务内分配。"""
        new_id = turn_id or f"turn_{uuid4().hex}"
        tokens = _tokenize(user_text)
        with _guard(self._conn, "写入 turn"):
            self._conn.execute("BEGIN IMMEDIATE")
            seq = self.next_seq(session_id)
            self._conn.execute(
                "INSERT INTO turn"
                " (turn_id, session_id, profile_id, seq, user_text, assistant_text,"
                "  tokens, status, voice_id, model, persona_id, started_at)"
                " VALUES (?, ?, ?, ?, ?, NULL, ?, 'pending', ?, ?, ?, ?)",
                (
                    new_id,
                    session_id,
                    profile_id,
                    seq,
                    user_text,
                    tokens,
                    voice_id,
                    model,
                    persona_id,
                    now,
                ),
            )
            self._conn.commit()
        return TurnRow(
            turn_id=new_id,
            session_id=session_id,
            profile_id=profile_id,
            seq=seq,
            user_text=user_text,
            assistant_text=None,
            tokens=tokens,
            status="pending",
            fail_reason=None,
            voice_id=voice_id,
            model=model,
            persona_id=persona_id,
            latency_ms=None,
            started_at=now,
            ended_at=None,
            superseded_by=None,
        )

    def finish(
        self,
        turn_id: str,
        *,
        assistant_text: str | None,
        status: str,
        now: float,
        latency_ms: int | None = None,
        fail_reason: str | None = None,
        emotion: str | None = None,
    ) -> None:
        """收尾：终态 + assistant_text + tokens 重算；必须先于 turn_complete。"""
        if status not in {"complete", "cancelled", "failed"}:
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"非法 turn 终态：{status!r}")
        with _guard(self._conn, "收尾 turn"):
            current = self.get(turn_id)
            if current is None:
                raise EchoesError(ErrorCode.STORAGE_ERROR, f"turn 不存在：{turn_id}")
            combined = current.user_text
            if assistant_text:
                combined = f"{combined}\n{assistant_text}"
            tokens = _tokenize(combined)
            cursor = self._conn.execute(
                "UPDATE turn SET assistant_text = ?, tokens = ?, status = ?,"
                " fail_reason = ?, latency_ms = ?, ended_at = ?, emotion = ?"
                " WHERE turn_id = ?",
                (
                    assistant_text,
                    tokens,
                    status,
                    fail_reason,
                    latency_ms,
                    now,
                    emotion,
                    turn_id,
                ),
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"turn 不存在：{turn_id}")

    def last_finished(self, session_id: str) -> TurnRow | None:
        """会话里最近一条未被取代的已收尾 turn（重说/编辑定位用）。"""
        row = self._conn.execute(
            f"SELECT {_TURN_COLUMNS} FROM turn"
            " WHERE session_id = ? AND status IN ('complete', 'cancelled', 'failed')"
            "   AND superseded_by IS NULL"
            " ORDER BY seq DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return None if row is None else _turn_from_row(row)

    def supersede(self, old_turn_id: str, new_turn_id: str) -> None:
        """append-only 重说/编辑：旧 turn 指向新 turn（列表/检索默认排除）。"""
        with _guard(self._conn, "标记重说"):
            cursor = self._conn.execute(
                "UPDATE turn SET superseded_by = ?"
                " WHERE turn_id = ? AND superseded_by IS NULL",
                (new_turn_id, old_turn_id),
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise EchoesError(
                ErrorCode.STORAGE_ERROR, f"turn {old_turn_id} 不存在或已被取代"
            )

    def set_grounding(
        self,
        turn_id: str,
        *,
        score: float,
        verdict: str,
        claims: list[str],
        now: float,
    ) -> None:
        """写入异步质检结果（R4 4.3）；不改变 turn 状态，失败由调用方兜底。"""
        if verdict not in {"faithful", "unfaithful"}:
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"未知质检结论 {verdict!r}")
        payload = json.dumps(claims, ensure_ascii=False)
        with _guard(self._conn, "写入质检结果"):
            cursor = self._conn.execute(
                "UPDATE turn SET grounding_score = ?, grounding_verdict = ?,"
                " grounding_claims = ?, grounding_checked_at = ? WHERE turn_id = ?",
                (max(0.0, min(1.0, score)), verdict, payload, now, turn_id),
            )
            self._conn.commit()
        if cursor.rowcount == 0:
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"turn 不存在：{turn_id}")

    def get(self, turn_id: str) -> TurnRow | None:
        row = self._conn.execute(
            f"SELECT {_TURN_COLUMNS} FROM turn WHERE turn_id = ?",            (turn_id,),
        ).fetchone()
        return None if row is None else _turn_from_row(row)

    def recent(self, session_id: str, *, limit: int = 12) -> list[TurnRow]:
        """prompt 窗口：最近 N 轮，按 seq 升序返回。"""
        if limit <= 0:
            return []
        rows = self._conn.execute(
            f"SELECT {_TURN_COLUMNS} FROM turn"
            " WHERE session_id = ? AND status IN ('complete', 'cancelled')"
            "   AND superseded_by IS NULL"
            " ORDER BY seq DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [_turn_from_row(row) for row in reversed(rows)]

    def list_session(
        self,
        session_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        include_superseded: bool = False,
    ) -> list[TurnRow]:
        """历史列表：默认排除 superseded/pending，按 seq 倒序。"""
        where = [
            "session_id = ?",
            "status IN ('complete', 'cancelled', 'failed')",
        ]
        params: list[Any] = [session_id]
        if not include_superseded:
            where.append("superseded_by IS NULL")
        rows = self._conn.execute(
            f"SELECT {_TURN_COLUMNS} FROM turn WHERE {' AND '.join(where)}"
            " ORDER BY seq DESC LIMIT ? OFFSET ?",
            (*params, max(0, limit), max(0, offset)),
        ).fetchall()
        return [_turn_from_row(row) for row in rows]

    def search(
        self,
        query: str,
        *,
        session_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
        include_superseded: bool = False,
    ) -> list[TurnRow]:
        """历史全文搜索；FTS 查询为空时返回空。"""
        match = _fts_query(query)
        if not match or limit <= 0:
            return []
        where = [
            "turn_fts MATCH ?",
            "t.status IN ('complete', 'cancelled', 'failed')",
        ]
        params: list[Any] = [match]
        if session_id is not None:
            where.append("t.session_id = ?")
            params.append(session_id)
        if not include_superseded:
            where.append("t.superseded_by IS NULL")
        rows = self._conn.execute(
            f"SELECT {', '.join('t.' + column.strip() for column in _TURN_COLUMNS.split(','))}"
            " FROM turn_fts JOIN turn AS t ON t.rowid = turn_fts.rowid"
            f" WHERE {' AND '.join(where)}"
            " ORDER BY bm25(turn_fts), t.seq DESC LIMIT ? OFFSET ?",
            (*params, limit, max(0, offset)),
        ).fetchall()
        return [_turn_from_row(row) for row in rows]

    def link_memory(
        self, turn_id: str, fact_ids: list[str], *, weight: float | None = None
    ) -> None:
        """记录「本轮注入了哪些事实」（R3a 3.8 来源回溯）。

        幂等：同一 (turn_id, fact_id) 重复写只更新 weight。空列表直接返回。
        """
        ids = [fact_id for fact_id in fact_ids if fact_id]
        if not ids:
            return
        with _guard(self._conn, "记录记忆来源"):
            self._conn.executemany(
                "INSERT OR REPLACE INTO turn_memory_ref (turn_id, fact_id, weight)"
                " VALUES (?, ?, ?)",
                [(turn_id, fact_id, weight) for fact_id in ids],
            )
            self._conn.commit()

    def memory_refs(self, turn_id: str) -> list[str]:
        """本轮注入过的事实 id（来源回溯读接口）。"""
        rows = self._conn.execute(
            "SELECT fact_id FROM turn_memory_ref WHERE turn_id = ? ORDER BY fact_id",
            (turn_id,),
        ).fetchall()
        return [str(row[0]) for row in rows]

    def turns_for_fact(self, fact_id: str, *, limit: int = 20) -> list[str]:
        """反查「这条记忆被哪些回复用过」。"""
        rows = self._conn.execute(
            "SELECT turn_id FROM turn_memory_ref WHERE fact_id = ?"
            " ORDER BY rowid DESC LIMIT ?",
            (fact_id, max(0, limit)),
        ).fetchall()
        return [str(row[0]) for row in rows]

    def unsummarized(
        self, session_id: str, *, after_seq: int, limit: int = 50
    ) -> list[TurnRow]:
        """摘要补偿：从 DB 取 seq > after_seq 的 complete 轮次（升序）。"""
        if limit <= 0:
            return []
        rows = self._conn.execute(
            f"SELECT {_TURN_COLUMNS} FROM turn"
            " WHERE session_id = ? AND status = 'complete'"
            "   AND superseded_by IS NULL AND seq > ?"
            " ORDER BY seq ASC LIMIT ?",
            (session_id, after_seq, limit),
        ).fetchall()
        return [_turn_from_row(row) for row in rows]

    def cleanup_pending(self, *, now: float) -> int:
        """启动清洗：崩溃残留的 pending 统一置 failed。"""
        with _guard(self._conn, "清洗 pending turn"):
            cursor = self._conn.execute(
                "UPDATE turn SET status = 'failed', fail_reason = 'crash_cleanup',"
                " ended_at = ? WHERE status = 'pending'",
                (now,),
            )
            self._conn.commit()
        return int(cursor.rowcount)


class SettingRepo:
    """键值设置（5.1 setting）：value 为 JSON 编码（provider / 嵌入档位 / 隐私模式）。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, key: str) -> object | None:
        row = self._conn.execute("SELECT value FROM setting WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        raw = _text(row["value"])
        try:
            parsed: object = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise EchoesError(
                ErrorCode.STORAGE_ERROR, f"setting[{key}] 不是合法 JSON：{raw!r}"
            ) from exc
        return parsed

    def set(self, key: str, value: object) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        with _guard(self._conn, "写入设置"):
            self._conn.execute(
                "INSERT INTO setting (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, payload),
            )
            self._conn.commit()


@dataclass(frozen=True)
class Storage:
    """存储门面：连接 + 六个仓储（组合根持有单例，随进程生命周期）。"""

    conn: sqlite3.Connection
    personas: PersonaRepo
    voices: VoiceRepo
    sessions: SessionRepo
    turns: TurnRepo
    settings: SettingRepo
    memories: MemoryRepo
    chunks: ChunkRepo

    @classmethod
    def open(cls, db_file: Path, *, migrations_dir: Path | None = None) -> Storage:
        conn = connect(db_file, migrations_dir=migrations_dir)
        return cls(
            conn=conn,
            personas=PersonaRepo(conn),
            voices=VoiceRepo(conn),
            sessions=SessionRepo(conn),
            turns=TurnRepo(conn),
            settings=SettingRepo(conn),
            memories=MemoryRepo(conn),
            chunks=ChunkRepo(conn),
        )

    def close(self) -> None:
        self.conn.close()
