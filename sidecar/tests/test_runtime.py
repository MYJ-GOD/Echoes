"""ADR-011 运行时包：清单、档位选择、注入、档案安装（zip-slip/原子/校验）。"""
from __future__ import annotations

import hashlib
import json
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

from echoes_sidecar import runtime

CORE_DEPS = {"pydantic", "websockets", "httpx", "sqlite-vec"}


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个用例独占 sys.path 与注入标记；env 不串味。"""
    before = list(sys.path)
    runtime._INJECTED.clear()
    for name in (runtime.ENV_PROFILE, runtime.ENV_RUNTIME_DIR, runtime.ENV_FORCE):
        monkeypatch.delenv(name, raising=False)
    yield
    sys.path[:] = before
    runtime._INJECTED.clear()
    sys.modules.pop("demo_runtime_pkg", None)


def _write_runtime(
    root: Path, profile: str, *, python: str = "3.13", installed_at: str = "2026-01-01"
) -> Path:
    """手搓一份已安装档位（不走 zip，专测发现/选择逻辑）。"""
    directory = root / profile
    site = directory / "site-packages"
    site.mkdir(parents=True)
    (site / "demo_runtime_pkg").mkdir()
    (site / "demo_runtime_pkg" / "__init__.py").write_text("VALUE = 42\n")
    (directory / "runtime.json").write_text(
        json.dumps(
            {
                "version": 1,
                "profile": profile,
                "python": python,
                "platform": "win_amd64",
                "installed_at": installed_at,
                "site-packages": "site-packages",
            }
        ),
        encoding="utf-8",
    )
    return directory


def _zip(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)
    return path


def _dep_name(requirement: str) -> str:
    head = requirement.split(";")[0]
    for sep in ("[", "=", "<", ">", "!", "~", " "):
        head = head.split(sep)[0]
    return head.strip().lower().replace("_", "-")


# ------------------------------ 清单 ------------------------------


def test_default_manifest_has_cpu_and_cuda_profiles() -> None:
    specs = runtime.load_specs()
    assert {"cpu", "cuda126"} <= set(specs)
    for spec in specs.values():
        assert spec.python and spec.platform
        assert spec.index_url.startswith("https://download.pytorch.org/whl/")
        assert "torch" in spec.verified_modules
        assert any(req.startswith("torch==") for req in spec.requirements)


def test_manifest_covers_pyproject_ml_deps() -> None:
    """清单漂移守卫：pyproject 里的重依赖必须出现在每个档位的 requirements。"""
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    deps = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["dependencies"]
    heavy = {dep for dep in deps if _dep_name(dep) not in CORE_DEPS}
    for profile, spec in runtime.load_specs().items():
        listed = {_dep_name(req) for req in spec.requirements}
        missing = {dep for dep in heavy if _dep_name(dep) not in listed}
        assert not missing, f"{profile} 缺依赖：{sorted(missing)}"


def test_unpublished_bundle_is_allowed() -> None:
    # 发布地址可以留空：CLI 会给出 --from-bundle 指引，而不是启动即崩
    specs = runtime.load_specs()
    assert all(source.url == "" for spec in specs.values() for source in spec.bundles)


# ------------------------------ 档位选择 ------------------------------


def test_active_layout_is_none_for_empty_root(tmp_path: Path) -> None:
    assert runtime.active_layout(tmp_path) is None
    assert runtime.installed_profiles(tmp_path) == []


def test_active_layout_uses_single_profile(tmp_path: Path) -> None:
    _write_runtime(tmp_path, "cpu")
    layout = runtime.active_layout(tmp_path)
    assert layout is not None
    assert layout.profile == "cpu"
    assert layout.site_packages == tmp_path / "cpu" / "site-packages"


def test_active_pointer_beats_newest(tmp_path: Path) -> None:
    _write_runtime(tmp_path, "cpu", installed_at="2026-01-01")
    _write_runtime(tmp_path, "cuda126", installed_at="2026-09-09")
    (tmp_path / runtime.ACTIVE_FILE).write_text("cpu\n", encoding="utf-8")
    assert runtime.active_profile(tmp_path) == "cpu"


def test_env_profile_beats_pointer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_runtime(tmp_path, "cpu")
    _write_runtime(tmp_path, "cuda126")
    (tmp_path / runtime.ACTIVE_FILE).write_text("cuda126\n", encoding="utf-8")
    monkeypatch.setenv(runtime.ENV_PROFILE, "cpu")
    assert runtime.active_profile(tmp_path) == "cpu"


def test_broken_manifest_is_ignored(tmp_path: Path) -> None:
    broken = tmp_path / "cpu"
    broken.mkdir()
    (broken / runtime.MANIFEST_FILE).write_text("{not json", encoding="utf-8")
    assert runtime.active_layout(tmp_path) is None


# ------------------------------ 注入 ------------------------------


def test_inject_noop_without_runtime(tmp_path: Path) -> None:
    before = list(sys.path)
    assert runtime.inject(root=tmp_path, force=True) is None
    assert sys.path == before


def test_inject_puts_site_packages_first_and_imports(tmp_path: Path) -> None:
    _write_runtime(tmp_path, "cpu")
    layout = runtime.inject(root=tmp_path, force=True)
    assert layout is not None
    assert sys.path[0] == str(tmp_path / "cpu" / "site-packages")

    import demo_runtime_pkg

    assert demo_runtime_pkg.VALUE == 42


def test_inject_is_idempotent(tmp_path: Path) -> None:
    _write_runtime(tmp_path, "cpu")
    site = str(tmp_path / "cpu" / "site-packages")
    runtime.inject(root=tmp_path, force=True)
    runtime.inject(root=tmp_path, force=True)
    assert sys.path.count(site) == 1


def test_inject_skips_python_mismatch(tmp_path: Path) -> None:
    _write_runtime(tmp_path, "cpu", python="2.7")
    assert runtime.inject(root=tmp_path, force=True) is None
    assert str(tmp_path / "cpu" / "site-packages") not in sys.path


def test_inject_respects_frozen_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_runtime(tmp_path, "cpu")
    # 非冻结 + 无 env：dev 形态不注入（.venv 才是依赖源）
    assert runtime.inject(root=tmp_path) is None
    monkeypatch.setenv(runtime.ENV_FORCE, "1")
    assert runtime.inject(root=tmp_path) is not None


# ------------------------------ 安装 ------------------------------


def test_install_standard_zip_activates(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    archive = _zip(
        tmp_path / "cpu.zip",
        {
            "site-packages/demo_runtime_pkg/__init__.py": "VALUE = 7\n",
            "site-packages/demo_runtime_pkg/data.txt": "payload",
        },
    )
    layout = runtime.install_bundle(archive, "cpu", root=root)

    assert layout.profile == "cpu"
    assert (layout.site_packages / "demo_runtime_pkg" / "data.txt").read_text() == "payload"
    assert (root / runtime.ACTIVE_FILE).read_text(encoding="utf-8").strip() == "cpu"
    manifest = json.loads((root / "cpu" / runtime.MANIFEST_FILE).read_text(encoding="utf-8"))
    assert manifest["profile"] == "cpu"
    assert manifest["bundle_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert not (root / ".staging").exists() or not any((root / ".staging").iterdir())


def test_install_flat_zip_is_normalized(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    archive = _zip(
        tmp_path / "flat.zip",
        {"demo_runtime_pkg/__init__.py": "VALUE = 1\n"},
    )
    layout = runtime.install_bundle(archive, "cpu", root=root)
    assert (layout.site_packages / "demo_runtime_pkg" / "__init__.py").is_file()
    assert runtime.inject(root=root, force=True) is not None


def test_install_rejects_zip_slip(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    archive = _zip(
        tmp_path / "evil.zip",
        {"site-packages/ok.txt": "ok", "../escaped.txt": "boom"},
    )
    with pytest.raises(ValueError, match="越界路径"):
        runtime.install_bundle(archive, "cpu", root=root)
    assert not (tmp_path / "escaped.txt").exists()
    assert not (root / "cpu").exists()


def test_install_refuses_existing_without_force(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    first = _zip(tmp_path / "a.zip", {"site-packages/demo_runtime_pkg/__init__.py": "V=1\n"})
    runtime.install_bundle(first, "cpu", root=root)

    second = _zip(tmp_path / "b.zip", {"site-packages/demo_runtime_pkg/__init__.py": "V=2\n"})
    with pytest.raises(FileExistsError):
        runtime.install_bundle(second, "cpu", root=root)
    installed = (root / "cpu" / "site-packages" / "demo_runtime_pkg" / "__init__.py").read_text()
    assert installed == "V=1\n"


def test_install_sha_mismatch_keeps_old(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    first = _zip(tmp_path / "a.zip", {"site-packages/demo_runtime_pkg/__init__.py": "V=1\n"})
    runtime.install_bundle(first, "cpu", root=root)

    second = _zip(tmp_path / "b.zip", {"site-packages/demo_runtime_pkg/__init__.py": "V=2\n"})
    with pytest.raises(ValueError, match="sha256"):
        runtime.install_bundle(
            second, "cpu", root=root, force=True, expected_sha256="0" * 64
        )
    installed = (root / "cpu" / "site-packages" / "demo_runtime_pkg" / "__init__.py").read_text()
    assert installed == "V=1\n"


def test_install_missing_archive(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        runtime.install_bundle(tmp_path / "nope.zip", "cpu", root=tmp_path / "runtime")


def test_install_writes_manifest_from_spec(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    archive = _zip(tmp_path / "c.zip", {"site-packages/demo_runtime_pkg/__init__.py": "V=1\n"})
    spec = runtime.load_specs()["cuda126"]
    layout = runtime.install_bundle(archive, "cuda126", root=root, spec=spec)
    assert layout.installed.python == spec.python
    assert layout.installed.platform == spec.platform
