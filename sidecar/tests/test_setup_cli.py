"""R5 setup CLI 接线：data-export / data-import / models-info 的 JSON 行契约。"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from echoes_sidecar import setup_cli
from echoes_sidecar.db import Storage


def _last_json(capsys: pytest.CaptureFixture[str]) -> dict:
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert lines, "CLI 没有输出"
    return json.loads(lines[-1])


def _seed(root: Path) -> None:
    store = Storage.open(root / "db" / "echoes.db")
    try:
        now = time.time()
        persona = store.personas.sync(
            persona_id="default", name="默认人设", system_prompt="s", now=now
        )
        store.sessions.create(session_id="s1", persona_id=persona.id, now=now)
        turn = store.turns.insert(session_id="s1", user_text="导出我", now=now)
        store.turns.finish(
            turn.turn_id, assistant_text="好", status="complete", now=now + 1
        )
    finally:
        store.close()


def test_cli_data_export_then_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "data"
    monkeypatch.setenv("ECHOES_DATA_DIR", str(source))
    _seed(source)
    bundle = tmp_path / "bundle.json"

    assert setup_cli.main(["data-export", "--path", str(bundle)]) == 0
    exported = _last_json(capsys)
    assert exported["type"] == "result"
    assert exported["turns"] == 1
    assert bundle.is_file()

    target = tmp_path / "data2"
    monkeypatch.setenv("ECHOES_DATA_DIR", str(target))
    assert setup_cli.main(["data-import", "--path", str(bundle)]) == 0
    imported = _last_json(capsys)
    assert imported["type"] == "result"
    assert imported["turns"] == 1

    store = Storage.open(target / "db" / "echoes.db")
    try:
        assert store.turns.last_finished("s1") is not None
    finally:
        store.close()


def test_cli_data_import_reports_bad_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ECHOES_DATA_DIR", str(tmp_path / "data"))
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")

    assert setup_cli.main(["data-import", "--path", str(bad)]) == 1
    payload = _last_json(capsys)
    assert payload["type"] == "error"
    assert "format" in payload["message"]


def test_cli_models_info_lists_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ECHOES_MODELS_DIR", str(tmp_path / "models"))

    assert setup_cli.main(["models-info"]) == 0
    payload = _last_json(capsys)
    ids = {row["id"] for row in payload["models"]}
    assert {"bge-small-zh-v1.5", "faster-whisper-tiny", "qwen3-8b"} <= ids
    assert all("bytes" in row and "installed" in row for row in payload["models"])
