"""首启向导后端（ADR-011/016）：推荐档位、缺失清单、下载量、安装分支。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from echoes_sidecar import runtime, setup
from echoes_sidecar.core.errors import EchoesError, ErrorCode


@pytest.fixture(autouse=True)
def _fake_hardware(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认一台「无独显、源码 venv」的机器；单个用例再覆盖。"""
    monkeypatch.setattr(setup, "_cpu_name", lambda: "Test CPU")
    monkeypatch.setattr(setup, "_ram_gb", lambda: 16.0)
    monkeypatch.setattr(setup, "_gpu_probe", lambda: None)
    monkeypatch.setattr(setup, "_disk_free_gb", lambda: 200.0)
    monkeypatch.setattr(setup, "_dev_venv", lambda: False)
    monkeypatch.setattr(
        setup,
        "_ollama_probe",
        lambda: setup.OllamaInfo(url="http://127.0.0.1:11434", reachable=False),
    )


def _report(tmp_path: Path, **kwargs: object) -> setup.SetupReport:
    return setup.detect(
        models_root=tmp_path / "models",
        runtime_root=tmp_path / "runtime",
        **kwargs,  # type: ignore[arg-type]
    )


def test_cpu_machine_needs_runtime_and_all_models(tmp_path: Path) -> None:
    report = _report(tmp_path)
    assert report.recommended_profile == "cpu"
    assert report.needs_runtime is True
    assert report.dev_venv is False
    assert report.missing_models == setup.REQUIRED_MODELS
    # whisper 461 + bge 95 + cosyvoice 3800 + cpu 档位 1200
    assert report.download_mb >= 5500
    assert report.runtime_archive_ready is False
    assert any("未发布" in note for note in report.notes)


def test_cuda_recommendation_by_vram(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup, "_gpu_probe", lambda: setup.GpuInfo("RTX 3060", 12.0))
    report = _report(tmp_path)
    assert report.recommended_profile == "cuda126"
    assert report.gpu is not None and report.gpu.name == "RTX 3060"


def test_small_vram_stays_on_cpu(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup, "_gpu_probe", lambda: setup.GpuInfo("GTX 1050", 4.0))
    assert _report(tmp_path).recommended_profile == "cpu"


def test_dev_venv_skips_runtime_and_keeps_models(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(setup, "_dev_venv", lambda: True)
    report = _report(tmp_path)
    assert report.needs_runtime is False
    assert report.dev_venv is True
    # 省掉 1200MB 运行时段位，只剩三个权重
    assert report.download_mb == pytest.approx(461 + 95 + 3800, abs=1)


def test_installed_runtime_is_detected(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    directory = root / "cpu"
    (directory / "site-packages").mkdir(parents=True)
    (directory / "runtime.json").write_text(
        json.dumps(
            {
                "profile": "cpu",
                "python": "3.13",
                "platform": "win_amd64",
                "installed_at": "2026-01-01",
                "site-packages": "site-packages",
            }
        ),
        encoding="utf-8",
    )

    report = _report(tmp_path)
    assert report.active_profile == "cpu"
    assert report.runtime_profiles == ("cpu",)
    assert report.needs_runtime is False
    assert report.download_mb == pytest.approx(461 + 95 + 3800, abs=1)


def test_install_runtime_without_published_archive_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(EchoesError) as excinfo:
        setup.install_runtime("cpu", runtime_root=tmp_path / "runtime")
    assert excinfo.value.code is ErrorCode.MODEL_NOT_LOADED
    assert "未发布" in excinfo.value.message


def test_install_runtime_unknown_profile(tmp_path: Path) -> None:
    with pytest.raises(EchoesError) as excinfo:
        setup.install_runtime("gpu99", runtime_root=tmp_path / "runtime")
    assert "未知运行时档位" in excinfo.value.message


def test_models_already_installed_are_not_downloaded(tmp_path: Path) -> None:
    models = tmp_path / "models"
    # 按 manifest 的 required_files 造出「已安装」的最小形状
    whisper = models / "faster-whisper-small"
    whisper.mkdir(parents=True)
    for name in ("config.json", "model.bin", "tokenizer.json"):
        (whisper / name).write_text("{}", encoding="utf-8")

    calls: list[tuple[str, int]] = []
    result = setup.install_models(
        ["faster-whisper-small"],
        models_root=models,
        progress=lambda item, pct: calls.append((item, pct)),
    )
    assert result == {"faster-whisper-small": "already"}
    assert calls == [("faster-whisper-small", 100)]


def test_unknown_model_id_is_reported_not_raised(tmp_path: Path) -> None:
    result = setup.install_models(["nope"], models_root=tmp_path / "models")
    assert result == {"nope": "未知模型"}


def test_json_line_keeps_chinese_readable() -> None:
    line = setup.json_line({"type": "progress", "item": "音色"})
    assert "音色" in line
    assert json.loads(line)["item"] == "音色"


def test_required_models_exist_in_manifest() -> None:
    ids = {entry.id for entry in setup.ModelManager.load().entries()}
    assert set(setup.REQUIRED_MODELS) <= ids


def test_platform_tag_matches_manifest() -> None:
    """清单的 platform 必须与当前构建机一致，否则向导会推荐一个装不上的档位。"""
    spec = runtime.load_specs()["cpu"]
    assert spec.platform == runtime.platform_tag()
