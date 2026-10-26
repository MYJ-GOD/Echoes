"""首启向导的后端（ADR-011/016）：硬件检测 → 档位推荐 → 运行时/模型安装。

**为什么检测和下载都在 sidecar**：下载器（运行时档案 / 模型清单）与注入布局都在
Python 侧；壳只负责“跑一次 setup、把进度转给前端”，避免同一套断点续传写两遍。

**边界**：本模块只读缓存目录、只写 `<runtime>` / `<models>`；不碰 SQLite
（`first_run_done` 与设置归壳，3.4 拉取语义）。安装失败抛 `EchoesError`，
`setup_cli` 折成一行 JSON。
"""
from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from echoes_sidecar import runtime
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.models.manager import ModelManager

# 本地引擎跑起来所需的最小权重集（与 models/manifest.json 的 id 对齐）
REQUIRED_MODELS: tuple[str, ...] = (
    "faster-whisper-small",
    "bge-small-zh-v1.5",
    "cosyvoice2-0.5b",
)
OLLAMA_ENV = "OLLAMA_URL"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
# CosyVoice2 0.5B fp16 实测约 4GB 显存；留 2GB 余量给 WebView 与系统
MIN_CUDA_VRAM_GB = 6.0

Progress = Callable[[str, int], None]  # (item, pct)


@dataclass(frozen=True)
class GpuInfo:
    name: str
    vram_gb: float


@dataclass(frozen=True)
class OllamaInfo:
    url: str
    reachable: bool
    models: tuple[str, ...] = ()


@dataclass(frozen=True)
class SetupReport:
    """一次检测的完整快照；前端据此渲染向导第一屏。"""

    platform: str
    python: str
    frozen: bool
    cpu: str
    ram_gb: float | None
    gpu: GpuInfo | None
    disk_free_gb: float
    disk_path: str
    ollama: OllamaInfo
    runtime_profiles: tuple[str, ...]
    active_profile: str | None
    dev_venv: bool
    models: dict[str, bool] = field(default_factory=dict)
    recommended_profile: str = "cpu"
    needs_runtime: bool = False
    missing_models: tuple[str, ...] = ()
    download_mb: float = 0.0
    runtime_archive_ready: bool = False
    notes: tuple[str, ...] = ()


# ------------------------------ 检测 ------------------------------


def detect(
    *,
    models_root: Path | None = None,
    runtime_root: Path | None = None,
    model_ids: Sequence[str] = REQUIRED_MODELS,
) -> SetupReport:
    """探测本机并给出建议；所有外部探测都走模块级函数（测试可 monkeypatch）。"""
    gpu = _gpu_probe()
    ollama = _ollama_probe()
    profiles = tuple(item.profile for item in runtime.installed_profiles(runtime_root))
    active = runtime.active_profile(runtime_root)
    dev_venv = _dev_venv()
    manager = ModelManager.load(root=models_root)
    models = {model_id: manager.status(model_id).installed for model_id in model_ids}
    notes: list[str] = []

    specs = runtime.load_specs()
    needs_runtime = not dev_venv and active is None
    archive_ready = any(
        bool(source.url) for spec in specs.values() for source in spec.bundles
    )
    if needs_runtime and not archive_ready:
        notes.append(
            "运行时档案未发布：需要先在构建机生成 zip 并回填 "
            "runtime_manifest.json 的 bundles[].url"
        )

    missing = tuple(model_id for model_id, ok in models.items() if not ok)
    download_mb = 0.0
    if needs_runtime:
        # 推荐档位的体积（未发布时也照实报，方便判断磁盘够不够）
        rec = _recommend(gpu, sys.platform)
        spec = specs.get(rec)
        download_mb += float(spec.size_mb) if spec else 0.0
    for model_id in missing:
        try:
            download_mb += manager.status(model_id).entry.size_mb
        except KeyError:
            notes.append(f"模型清单缺 {model_id}（升级 sidecar？）")

    return SetupReport(
        platform=sys.platform,
        python=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        frozen=bool(getattr(sys, "frozen", False)),
        cpu=_cpu_name(),
        ram_gb=_ram_gb(),
        gpu=gpu,
        disk_free_gb=_disk_free_gb(),
        disk_path=str(Path.home()),
        ollama=ollama,
        runtime_profiles=profiles,
        active_profile=active,
        dev_venv=dev_venv,
        models=models,
        recommended_profile=_recommend(gpu, sys.platform),
        needs_runtime=needs_runtime,
        missing_models=missing,
        download_mb=round(download_mb, 1),
        runtime_archive_ready=archive_ready,
        notes=tuple(notes),
    )


def as_dict(report: SetupReport) -> dict[str, Any]:
    return asdict(report)


def _recommend(gpu: GpuInfo | None, platform_name: str) -> str:
    """有 NVIDIA 且显存够 → cuda126；其余一律 cpu（Windows 优先，ADR-011）。"""
    if gpu is not None and gpu.vram_gb >= MIN_CUDA_VRAM_GB:
        return "cuda126" if platform_name.startswith("win") else "cuda126"
    return "cpu"


