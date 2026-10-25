"""模型管理器（7.3）：清单、缓存扫描、多源下载、sha256、Ollama 复用。

**边界**：只在部署/首启引导时联网；运行时引擎只读本地缓存，缺件报
`MODEL_NOT_LOADED`（7.3/16.1 离线红线）。重活（HTTP/大文件）由本模块承担，
引擎不感知下载来源。

清单是主程序随包的 JSON（`models/manifest.json`）：
- `repo`：HuggingFace / ModelScope 快照，落到 `~/.cache/echoes/models/<target>`；
- `file`：单文件直链，断点续传 + sha256；
- `ollama`：复用本机 Ollama 模型（状态查询 / `ollama pull`）。

多源按清单顺序尝试；repo 源失败换下一个，file 源失败换下一个 URL。校验失败
删残件重下（14.2 原子落盘：先 `.part`，校验通过再 rename）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

from echoes_sidecar.core.errors import EchoesError, ErrorCode

MODELS_ENV = "ECHOES_MODELS_DIR"
OLLAMA_ENV = "OLLAMA_URL"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "manifest.json"

Progress = Callable[[str, int], None]
RepoDownloader = Callable[["ModelSource", Path, Progress | None], None]
OllamaList = Callable[[], list[str]]
OllamaPull = Callable[[str, Progress | None], None]

_SOURCE_TYPES = frozenset({"modelscope", "huggingface", "url"})
_KINDS = frozenset({"repo", "file", "ollama"})


@dataclass(frozen=True)
class ModelSource:
    type: Literal["modelscope", "huggingface", "url"]
    id: str | None = None
    url: str | None = None
    revision: str | None = None


@dataclass(frozen=True)
class ModelEntry:
    id: str
    display_name: str
    kind: Literal["repo", "file", "ollama"]
    target: str
    sources: tuple[ModelSource, ...]
    required_files: tuple[str, ...]
    size_mb: float
    tier: str
    sha256: dict[str, str] | None = None


@dataclass(frozen=True)
class ModelStatus:
    entry: ModelEntry
    installed: bool
    path: Path
    detail: str


class ModelManager:
    """清单驱动的模型状态/下载器；所有外部 IO 可注入，便于离线测试。"""

    def __init__(
        self,
        entries: list[ModelEntry],
        *,
        root: Path | None = None,
        repo_downloader: RepoDownloader | None = None,
        ollama_list: OllamaList | None = None,
        ollama_pull: OllamaPull | None = None,
        http_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self._entries = {entry.id: entry for entry in entries}
        if len(self._entries) != len(entries):
            raise ValueError("模型清单 id 重复")
        self._root = (root or default_root()).expanduser()
        self._repo_downloader = repo_downloader or _default_repo_downloader
        self._ollama_list = ollama_list or self._default_ollama_list
        self._ollama_pull = ollama_pull or self._default_ollama_pull
        self._http_factory = http_factory or (
            lambda: httpx.Client(follow_redirects=True, timeout=60.0)
        )

    @classmethod
    def load(
        cls,
        manifest: Path | None = None,
        *,
        root: Path | None = None,
        **kwargs: Any,
    ) -> ModelManager:
        return cls(load_manifest(manifest), root=root, **kwargs)

    @property
    def root(self) -> Path:
        return self._root

    def entries(self) -> list[ModelEntry]:
        return list(self._entries.values())

    def path_for(self, entry: ModelEntry) -> Path:
        target = (self._root / entry.target).resolve()
        root = self._root.resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"模型 target 越出缓存根：{entry.target!r}")
        return target

    def status(self, model_id: str) -> ModelStatus:
        entry = self._entry(model_id)
        path = self.path_for(entry)
        if entry.kind == "ollama":
            names = self._safe_ollama_list()
            installed = entry.target in names
            return ModelStatus(entry, installed, path, "ok" if installed else "未在 Ollama 中")
        if entry.kind == "file":
            return self._file_status(entry, path)
        missing = [name for name in entry.required_files if not (path / name).is_file()]
        if missing:
            return ModelStatus(entry, False, path, f"缺少 {', '.join(missing)}")
        bad = self._bad_hashes(path, entry)
        if bad:
            return ModelStatus(entry, False, path, f"sha256 不匹配：{', '.join(bad)}")
        return ModelStatus(entry, True, path, "ok")

    def list_status(self) -> list[ModelStatus]:
        return [self.status(entry.id) for entry in self._entries.values()]

    def ensure(self, model_id: str, progress: Progress | None = None) -> Path:
        """确保模型可用；失败抛 MODEL_NOT_LOADED（部署引导捕获并重试）。"""
        entry = self._entry(model_id)
        current = self.status(model_id)
        if current.installed:
            return current.path

        if entry.kind == "ollama":
            self._ollama_pull(entry.target, progress)
            if self.status(model_id).installed:
                return self.path_for(entry)
            raise EchoesError(ErrorCode.MODEL_NOT_LOADED, f"Ollama 模型仍未就绪：{entry.target}")

        path = self.path_for(entry)
        if entry.kind == "file":
            self._download_file_entry(entry, path, progress)
        else:
            self._download_repo_entry(entry, path, progress)
        final = self.status(model_id)
        if not final.installed:
            raise EchoesError(
                ErrorCode.MODEL_NOT_LOADED,
                f"模型 {entry.id} 下载后校验失败：{final.detail}",
            )
        return path

    # ------------------------------ 内部 ------------------------------

    def _entry(self, model_id: str) -> ModelEntry:
        try:
            return self._entries[model_id]
        except KeyError as exc:
            raise KeyError(f"未知模型 {model_id!r}（见 manifest）") from exc

    def _file_status(self, entry: ModelEntry, path: Path) -> ModelStatus:
        if not path.is_file():
            return ModelStatus(entry, False, path, "文件不存在")
        expected = (entry.sha256 or {}).get(path.name)
        if expected is not None and _sha256(path) != expected:
            return ModelStatus(entry, False, path, "sha256 不匹配")
        return ModelStatus(entry, True, path, "ok")

    def _bad_hashes(self, path: Path, entry: ModelEntry) -> list[str]:
        if not entry.sha256:
            return []
        return [
            name
            for name, expected in entry.sha256.items()
            if (path / name).is_file() and _sha256(path / name) != expected
        ]

    def _download_repo_entry(
        self, entry: ModelEntry, path: Path, progress: Progress | None
    ) -> None:
        path.mkdir(parents=True, exist_ok=True)
        failures: list[str] = []
        for source in entry.sources:
            try:
                print(f"[models] {entry.id}: 尝试 {source.type}/{source.id}", file=sys.stderr)
                self._repo_downloader(source, path, progress)
                status = self.status(entry.id)
                if status.installed:
                    return
                failures.append(f"{source.type}: {status.detail}")
            except Exception as exc:  # noqa: BLE001  换源继续
                failures.append(f"{source.type}: {exc}")
                print(f"[models] {entry.id} 源失败：{exc}", file=sys.stderr)
        raise EchoesError(
            ErrorCode.MODEL_NOT_LOADED,
            f"模型 {entry.id} 所有源均失败：{'；'.join(failures)}",
        )

    def _download_file_entry(
        self, entry: ModelEntry, path: Path, progress: Progress | None
    ) -> None:
        expected = (entry.sha256 or {}).get(path.name)
        last_error: Exception | None = None
        for source in entry.sources:
            url = source.url
            if not url:
                continue
            try:
                self._download_url(entry.id, url, path, expected, progress)
                return
            except Exception as exc:  # noqa: BLE001  换源继续
                last_error = exc
                print(f"[models] {entry.id} 下载失败 {url}: {exc}", file=sys.stderr)
        raise EchoesError(
            ErrorCode.MODEL_NOT_LOADED,
            f"模型 {entry.id} 文件下载失败：{last_error}",
        )

    def _download_url(
        self,
        model_id: str,
        url: str,
        target: Path,
        expected: str | None,
        progress: Progress | None,
    ) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(f".{target.name}.part")
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                self._stream_to_part(model_id, url, part, progress)
                digest = _sha256(part)
                if expected is not None and digest != expected:
                    part.unlink(missing_ok=True)
                    raise ValueError("sha256 不匹配")
                os.replace(part, target)
                return
            except Exception as exc:
                if attempt == attempts:
                    part.unlink(missing_ok=True)
                    raise
                print(
                    f"[models] {model_id} 下载重试 {attempt}/{attempts}：{exc}",
                    file=sys.stderr,
                )

    def _stream_to_part(
        self, model_id: str, url: str, part: Path, progress: Progress | None
    ) -> None:
        existing = part.stat().st_size if part.is_file() else 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}
        with self._http_factory() as client, client.stream(
            "GET", url, headers=headers
        ) as resp:
            if resp.status_code == 416 and existing:
                return
            if resp.status_code == 200 and existing:
                existing = 0  # 服务端不支持 Range：从头来
            elif resp.status_code not in (200, 206):
                resp.raise_for_status()
            mode = "ab" if existing and resp.status_code == 206 else "wb"
            total = existing + int(resp.headers.get("content-length", "0") or "0")
            done = existing
            with part.open(mode) as handle:
                for chunk in resp.iter_bytes(1 << 16):
                    handle.write(chunk)
                    done += len(chunk)
                    if progress is not None and total > 0:
                        progress(model_id, min(99, int(done * 100 / total)))

    def _safe_ollama_list(self) -> list[str]:
        try:
            return self._ollama_list()
        except Exception as exc:  # noqa: BLE001  Ollama 未启动不是 status 的致命错误
            print(f"[models] Ollama 不可达：{exc}", file=sys.stderr)
            return []

    def _default_ollama_list(self) -> list[str]:
        url = os.environ.get(OLLAMA_ENV, DEFAULT_OLLAMA_URL).rstrip("/")
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
        return [str(item["name"]) for item in data.get("models", [])]

    def _default_ollama_pull(self, name: str, progress: Progress | None) -> None:
        url = os.environ.get(OLLAMA_ENV, DEFAULT_OLLAMA_URL).rstrip("/")
        with httpx.Client(timeout=None) as client, client.stream(
            "POST", f"{url}/api/pull", json={"name": name, "stream": True}
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                if event.get("error"):
                    raise EchoesError(
                        ErrorCode.MODEL_NOT_LOADED, f"Ollama pull 失败：{event['error']}"
                    )
                total = int(event.get("total") or 0)
                completed = int(event.get("completed") or 0)
                if progress is not None and total > 0:
                    progress(name, min(99, int(completed * 100 / total)))
        if progress is not None:
            progress(name, 100)


def default_root() -> Path:
    override = os.environ.get(MODELS_ENV, "").strip()
    if override:
        return Path(override)
    return Path.home() / ".cache" / "echoes" / "models"


def load_manifest(path: Path | None = None) -> list[ModelEntry]:
    manifest = Path(path) if path is not None else DEFAULT_MANIFEST
    try:
        raw = json.loads(manifest.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"模型清单不可读：{manifest}（{exc}）") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型清单不是合法 JSON：{manifest}（{exc}）") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("models"), list):
        raise ValueError(f"模型清单缺 models 数组：{manifest}")

    entries: list[ModelEntry] = []
    for index, item in enumerate(raw["models"]):
        if not isinstance(item, dict):
            raise ValueError(f"models[{index}] 必须是对象")
        entries.append(_parse_entry(item, index))
    return entries


def _parse_entry(item: dict[str, Any], index: int) -> ModelEntry:
    model_id = item.get("id")
    kind = item.get("kind")
    target = item.get("target")
    if not isinstance(model_id, str) or not model_id:
        raise ValueError(f"models[{index}] 缺 id")
    if kind not in _KINDS:
        raise ValueError(f"models[{index}]（{model_id}）未知 kind {kind!r}")
    if not isinstance(target, str) or not target:
        raise ValueError(f"models[{index}]（{model_id}）缺 target")
    target_path = Path(target)
    if target_path.is_absolute() or ".." in target_path.parts:
        raise ValueError(f"models[{index}]（{model_id}）target 必须是缓存根内相对路径")

    raw_sources = item.get("sources", [])
    if not isinstance(raw_sources, list):
        raise ValueError(f"models[{index}]（{model_id}）sources 必须是数组")
    sources: list[ModelSource] = []
    for src in raw_sources:
        if not isinstance(src, dict) or src.get("type") not in _SOURCE_TYPES:
            raise ValueError(f"models[{index}]（{model_id}）source.type 非法")
        source_type = str(src["type"])
        source_id = src.get("id")
        source_url = src.get("url")
        revision = src.get("revision")
        if source_type == "url" and not isinstance(source_url, str):
            raise ValueError(f"models[{index}]（{model_id}）url 源缺 url")
        if source_type != "url" and not isinstance(source_id, str):
            raise ValueError(f"models[{index}]（{model_id}）repo 源缺 id")
        sources.append(
            ModelSource(
                type=source_type,  # type: ignore[arg-type]
                id=source_id if isinstance(source_id, str) else None,
                url=source_url if isinstance(source_url, str) else None,
                revision=revision if isinstance(revision, str) else None,
            )
        )
    if kind in {"repo", "file"} and not sources:
        raise ValueError(f"models[{index}]（{model_id}）{kind} 至少一个源")

    required = item.get("required_files", [])
    if not isinstance(required, list) or not all(isinstance(x, str) for x in required):
        raise ValueError(f"models[{index}]（{model_id}）required_files 必须是字符串数组")
    sha = item.get("sha256")
    if sha is not None and (
        not isinstance(sha, dict)
        or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in sha.items()
        )
    ):
        raise ValueError(
            f"models[{index}]（{model_id}）sha256 必须是 {{文件名: 哈希}} 对象"
        )

    return ModelEntry(
        id=model_id,
        display_name=str(item.get("display_name") or model_id),
        kind=kind,
        target=target,
        sources=tuple(sources),
        required_files=tuple(required),
        size_mb=float(item.get("size_mb") or 0),
        tier=str(item.get("tier") or "all"),
        sha256=sha,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_repo_downloader(
    source: ModelSource, target: Path, progress: Progress | None
) -> None:
    """repo 快照下载：ModelScope 优先，HuggingFace 备选；进度由库自身打印。"""
    _ = progress
    if source.type == "modelscope":
        from modelscope import snapshot_download

        snapshot_download(
            source.id, revision=source.revision, local_dir=str(target)
        )
        return
    if source.type == "huggingface":
        from huggingface_hub import snapshot_download

        snapshot_download(
            repo_id=source.id, revision=source.revision, local_dir=str(target)
        )
        return
    raise ValueError(f"repo 不支持源类型 {source.type}")


__all__ = [
    "DEFAULT_MANIFEST",
    "MODELS_ENV",
    "ModelEntry",
    "ModelManager",
    "ModelSource",
    "ModelStatus",
    "default_root",
    "load_manifest",
]
