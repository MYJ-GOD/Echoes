"""ASR 本地档位：按 model size 找对应权重目录（R2a 2.2 / R3b 清单）。"""

from __future__ import annotations

from pathlib import Path

from echoes_sidecar.main import _whisper_model_path
from echoes_sidecar.models.manager import load_manifest


def test_manifest_covers_all_whisper_tiers() -> None:
    manifest = {entry.id: entry for entry in load_manifest()}
    for size in ("tiny", "base", "small"):
        entry = manifest[f"faster-whisper-{size}"]
        assert entry.target == f"faster-whisper-{size}"
        assert "model.bin" in entry.required_files


def test_local_tier_path_matches_manifest_target(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("ECHOES_MODELS_DIR", str(tmp_path))
    assert _whisper_model_path("tiny") is None

    target = tmp_path / "faster-whisper-tiny"
    target.mkdir()
    (target / "model.bin").write_bytes(b"stub")
    assert _whisper_model_path("tiny") == str(target)

    # 档位独立：装 tiny 不等于装 base
    assert _whisper_model_path("base") is None
