"""R5 模型管理：占用统计与删除只落在清单 target 目录内。"""

from __future__ import annotations

from pathlib import Path

import pytest

from echoes_sidecar import setup
from echoes_sidecar.core.errors import EchoesError
from echoes_sidecar.models.manager import load_manifest


def _install_fake(root: Path, model_id: str) -> Path:
    entry = next(item for item in load_manifest() if item.id == model_id)
    target = root / entry.target
    target.mkdir(parents=True)
    for name in entry.required_files:
        (target / name).write_bytes(b"x" * 8)
    return target


def test_models_info_reports_installed_and_bytes(tmp_path: Path) -> None:
    target = _install_fake(tmp_path, "faster-whisper-tiny")

    rows = {row["id"]: row for row in setup.models_info(models_root=tmp_path)}
    tiny = rows["faster-whisper-tiny"]
    assert tiny["installed"] is True
    assert tiny["bytes"] == 8 * len(
        next(item for item in load_manifest() if item.id == "faster-whisper-tiny").required_files
    )
    assert tiny["path"] == str(target)
    assert rows["faster-whisper-base"]["installed"] is False
    assert rows["faster-whisper-base"]["bytes"] == 0


def test_remove_models_deletes_only_that_target(tmp_path: Path) -> None:
    tiny = _install_fake(tmp_path, "faster-whisper-tiny")
    base = _install_fake(tmp_path, "faster-whisper-base")

    result = setup.remove_models(["faster-whisper-tiny"], models_root=tmp_path)

    assert result["removed"] == ["faster-whisper-tiny"]
    assert result["freedBytes"] > 0
    assert not tiny.exists()
    assert base.exists()


def test_remove_models_refuses_ollama_and_unknown(tmp_path: Path) -> None:
    with pytest.raises(EchoesError) as err:
        setup.remove_models(["qwen3-8b"], models_root=tmp_path)
    assert "ollama" in err.value.message.lower()

    with pytest.raises(EchoesError):
        setup.remove_models(["not-a-model"], models_root=tmp_path)

    with pytest.raises(EchoesError):
        setup.remove_models([], models_root=tmp_path)
