"""最小 CRUD（母文档 5.1/14.2）：persona / voice / session / setting。

边界（15.2 依赖分层）：db 只依赖 core，**不 import session 聚合**——返回行对象，
由组合根映射成 `Session`（4.6 聚合归 session 层，反向依赖会破分层）。

事务边界（14.2）：单条状态变更 = 一个事务；写操作由上层串行（单写者）。
全部错误映射 `STORAGE_ERROR`（3.4.1 报错而非降级）。
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import Persona, VoiceStatus
from echoes_sidecar.db.connection import connect


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
    """5.1 voice 表行（资产路径仅作 ID 的附带元数据，3.2 资产用 ID 引用）。"""

    id: str
    display_name: str
    sample_path: str
    model_path: str | None
    status: VoiceStatus
    quality_score: float | None
    created_at: float


@dataclass(frozen=True)
class SessionRow:
    """5.1 session 表行；组合根据此重建 Session（14.1 v1.4 重启语义）。"""

    id: str
    profile_id: str
    persona_id: str
    voice_id: str | None
    started_at: float
    last_active_at: float


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

    _COLUMNS = "id, display_name, sample_path, model_path, status, quality_score, created_at"

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
        sample_path=_text(row["sample_path"]),
        model_path=_opt_text(row["model_path"]),
        status=_voice_status(row["status"]),
        quality_score=_opt_num(row["quality_score"]),
        created_at=_num(row["created_at"]),
    )


class SessionRepo:
    """会话行（5.1）：阶段 0 单会话，但路径按 id 查找写（4.6 远程复用）。"""

    _COLUMNS = "id, profile_id, persona_id, voice_id, started_at, last_active_at"

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, session_id: str) -> SessionRow | None:
        row = self._conn.execute(
            f"SELECT {self._COLUMNS} FROM session WHERE id = ?",  # 列名为模块常量，无注入面
            (session_id,),
        ).fetchone()
        return None if row is None else _session_from_row(row)

    def latest(self) -> SessionRow | None:
        """14.1 v1.4：重启后依「最近活跃」session 重建（沿用原 session_id）。"""
        row = self._conn.execute(
            f"SELECT {self._COLUMNS} FROM session"
            " ORDER BY last_active_at DESC LIMIT 1"
        ).fetchone()
        return None if row is None else _session_from_row(row)

    def create(
        self,
        *,
        session_id: str,
        persona_id: str,
        profile_id: str = "default",
        voice_id: str | None = None,
        now: float,
    ) -> SessionRow:
        with _guard(self._conn, "创建会话"):
            self._conn.execute(
                "INSERT INTO session"
                " (id, profile_id, persona_id, voice_id, started_at, last_active_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, profile_id, persona_id, voice_id, now, now),
            )
            self._conn.commit()
        return SessionRow(
            id=session_id,
            profile_id=profile_id,
            persona_id=persona_id,
            voice_id=voice_id,
            started_at=now,
            last_active_at=now,
        )

    def touch(self, session_id: str, *, now: float) -> None:
        """turn 收尾打点（不落轮次明细——5.1「轮次明细不落库」）。"""
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


def _session_from_row(row: sqlite3.Row) -> SessionRow:
    return SessionRow(
        id=_text(row["id"]),
        profile_id=_text(row["profile_id"]),
        persona_id=_text(row["persona_id"]),
        voice_id=_opt_text(row["voice_id"]),
        started_at=_num(row["started_at"]),
        last_active_at=_num(row["last_active_at"]),
    )


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
    """存储门面：连接 + 四个仓储（组合根持有单例，随进程生命周期）。"""

    conn: sqlite3.Connection
    personas: PersonaRepo
    voices: VoiceRepo
    sessions: SessionRepo
    settings: SettingRepo

    @classmethod
    def open(cls, db_file: Path, *, migrations_dir: Path | None = None) -> Storage:
        conn = connect(db_file, migrations_dir=migrations_dir)
        return cls(
            conn=conn,
            personas=PersonaRepo(conn),
            voices=VoiceRepo(conn),
            sessions=SessionRepo(conn),
            settings=SettingRepo(conn),
        )

    def close(self) -> None:
        self.conn.close()
