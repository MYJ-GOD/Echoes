"""R1c：按 id 重建 Session（切换会话的 sidecar 入口）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError
from echoes_sidecar.db.repo import Storage
from echoes_sidecar.main import _load_session, _open_session


def test_load_session_by_id_preserves_persona_and_voice(tmp_path: Path) -> None:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    try:
        persona = storage.personas.sync(
            persona_id="default", name="默认人设", system_prompt="s", now=1.0
        )
        storage.voices.insert_training(
            voice_id="v1", display_name="音色", sample_path="v1.wav", now=2.0
        )
        storage.sessions.create(
            session_id="s2",
            persona_id=persona.id,
            voice_id="v1",
            title="第二个会话",
            now=3.0,
        )
        loaded = _load_session(storage, "s2", now=4.0)
        assert loaded.session_id == "s2"
        assert loaded.persona.id == "default"
        assert loaded.voice_id == "v1"
        assert loaded.created_at == 3.0
    finally:
        storage.close()


def test_load_missing_session_is_explicit(tmp_path: Path) -> None:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    try:
        with pytest.raises(EchoesError):
            _load_session(storage, "ghost", now=1.0)
    finally:
        storage.close()


def test_open_session_skips_archived_default(tmp_path: Path) -> None:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    try:
        storage.personas.sync(
            persona_id="default", name="默认人设", system_prompt="s", now=1.0
        )
        storage.sessions.create(session_id="default", persona_id="default", now=1.0)
        storage.conn.execute(
            "UPDATE session SET archived_at = 2.0 WHERE id = 'default'"
        )
        storage.conn.commit()
        opened = _open_session(storage, now=3.0)
        assert opened.session_id != "default"
        assert storage.sessions.get("default") is not None
        assert storage.sessions.get("default").archived_at == 2.0  # type: ignore[union-attr]
    finally:
        storage.close()
