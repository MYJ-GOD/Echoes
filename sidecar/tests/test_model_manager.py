"""7.3 模型管理器：manifest 校验、repo 多源、file sha/续传、Ollama 复用。"""

from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError
from echoes_sidecar.models.manager import (
    ModelEntry,
    ModelManager,
    ModelSource,
    load_manifest,
)

PAYLOAD = b"echoes-model-payload-0123456789"


def _entry(
    *,
    kind: str = "repo",
    target: str = "m",
    sources: tuple[ModelSource, ...] | None = None,
    required: tuple[str, ...] = ("config.json",),
    sha: dict[str, str] | None = None,
) -> ModelEntry:
    return ModelEntry(
        id="m",
        display_name="测试模型",
        kind=kind,  # type: ignore[arg-type]
        target=target,
        sources=sources or (ModelSource(type="huggingface", id="org/repo"),),
        required_files=required,
        size_mb=1.0,
        tier="all",
        sha256=sha,
    )


def test_default_manifest_has_core_models() -> None:
    entries = load_manifest()
    ids = {entry.id for entry in entries}
    assert {"bge-small-zh-v1.5", "cosyvoice2-0.5b", "faster-whisper-small", "qwen3-8b"} <= ids
    assert all(entry.sources for entry in entries if entry.kind != "ollama")


def test_manifest_rejects_duplicate_id_and_path_traversal(tmp_path: Path) -> None:
    dup = tmp_path / "dup.json"
    dup.write_text(
        json.dumps(
            {
                "models": [
                    {"id": "x", "kind": "repo", "target": "x", "required_files": [],
                     "sources": [{"type": "huggingface", "id": "a/b"}]},
                    {"id": "x", "kind": "repo", "target": "y", "required_files": [],
                     "sources": [{"type": "huggingface", "id": "a/b"}]},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        ModelManager.load(dup, root=tmp_path / "root")

    escape = tmp_path / "escape.json"
    escape.write_text(
        json.dumps(
            {
                "models": [
                    {"id": "x", "kind": "repo", "target": "../x", "required_files": [],
                     "sources": [{"type": "huggingface", "id": "a/b"}]}
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_manifest(escape)


def test_repo_sources_fallback(tmp_path: Path) -> None:
    attempts: list[str] = []

    def downloader(source: ModelSource, target: Path, progress: object) -> None:
        _ = progress
        attempts.append(str(source.id))
        if source.id == "bad":
            raise RuntimeError("源不可用")
        target.mkdir(parents=True, exist_ok=True)
        (target / "config.json").write_text("{}", encoding="utf-8")

    entry = _entry(
        sources=(
            ModelSource(type="modelscope", id="bad"),
            ModelSource(type="huggingface", id="good"),
        )
    )
    manager = ModelManager([entry], root=tmp_path, repo_downloader=downloader)

    assert manager.status("m").installed is False
    path = manager.ensure("m")
    assert (path / "config.json").is_file()
    assert manager.status("m").installed is True
    assert attempts == ["bad", "good"]


def test_repo_all_sources_fail_is_model_not_loaded(tmp_path: Path) -> None:
    def downloader(source: ModelSource, target: Path, progress: object) -> None:
        _ = (source, target, progress)
        raise RuntimeError("down")

    manager = ModelManager([_entry()], root=tmp_path, repo_downloader=downloader)
    with pytest.raises(EchoesError):
        manager.ensure("m")


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/asset.bin", "/other.bin"}:
            self.send_error(404)
            return
        start = 0
        header = self.headers.get("Range")
        if header:
            start = int(header.split("=")[1].split("-")[0])
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}")
        else:
            self.send_response(200)
        body = PAYLOAD[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # 静默测试服务器
        return


@pytest.fixture
def http_base() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_file_download_and_sha(tmp_path: Path, http_base: str) -> None:
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    entry = _entry(
        kind="file",
        target="asset.bin",
        sources=(ModelSource(type="url", url=f"{http_base}/asset.bin"),),
        required=(),
        sha={"asset.bin": digest},
    )
    manager = ModelManager([entry], root=tmp_path)

    path = manager.ensure("m")

    assert path.read_bytes() == PAYLOAD
    assert manager.status("m").installed is True


def test_file_sha_mismatch_rejects(tmp_path: Path, http_base: str) -> None:
    entry = _entry(
        kind="file",
        target="asset.bin",
        sources=(ModelSource(type="url", url=f"{http_base}/asset.bin"),),
        required=(),
        sha={"asset.bin": "0" * 64},
    )
    manager = ModelManager([entry], root=tmp_path)

    with pytest.raises(EchoesError):
        manager.ensure("m")
    assert not (tmp_path / "asset.bin").exists()


def test_file_resume_from_part(tmp_path: Path, http_base: str) -> None:
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    part = tmp_path / ".asset.bin.part"
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(PAYLOAD[: len(PAYLOAD) // 2])

    entry = _entry(
        kind="file",
        target="asset.bin",
        sources=(ModelSource(type="url", url=f"{http_base}/asset.bin"),),
        required=(),
        sha={"asset.bin": digest},
    )
    path = ModelManager([entry], root=tmp_path).ensure("m")
    assert path.read_bytes() == PAYLOAD


def test_ollama_reuse_and_pull(tmp_path: Path) -> None:
    names: list[str] = []
    entry = _entry(
        kind="ollama", target="qwen3:8b", sources=(), required=()
    )
    manager = ModelManager(
        [entry],
        root=tmp_path,
        ollama_list=lambda: list(names),
        ollama_pull=lambda name, progress: names.append(name),
    )
    assert manager.status("m").installed is False
    manager.ensure("m")
    assert names == ["qwen3:8b"]
    assert manager.status("m").installed is True
