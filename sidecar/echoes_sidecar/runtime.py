"""运行时包（ADR-011 split-binary）：发现、注入与安装 torch/CUDA 运行时。

冻结版 sidecar 只带契约链（pydantic/websockets/httpx/sqlite-vec），ML 依赖
（torch/CUDA、transformers、faster-whisper、scipy…）按硬件档位单独下载。运行
时档案是 CI 预构建的 zip（不是运行时 pip 解析），装好后启动时注入 `sys.path`
与 Windows DLL 搜索路径——这样发布版才 import 得到 torch。

目录布局（`~/.cache/echoes/runtime/`，可用 `ECHOES_RUNTIME_DIR` 覆盖）::

    active                      # 当前档位名（纯文本，一行）
    <profile>/runtime.json      # 安装清单（本模块写/读）
    <profile>/site-packages/    # 归档解压出的包

边界（7.3/16.1）：只有安装时联网；运行时不下载，缺件仍由引擎报
`MODEL_NOT_LOADED`。dev 形态不注入（`.venv` 里有全套依赖），除非显式设置
`ECHOES_RUNTIME_INJECT=1`。
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import json
import os
import shutil
import sys
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import url2pathname

import httpx

ENV_RUNTIME_DIR = "ECHOES_RUNTIME_DIR"
ENV_PROFILE = "ECHOES_RUNTIME_PROFILE"
ENV_FORCE = "ECHOES_RUNTIME_INJECT"
ACTIVE_FILE = "active"
MANIFEST_FILE = "runtime.json"
SITE_DIR = "site-packages"
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "runtime_manifest.json"
MANIFEST_VERSION = 1

Progress = Callable[[int], None]

# Windows: `os.add_dll_directory` 返回的句柄一关就失效，必须活到进程结束。
_DLL_HANDLES: list[Any] = []
_INJECTED: set[str] = set()


class _RuntimeFinder:
    """让运行时目录优先于 PyInstaller 的 FrozenImporter。

    `sys.path` 只影响 PathFinder，而 PyInstaller 把模块塞在 PYZ 里、由 meta_path
    最前面的 FrozenImporter 提供——**哪怕只是被静态分析带进来的残缺副本**，也会
    盖住运行时的完整包（实测：包里那份 rich 没有 tree.py，CosyVoice2 直接炸）。
    所以这里插一个 finder：顶层模块先在运行时 site-packages 里找，找不到再落回包内。
    """

    def __init__(self, site: Path) -> None:
        self._site = str(site)

    def find_spec(
        self,
        fullname: str,
        path: Any = None,
        target: Any = None,
    ) -> Any:
        if "." in fullname:  # 子模块交给父包 __path__（已指向运行时目录）
            return None
        return importlib.machinery.PathFinder.find_spec(fullname, [self._site], target)


@dataclass(frozen=True)
class BundleSource:
    """归档来源（多源按顺序尝试；url 为空表示尚未发布）。"""

    url: str
    sha256: str | None = None


@dataclass(frozen=True)
class RuntimeSpec:
    """清单里的一档运行时（CPU / CUDA 变体）。"""

    id: str
    display_name: str
    python: str
    platform: str
    size_mb: float
    requirements: tuple[str, ...]
    index_url: str
    extra_index_url: str
    bundles: tuple[BundleSource, ...]
    verified_modules: tuple[str, ...]


@dataclass(frozen=True)
class InstalledRuntime:
    """落盘清单：`runtime.json` 的强类型视图。"""

    profile: str
    python: str
    platform: str
    installed_at: str
    site_packages: str
    bundle_sha256: str | None = None


@dataclass(frozen=True)
class RuntimeLayout:
    """一次成功解析的运行时（注入与验证共用）。"""

    profile: str
    root: Path
    site_packages: Path
    installed: InstalledRuntime


def default_root() -> Path:
    override = os.environ.get(ENV_RUNTIME_DIR, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "echoes" / "runtime"


def load_specs(path: Path | None = None) -> dict[str, RuntimeSpec]:
    """读运行时清单（随包 JSON，与模型清单同样的校验口径）。"""
    manifest = Path(path) if path is not None else DEFAULT_MANIFEST
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"运行时清单不可读：{manifest}（{exc}）") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"运行时清单不是合法 JSON：{manifest}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("profiles"), dict):
        raise ValueError(f"运行时清单缺 profiles 对象：{manifest}")

    specs: dict[str, RuntimeSpec] = {}
    for profile, item in raw["profiles"].items():
        if not isinstance(item, dict):
            raise ValueError(f"profiles.{profile} 必须是对象")
        bundles = item.get("bundles", [])
        if not isinstance(bundles, list):
            raise ValueError(f"profiles.{profile}.bundles 必须是数组")
        sources: list[BundleSource] = []
        for src in bundles:
            if not isinstance(src, dict) or not isinstance(src.get("url"), str):
                raise ValueError(f"profiles.{profile} 的来源缺 url")
            sha = src.get("sha256")
            sources.append(
                BundleSource(url=src["url"], sha256=sha if isinstance(sha, str) else None)
            )
        modules = item.get("verified_modules", [])
        requirements = item.get("requirements", [])
        if not isinstance(requirements, list):
            raise ValueError(f"profiles.{profile}.requirements 必须是数组")
        specs[profile] = RuntimeSpec(
            id=profile,
            display_name=str(item.get("display_name") or profile),
            python=str(item.get("python") or ""),
            platform=str(item.get("platform") or ""),
            size_mb=float(item.get("size_mb") or 0),
            requirements=tuple(r for r in requirements if isinstance(r, str)),
            index_url=str(item.get("index_url") or ""),
            extra_index_url=str(item.get("extra_index_url") or ""),
            bundles=tuple(sources),
            verified_modules=tuple(m for m in modules if isinstance(m, str)),
        )
    return specs


def profile_dir(root: Path, profile: str) -> Path:
    return root / profile


def platform_tag() -> str:
    """清单里的平台口径：`win_amd64` / `linux_x86_64` / `macos_arm64`。"""
    system = {"win32": "win", "darwin": "macos"}.get(sys.platform, "linux")
    return f"{system}_{_machine()}"


def read_installed(directory: Path) -> InstalledRuntime | None:
    """解析 `<profile>/runtime.json`；缺件或坏件返回 None（不抛，只提示）。"""
    manifest = directory / MANIFEST_FILE
    if not manifest.is_file():
        return None
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[runtime] 安装清单损坏：{manifest}（{exc}）", file=sys.stderr)
        return None
    if not isinstance(raw, dict) or not raw.get("profile"):
        return None
    installed = InstalledRuntime(
        profile=str(raw.get("profile")),
        python=str(raw.get("python") or ""),
        platform=str(raw.get("platform") or ""),
        installed_at=str(raw.get("installed_at") or ""),
        site_packages=str(raw.get(SITE_DIR) or SITE_DIR),
        bundle_sha256=raw.get("bundle_sha256") or None,
    )
    if not (directory / installed.site_packages).is_dir():
        print(f"[runtime] {directory} 缺 {installed.site_packages}/，按未安装处理", file=sys.stderr)
        return None
    return installed


def installed_profiles(root: Path | None = None) -> list[InstalledRuntime]:
    base = (root or default_root()).expanduser()
    if not base.is_dir():
        return []
    found: list[InstalledRuntime] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        installed = read_installed(child)
        if installed is not None:
            found.append(installed)
    return found


def active_profile(root: Path | None = None) -> str | None:
    """档位优先级：env > `active` 指针 > 唯一已装档位 > 最近安装的一档。"""
    override = os.environ.get(ENV_PROFILE, "").strip()
    if override and read_installed(profile_dir(root or default_root(), override)) is not None:
        return override

    base = (root or default_root()).expanduser()
    pointer = base / ACTIVE_FILE
    if pointer.is_file():
        name = pointer.read_text(encoding="utf-8").strip()
        if name and read_installed(base / name) is not None:
            return name

    found = installed_profiles(base)
    if len(found) == 1:
        return found[0].profile
    if not found:
        return None
    newest = max(found, key=lambda item: item.installed_at)
    print(
        f"[runtime] 多个档位但缺 {ACTIVE_FILE} 指针，暂用最近安装的 {newest.profile}",
        file=sys.stderr,
    )
    return newest.profile


def active_layout(root: Path | None = None) -> RuntimeLayout | None:
    base = (root or default_root()).expanduser()
    profile = active_profile(base)
    if profile is None:
        return None
    installed = read_installed(profile_dir(base, profile))
    if installed is None:
        return None
    return RuntimeLayout(
        profile=profile,
        root=base / profile,
        site_packages=base / profile / installed.site_packages,
        installed=installed,
    )


def inject(*, root: Path | None = None, force: bool = False) -> RuntimeLayout | None:
    """把运行时接进当前解释器；无运行时/版本不符时安静返回 None。

    必须在首次 import torch 之前调用（组合根 `serve()` 第一句）。
    返回的 layout 供组合根打日志与首启引导复用。
    """
    if not (force or _is_frozen() or _env_flag(ENV_FORCE)):
        return None
    layout = active_layout(root)
    if layout is None:
        return None
    if not _python_matches(layout.installed.python):
        print(
            f"[runtime] {layout.profile} 为 Python {layout.installed.python} 构建，"
            f"当前 {sys.version_info.major}.{sys.version_info.minor}，跳过注入",
            file=sys.stderr,
        )
        return None

    site = str(layout.site_packages)
    if site not in _INJECTED:
        if site in sys.path:
            sys.path.remove(site)
        sys.path.insert(0, site)  # 必须压过 ONEDIR 自带的 numpy 等
        importlib.invalidate_caches()
        _install_finder(layout.site_packages)
        _add_dll_dirs(layout.site_packages)
        _INJECTED.add(site)
    return layout


def _install_finder(site: Path) -> None:
    """把运行时 finder 插到 meta_path 最前（见 `_RuntimeFinder` 的理由）。"""
    if any(isinstance(finder, _RuntimeFinder) for finder in sys.meta_path):
        return
    sys.meta_path.insert(0, _RuntimeFinder(site))


def verify(layout: RuntimeLayout, modules: tuple[str, ...] | None = None) -> list[str]:
    """逐个 import 验证运行时；返回失败项（空 = 全通）。

    只在 CLI/开发机跑：真机首启不该为了自检把 torch 拉起来两遍。
    """
    targets = modules or _spec_modules(layout.profile)
    failures: list[str] = []
    for name in targets:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001  自检要把真实失败原因带给用户
            failures.append(f"{name}: {exc}")
    return failures


def install_bundle(
    archive: Path,
    profile: str,
    *,
    root: Path | None = None,
    force: bool = False,
    expected_sha256: str | None = None,
    spec: RuntimeSpec | None = None,
) -> RuntimeLayout:
    """解压预构建档案并激活。

    档案两种形态都认：根目录含 `site-packages/`（推荐，可带额外文件），或
    归档内容本身就是 site-packages。失败一律不动旧档（14.2 原子落盘）。
    """
    base = (root or default_root()).expanduser()
    archive = Path(archive)
    if not archive.is_file():
        raise FileNotFoundError(f"运行时档案不存在：{archive}")

    target = base / profile
    if target.exists() and not force:
        raise FileExistsError(f"{target} 已存在（--force 覆盖）")

    digest = _sha256(archive)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"运行时档案 sha256 不匹配：{archive}")

    staging = base / ".staging" / f"{profile}-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        _extract(archive, staging)
        site = staging / SITE_DIR
        if not site.is_dir():
            # 扁平归档：内容即 site-packages，统一成标准布局
            site = staging / SITE_DIR
            site.mkdir()
            for child in list(staging.iterdir()):
                if child.name != SITE_DIR:
                    shutil.move(str(child), str(site / child.name))
        installed = InstalledRuntime(
            profile=profile,
            python=(spec.python if spec else _current_python()),
            platform=(spec.platform if spec else platform_tag()),
            installed_at=datetime.now(UTC).isoformat(timespec="seconds"),
            site_packages=SITE_DIR,
            bundle_sha256=digest,
        )
        (staging / MANIFEST_FILE).write_text(
            json.dumps(_manifest_payload(installed), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _swap_in(staging, target, force=force)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    base.mkdir(parents=True, exist_ok=True)
    (base / ACTIVE_FILE).write_text(f"{profile}\n", encoding="utf-8")
    layout = active_layout(base)
    if layout is None:  # 刚装完必然可解析；防御坏归档
        raise RuntimeError(f"运行时 {profile} 安装后无法解析")
    return layout


def download_bundle(
    source: BundleSource,
    *,
    dest_dir: Path | None = None,
    progress: Progress | None = None,
) -> Path:
    """下载归档到 `<runtime>/.downloads/`（断点续传 + sha256 校验）。

    `file://` 走本地拷贝（离线/内网/自建档案的落地点），其余走 HTTP。
    """
    if not source.url:
        raise ValueError("运行时来源未配置 url")
    name = source.url.rsplit("/", 1)[-1] or "runtime.zip"
    folder = (dest_dir or (default_root() / ".downloads")).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    if target.is_file() and (
        source.sha256 is None or _sha256(target) == source.sha256
    ):
        return target

    if source.url.startswith("file://"):
        _copy_local(source.url, target, progress=progress)
    else:
        _download_http(source, target, progress=progress)

    if source.sha256 is not None and _sha256(target) != source.sha256:
        target.unlink(missing_ok=True)
        raise ValueError(f"下载校验失败（sha256）：{source.url}")
    if progress is not None:
        progress(100)
    return target


def _copy_local(url: str, target: Path, *, progress: Progress | None) -> None:
    source = Path(url2pathname(urlparse(url).path))
    if not source.is_file():
        raise FileNotFoundError(f"本地运行时档案不存在：{source}")
    part = target.with_name(f".{target.name}.part")
    shutil.copyfile(source, part)
    if progress is not None:
        progress(99)
    os.replace(part, target)


def _download_http(source: BundleSource, target: Path, *, progress: Progress | None) -> None:
    part = target.with_name(f".{target.name}.part")
    existing = part.stat().st_size if part.is_file() else 0
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    with httpx.Client(follow_redirects=True, timeout=None) as client, client.stream(
        "GET", source.url, headers=headers
    ) as resp:
        if resp.status_code == 416 and existing:
            pass
        else:
            if resp.status_code == 200 and existing:
                existing = 0
            elif resp.status_code not in (200, 206):
                resp.raise_for_status()
            total = existing + int(resp.headers.get("content-length", "0") or "0")
            done = existing
            mode = "ab" if existing and resp.status_code == 206 else "wb"
            with part.open(mode) as handle:
                for chunk in resp.iter_bytes(1 << 20):
                    handle.write(chunk)
                    done += len(chunk)
                    if progress is not None and total > 0:
                        progress(min(99, int(done * 100 / total)))
    os.replace(part, target)


# ------------------------------ 内部 ------------------------------


def _manifest_payload(installed: InstalledRuntime) -> dict[str, Any]:
    return {
        "version": MANIFEST_VERSION,
        "profile": installed.profile,
        "python": installed.python,
        "platform": installed.platform,
        "installed_at": installed.installed_at,
        "site-packages": installed.site_packages,
        "bundle_sha256": installed.bundle_sha256,
    }


def _swap_in(staging: Path, target: Path, *, force: bool) -> None:
    """目录替换：旧档先挪开再换新，失败可回滚（Windows 不允许覆盖非空目录）。"""
    backup = target.with_name(f".{target.name}.old")
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        if not force:
            raise FileExistsError(f"{target} 已存在（--force 覆盖）")
        os.replace(target, backup)
    try:
        os.replace(staging, target)
    except OSError:
        if backup.exists() and not target.exists():
            os.replace(backup, target)  # 回滚旧档，别把用户变成"没运行时"
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


def _extract(archive: Path, dest: Path) -> None:
    """解压并挡住 zip-slip（`../` / 绝对路径）。"""
    root = dest.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            resolved = (dest / member.filename).resolve()
            if resolved != root and root not in resolved.parents:
                raise ValueError(f"归档含越界路径：{member.filename}")
        bundle.extractall(dest)


def _add_dll_dirs(site: Path) -> None:
    """torch/CUDA 的原生 DLL 目录（Windows 需要显式登记，PATH 只是兜底）。"""
    dirs = [site, site / "torch" / "lib"]
    dirs.extend(sorted(site.glob("nvidia/*/bin")))
    dirs.extend(sorted(site.glob("*.libs")))  # numpy/scipy 的 OpenBLAS
    existing = [d for d in dirs if d.is_dir()]
    if not existing:
        return
    if os.name == "nt":
        for directory in existing:
            try:
                _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
            except OSError as exc:  # 目录被策略挡住时别让启动失败
                print(f"[runtime] DLL 目录不可用：{directory}（{exc}）", file=sys.stderr)
    os.environ["PATH"] = os.pathsep.join(
        [*(str(d) for d in existing), os.environ.get("PATH", "")]
    )


def _spec_modules(profile: str) -> tuple[str, ...]:
    try:
        spec = load_specs().get(profile)
    except ValueError:
        return ()
    return spec.verified_modules if spec else ()


def _python_matches(required: str) -> bool:
    if not required:
        return True
    return required == _current_python()


def _current_python() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _machine() -> str:
    import platform

    return platform.machine().lower()


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "ACTIVE_FILE",
    "BundleSource",
    "ENV_PROFILE",
    "ENV_RUNTIME_DIR",
    "InstalledRuntime",
    "RuntimeLayout",
    "RuntimeSpec",
    "active_layout",
    "active_profile",
    "default_root",
    "download_bundle",
    "inject",
    "install_bundle",
    "installed_profiles",
    "load_specs",
    "platform_tag",
    "profile_dir",
    "read_installed",
    "verify",
]