def _dev_venv() -> bool:
    """源码形态且 venv 有 torch：直接用 `.venv`，不必装运行时档案。"""
    if getattr(sys, "frozen", False):
        return False
    return importlib.util.find_spec("torch") is not None


def _cpu_name() -> str:
    name = platform.processor().strip()
    return name or platform.machine() or "unknown"


def _ram_gb() -> float | None:
    """Windows：GlobalMemoryStatusEx；其他平台返回 None（向导照样能跑）。"""
    if os.name != "nt":
        return None

    class _MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = _MemoryStatus()
    status.dwLength = ctypes.sizeof(_MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    total = float(status.ullTotalPhys)
    return round(total / (1024**3), 1)


def _gpu_probe() -> GpuInfo | None:
    """`nvidia-smi` 是唯一跨驱动版本都稳的探测方式；没有就当她没独显。"""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    first = result.stdout.strip().splitlines()[0]
    name, _, memory = first.partition(",")
    try:
        vram = round(float(memory.strip()) / 1024, 1)
    except ValueError:
        vram = 0.0
    return GpuInfo(name=name.strip(), vram_gb=vram)


def _ollama_probe() -> OllamaInfo:
    url = os.environ.get(OLLAMA_ENV, DEFAULT_OLLAMA_URL).rstrip("/")
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError):
        return OllamaInfo(url=url, reachable=False)
    names = tuple(
        str(item.get("name"))
        for item in data.get("models", [])
        if isinstance(item, dict) and item.get("name")
    )
    return OllamaInfo(url=url, reachable=True, models=names)


def _disk_free_gb() -> float:
    try:
        usage = shutil.disk_usage(Path.home())
    except OSError:
        return 0.0
    return round(usage.free / (1024**3), 1)


# ------------------------------ 安装 ------------------------------


def install_runtime(
    profile: str | None = None,
    *,
    runtime_root: Path | None = None,
    progress: Progress | None = None,
) -> SetupReport:
    """下载并激活运行时档案；未发布地址时抛 `RUNTIME_ARCHIVE_UNAVAILABLE`。"""
    specs = runtime.load_specs()
    target = profile or runtime.active_profile(runtime_root) or "cpu"
    spec = specs.get(target)
    if spec is None:
        raise EchoesError(
            ErrorCode.INTERNAL_ERROR, f"未知运行时档位 {target}（可选 {', '.join(specs)}）"
        )
    if spec.platform and spec.platform != runtime.platform_tag():
        raise EchoesError(
            ErrorCode.INTERNAL_ERROR,
            f"{target} 是 {spec.platform} 档案，当前 {runtime.platform_tag()}",
        )

    sources = [source for source in spec.bundles if source.url]
    if not sources:
        raise EchoesError(
            ErrorCode.MODEL_NOT_LOADED,
            f"{target} 运行时档案未发布：构建机生成 zip 后回填 runtime_manifest.json",
        )

    last_error: Exception | None = None
    for source in sources:
        try:
            archive = runtime.download_bundle(
                source,
                dest_dir=(runtime_root or runtime.default_root()) / ".downloads",
                progress=(lambda pct: progress and progress("runtime", pct)),
            )
            layout = runtime.install_bundle(
                archive,
                target,
                root=runtime_root,
                force=True,
                expected_sha256=source.sha256,
                spec=spec,
            )
            if progress is not None:
                progress("runtime", 100)
            print(f"[setup] 运行时已装：{layout.site_packages}", file=sys.stderr)
            break
        except Exception as exc:  # noqa: BLE001  多源按顺序尝试
            last_error = exc
            print(f"[setup] 运行时源失败（{source.url}）：{exc}", file=sys.stderr)
    else:
        raise EchoesError(
            ErrorCode.MODEL_NOT_LOADED, f"运行时 {target} 安装失败：{last_error}"
        )
    return detect(runtime_root=runtime_root)


def install_models(
    model_ids: Sequence[str] = REQUIRED_MODELS,
    *,
    models_root: Path | None = None,
    progress: Progress | None = None,
) -> dict[str, str]:
    """按清单安装权重；返回 `{id: 状态}`（已安装的不重复下载）。"""
    manager = ModelManager.load(root=models_root)
    result: dict[str, str] = {}
    for model_id in model_ids:
        try:
            status = manager.status(model_id)
        except KeyError:
            result[model_id] = "未知模型"
            continue
        if status.installed:
            result[model_id] = "already"
            if progress is not None:
                progress(model_id, 100)
            continue
        try:
            manager.ensure(
                model_id,
                progress=(
                    lambda item, pct: progress and progress(item, pct)
                ),
            )
            result[model_id] = "installed"
        except EchoesError as exc:
            result[model_id] = exc.code.value
            print(f"[setup] 模型 {model_id} 安装失败：{exc.message}", file=sys.stderr)
    return result


def json_line(payload: dict[str, Any]) -> str:
    """单行 JSON（壳按行解析），中文不转义，便于日志直读。"""
    return json.dumps(payload, ensure_ascii=False)


__all__ = [
    "DEFAULT_OLLAMA_URL",
    "GpuInfo",
    "OllamaInfo",
    "REQUIRED_MODELS",
    "SetupReport",
    "as_dict",
    "detect",
    "install_models",
    "install_runtime",
    "json_line",
]
