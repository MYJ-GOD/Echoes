"""首启向导的后端（ADR-011/016）：硬件检测 → 档位推荐 → 运行时/模型安装。

**为什么检测和下载都在 sidecar**：下载器（运行时档案 / 模型清单）与注入布局都在
Python 侧；壳只负责“跑一次 setup、把进度转给前端”，避免同一套断点续传写两遍。

**边界**：本模块只读缓存目录、只写 `<runtime>` / `<models>`；不碰 SQLite
（`first_run_done` 与设置归壳，3.4 拉取语义）。安装失败抛 `EchoesError`，
`setup_cli` 折成一行 JSON。
"""
from __future__ import annotations

import asyncio
import ctypes
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from echoes_sidecar import runtime
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db import Storage
from echoes_sidecar.db.memory_repo import CATEGORIES
from echoes_sidecar.db.paths import resolve as resolve_paths
from echoes_sidecar.memory.embedding import TransformersEmbedder
from echoes_sidecar.models.manager import ModelManager
from echoes_sidecar.secrets import llm_api_key

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


def _camel(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(part.capitalize() for part in rest)


def _camelize(value: Any) -> Any:
    """snake_case → camelCase（逐层）。壳侧视图一律 camelCase（见 `ipc.ts`）。"""
    if isinstance(value, dict):
        return {_camel(key): _camelize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_camelize(item) for item in value]
    return value


def as_dict(report: SetupReport) -> dict[str, Any]:
    """向导 JSON 行里的 report：**camelCase**（`ipc.ts::SetupReport` 的契约）。

    `asdict` 给的是 snake_case（`missing_models` / `recommended_profile` …），
    前端读 `missingModels` 会拿到 undefined —— 首启向导会在渲染时崩掉（白屏）。
    `models` 的键是模型 id（含连字符），不是字段名，原样保留。
    """
    raw = asdict(report)
    mapped: dict[str, Any] = _camelize(raw)
    mapped["models"] = dict(raw["models"])
    return mapped


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


# ------------------------------ 模型目录（R2a 2.6） ------------------------------


@dataclass(frozen=True)
class ModelOption:
    """下拉候选：id + 归属；`context_window` 预留（云端 `/v1/models` 不返回）。

    Ollama 的上下文长度要逐模型 `/api/show`（N 次请求），v1 先在「生效路径」
    里显示模型名，不阻塞设置页；需要时再做懒加载。
    """

    id: str
    owner: str | None = None
    context_window: int | None = None


def list_models(provider: str, *, base_url: str | None = None) -> list[ModelOption]:
    """拉取可用的 LLM 模型目录（3.2）。

    - `ollama`：本机 `/api/tags`，不需要 key；不可达 → `LLM_PROVIDER_UNAVAILABLE`
    - `openai`：`GET {base}/models`，key 从凭据管理器读（与 sidecar 请求同口径）
    - 其它 provider（mock）没有目录概念，调用方不该发起
    """
    if provider == "ollama":
        url = os.environ.get(OLLAMA_ENV, DEFAULT_OLLAMA_URL).rstrip("/")
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EchoesError(
                ErrorCode.LLM_PROVIDER_UNAVAILABLE,
                f"Ollama 不可达（{url}）：{exc}",
            ) from exc
        return [
            ModelOption(id=str(item["name"]), owner="ollama")
            for item in data.get("models", [])
            if isinstance(item, dict) and item.get("name")
        ]

    if provider == "openai":
        base = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
        if not base:
            raise EchoesError(ErrorCode.LLM_PROVIDER_UNAVAILABLE, "云端目录缺 base URL")
        key = llm_api_key()
        if not key:
            raise EchoesError(
                ErrorCode.LLM_KEY_MISSING,
                "尚未配置云端 LLM 的 API key（设置 → 引擎）",
            )
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{base}/models", headers={"Authorization": f"Bearer {key}"}
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise EchoesError(
                ErrorCode.LLM_PROVIDER_UNAVAILABLE,
                f"云端模型目录不可用（{base}）：{exc}",
            ) from exc
        items = data.get("data", []) if isinstance(data, dict) else []
        options: list[ModelOption] = []
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            owner = item.get("owned_by")
            options.append(
                ModelOption(
                    id=str(item["id"]),
                    owner=str(owner) if isinstance(owner, str) else None,
                )
            )
        return options

    raise EchoesError(ErrorCode.INTERNAL_ERROR, f"provider {provider!r} 没有模型目录")


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


# ------------------------------ 模型占用 / 删除（R5 7.9） ------------------------------


def models_info(*, models_root: Path | None = None) -> list[dict[str, Any]]:
    """清单里每个模型的安装状态与磁盘占用（camelCase，前端直接渲染）。

    `size_mb` 是清单里的预估下载体积；`bytes` 是当前目录的实际占用（未安装为 0）。
    Ollama 模型不在本模块的目录里，占用显示 0、删除也不归我们管。
    """
    manager = ModelManager.load(root=models_root)
    result: list[dict[str, Any]] = []
    for status in manager.list_status():
        entry = status.entry
        actual = 0
        if entry.kind != "ollama" and status.path.exists():
            actual = _dir_size(status.path)
        result.append(
            {
                "id": entry.id,
                "displayName": entry.display_name,
                "kind": entry.kind,
                "installed": status.installed,
                "detail": status.detail,
                "path": str(status.path),
                "expectedMb": entry.size_mb,
                "bytes": actual,
            }
        )
    return result


def remove_models(
    model_ids: Sequence[str], *, models_root: Path | None = None
) -> dict[str, Any]:
    """删除本地权重目录（只删清单 target 下的内容，Ollama 模型拒绝）。

    **不做确认弹窗**：确认归壳/前端；这里只保证「只删模型目录、绝不越界」。
    """
    ids = [item.strip() for item in model_ids if item and item.strip()]
    if not ids:
        raise EchoesError(ErrorCode.INTERNAL_ERROR, "没有指定要删除的模型")
    manager = ModelManager.load(root=models_root)
    removed: list[str] = []
    freed = 0
    for model_id in ids:
        try:
            status = manager.status(model_id)
        except KeyError as exc:
            raise EchoesError(
                ErrorCode.INTERNAL_ERROR, f"未知模型 {model_id!r}"
            ) from exc
        entry = status.entry
        if entry.kind == "ollama":
            raise EchoesError(
                ErrorCode.INTERNAL_ERROR,
                f"{model_id} 由 Ollama 管理，请用 `ollama rm {entry.target}` 删除",
            )
        path = manager.path_for(entry)
        if path.exists():
            size = _dir_size(path)
            shutil.rmtree(path)
            freed += size
            removed.append(model_id)
    return {"removed": removed, "freedBytes": freed}


def _dir_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                continue
    return total


# ------------------------------ 记忆写接口（R3b） ------------------------------
MEMORY_FACT_MAX_CHARS = 500
MEMORY_OPS = frozenset({"add", "update", "merge", "bulk"})
# 批量导入单次上限：一次嵌入 200 条已经是秒级，再多应该走多次操作
MEMORY_BULK_MAX = 200


def import_memories(
    raw: str,
    *,
    default_category: str = "other",
    data_root: Path | None = None,
    model_dir: Path | None = None,
    embedder: Any | None = None,
) -> dict[str, Any]:
    """R5 记忆批量导入：每行一条，支持 `事实|类别`。

    **去重口径**：与现有生效事实（未删/未被取代）原文完全相同就跳过；同一批里的
    重复也只保留第一条。不做语义去重——那是「合并」按钮的活，自动合并会悄悄改
    用户写下的原文。
    """
    if default_category not in CATEGORIES:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR,
            f"未知记忆类别 {default_category!r}（{'/'.join(sorted(CATEGORIES))}）",
        )

    parsed: list[tuple[str, str]] = []
    seen: set[str] = set()
    duplicates = 0
    for line in raw.splitlines():
        text = line.strip().lstrip("-*•").strip()
        if not text:
            continue
        fact, category = text, default_category
        head, sep, tail = text.rpartition("|")
        if sep and head.strip() and tail.strip() in CATEGORIES:
            fact, category = head.strip(), tail.strip()
        if len(fact) > MEMORY_FACT_MAX_CHARS:
            raise EchoesError(
                ErrorCode.STORAGE_ERROR,
                f"记忆内容过长（> {MEMORY_FACT_MAX_CHARS} 字）：{fact[:30]}…",
            )
        if fact in seen:
            duplicates += 1
            continue
        seen.add(fact)
        parsed.append((fact, category))
    if not parsed:
        raise EchoesError(ErrorCode.STORAGE_ERROR, "没有可导入的记忆（每行一条）")
    if len(parsed) > MEMORY_BULK_MAX:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR,
            f"一次最多导入 {MEMORY_BULK_MAX} 条（本次 {len(parsed)} 条）",
        )

    paths = resolve_paths(data_root)
    storage = Storage.open(paths.db_file)
    try:
        existing = storage.memories.active_texts()
        fresh = [(fact, category) for fact, category in parsed if fact not in existing]
        skipped = duplicates + (len(parsed) - len(fresh))
        if not fresh:
            return {"op": "bulk", "added": 0, "skipped": skipped, "ids": []}

        vectors = asyncio.run(
            (embedder or TransformersEmbedder(model_dir=model_dir)).embed(
                [fact for fact, _ in fresh]
            )
        )
        now = time.time()
        ids: list[str] = []
        for (fact, category), vector in zip(fresh, vectors, strict=True):
            created = storage.memories.insert(
                fact_id=uuid4().hex,
                fact=fact,
                category=category,
                embedding=vector,
                now=now,
            )
            ids.append(created.id)
        return {"op": "bulk", "added": len(ids), "skipped": skipped, "ids": ids}
    finally:
        storage.close()


