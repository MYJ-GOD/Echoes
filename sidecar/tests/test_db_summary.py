"""session_summary 仓储（5.1/5.2）：读、写、upsert、空摘要拒绝。"""

from __future__ import annotations

from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db.repo import Storage


def _open(tmp_path: Path) -> Storage:
    return Storage.open(tmp_path / "db" / "echoes.db")


def _session(storage: Storage) -> None:
    storage.personas.sync(
        persona_id="default", name="默认人设", system_prompt="s", now=1.0
    )
    storage.sessions.create(session_id="s1", persona_id="default", now=1.0)


def test_summary_roundtrip_and_upsert(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        _session(storage)
        assert storage.sessions.get_summary("s1") is None

        first = storage.sessions.save_summary(
            "s1", summary="  用户喜欢猫  ", up_to_turn=10, now=2.0
        )
        assert first.session_id == "s1"
        assert first.summary == "用户喜欢猫"
        assert first.up_to_turn == 10
        assert storage.sessions.get_summary("s1") == first

        second = storage.sessions.save_summary(
            "s1", summary="用户搬到上海", up_to_turn=20, now=3.0
        )
        assert storage.sessions.get_summary("s1") == second
        count = storage.conn.execute("SELECT COUNT(*) FROM session_summary").fetchone()[0]
        assert int(count) == 1  # upsert 不新增行
    finally:
        storage.close()


def test_empty_summary_is_rejected(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        _session(storage)
        with pytest.raises(EchoesError) as exc_info:
            storage.sessions.save_summary(
                "s1", summary="   ", up_to_turn=1, now=2.0
            )
        assert exc_info.value.code is ErrorCode.STORAGE_ERROR
        assert storage.sessions.get_summary("s1") is None
    finally:
        storage.close()


def test_summary_requires_existing_session(tmp_path: Path) -> None:
    storage = _open(tmp_path)
    try:
        with pytest.raises(EchoesError) as exc_info:
            storage.sessions.save_summary(
                "ghost", summary="用户喜欢猫", up_to_turn=1, now=2.0
            )
        assert exc_info.value.code is ErrorCode.STORAGE_ERROR
    finally:
        storage.close()