def write_memory(
    op: str,
    *,
    fact: str | None = None,
    fact_id: str | None = None,
    ids: Sequence[str] = (),
    category: str = "other",
    data_root: Path | None = None,
    model_dir: Path | None = None,
    embedder: Any | None = None,
) -> dict[str, Any]:
    """R3b 记忆写接口（一次性进程）：add / update / merge。

    **为什么走 `--setup` 而不是聊天协议**：写记忆必须重新生成 bge 向量，
    聊天面是冻结的 hello/state 契约；一次性进程复用同一套 Storage/嵌入器，
    不把「编辑记忆」塞进 turn 状态机。代价是每次操作加载一次嵌入权重
    （bge-small 秒级），对管理页的点击频率可以接受。

    - `add`：新事实（来源置空）
    - `update`：旧事实标记 `superseded_by = 新 id`（历史保留；等价「编辑」）
    - `merge`：多条旧事实合并成一条（全部指向新 id）
    """
    if op not in MEMORY_OPS:
        raise EchoesError(ErrorCode.INTERNAL_ERROR, f"未知记忆操作 {op!r}")
    text = (fact or "").strip()
    if not text:
        raise EchoesError(ErrorCode.STORAGE_ERROR, "记忆内容不能为空")
    if len(text) > MEMORY_FACT_MAX_CHARS:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR, f"记忆内容过长（> {MEMORY_FACT_MAX_CHARS} 字）"
        )
    if category not in CATEGORIES:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR,
            f"未知记忆类别 {category!r}（{'/'.join(sorted(CATEGORIES))}）",
        )
    old_ids = [item.strip() for item in ids if item and item.strip()]
    if op == "update" and not (fact_id or "").strip():
        raise EchoesError(ErrorCode.STORAGE_ERROR, "编辑记忆需要 fact_id")
    if op == "merge" and len(old_ids) < 2:
        raise EchoesError(ErrorCode.STORAGE_ERROR, "合并至少需要两条记忆")

    paths = resolve_paths(data_root)
    storage = Storage.open(paths.db_file)
    try:
        vectors = asyncio.run(
            (embedder or TransformersEmbedder(model_dir=model_dir)).embed([text])
        )
        vector = vectors[0]
        new_id = uuid4().hex
        now = time.time()
        common = {
            "fact_id": new_id,
            "fact": text,
            "category": category,
            "embedding": vector,
            "now": now,
        }
        if op == "add":
            created = storage.memories.insert(**common)
        elif op == "update":
            created = storage.memories.supersede((fact_id or "").strip(), **common)
        else:
            created = storage.memories.merge(old_ids, **common)
        return {"op": op, "factId": created.id}
    finally:
        storage.close()


__all__ = [
    "DEFAULT_OLLAMA_URL",
    "GpuInfo",
    "MEMORY_FACT_MAX_CHARS",
    "MEMORY_OPS",
    "ModelOption",
    "OllamaInfo",
    "REQUIRED_MODELS",
    "SetupReport",
    "as_dict",
    "detect",
    "install_models",
    "install_runtime",
    "json_line",
    "list_models",
    "import_memories",
    "models_info",
    "remove_models",
    "write_memory",
]
