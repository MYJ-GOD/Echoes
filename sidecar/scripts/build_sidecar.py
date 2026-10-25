"""构建 sidecar ONEDIR（ADR-011 split-binary；不含 torch/CUDA/模型权重）。

用法（cwd=sidecar）：

    .venv\\Scripts\\python.exe scripts\\build_sidecar.py
    .venv\\Scripts\\python.exe scripts\\build_sidecar.py --smoke

产物：`sidecar/dist/echoes-sidecar/echoes-sidecar.exe`（Windows）。
Tauri `bundle.resources` 把它映射到安装包 `sidecar/`；运行时模型/torch 由
`scripts/model_manager.py` 按档位下载（7.3）。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
WORK = ROOT / "build"
ENTRY = ROOT / "scripts" / "sidecar_entry.py"
NAME = "echoes-sidecar"

# 基础运行时只带契约链（pydantic/websockets/httpx/sqlite-vec）；ML 依赖归运行时包。
EXCLUDES = [
    "torch",
    "torchaudio",
    "transformers",
    "scipy",
    "cosyvoice",
    "matcha",
    "faster_whisper",
    "ctranslate2",
    "modelscope",
    "huggingface_hub",
    "datasets",
    "tokenizers",
    "onnxruntime",
    "librosa",
    "soundfile",
    "matplotlib",
    "pandas",
    "pyarrow",
    "pyworld",
    "diffusers",
    "lightning",
    "gdown",
    "wget",
    "hydra",
    "omegaconf",
    "conformer",
    "x_transformers",
    "inflect",
    "wetext",
    "openai_whisper",
    "tiktoken",
    "av",
]


def _data(source: Path, target: str) -> str:
    return f"{source}{os.pathsep}{target}"


def build() -> Path:
    if not ENTRY.is_file():
        raise SystemExit(f"缺入口脚本：{ENTRY}")
    if DIST.exists():
        shutil.rmtree(DIST)
    if WORK.exists():
        shutil.rmtree(WORK)

    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        NAME,
        "--paths",
        str(ROOT),
        "--distpath",
        str(DIST),
        "--workpath",
        str(WORK),
        "--specpath",
        str(WORK),
        "--collect-submodules",
        "echoes_sidecar",
        "--collect-all",
        "sqlite_vec",
        "--add-data",
        _data(ROOT / "echoes_sidecar" / "models" / "manifest.json", "echoes_sidecar/models"),
        "--add-data",
        _data(
            ROOT / "echoes_sidecar" / "db" / "migrations",
            "echoes_sidecar/db/migrations",
        ),
        "--add-data",
        _data(
            ROOT / "echoes_sidecar" / "engines" / "tts" / "assets",
            "echoes_sidecar/engines/tts/assets",
        ),
    ]
    for module in EXCLUDES:
        args.extend(["--exclude-module", module])
    args.append(str(ENTRY))

    print("[build] " + " ".join(args))
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"PyInstaller 失败（exit={result.returncode}）")

    exe = DIST / NAME / (f"{NAME}.exe" if os.name == "nt" else NAME)
    if not exe.is_file():
        raise SystemExit(f"构建产物缺失：{exe}")
    size_mb = sum(p.stat().st_size for p in (DIST / NAME).rglob("*") if p.is_file()) / 1e6
    print(f"[build] OK {exe}  {size_mb:.1f} MB")
    return exe


def smoke(exe: Path) -> None:
    """冻结 exe 冒烟：mock 引擎 + 临时数据目录，首行必须是 hello。"""
    with tempfile.TemporaryDirectory(prefix="echoes-sidecar-smoke-") as tmp:
        env = os.environ.copy()
        env["ECHOES_DATA_DIR"] = tmp
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(
            [
                str(exe),
                "--llm",
                "mock",
                "--asr",
                "mock",
                "--tts",
                "mock",
                "--ws",
                "auto",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.close()
        deadline = time.time() + 60
        line = ""
        while time.time() < deadline:
            line = proc.stdout.readline()
            if line.strip():
                break
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        if not line:
            err = proc.stderr.read() if proc.stderr is not None else ""
            raise SystemExit(f"冻结 exe 未输出 hello；stderr={err[-800:]}")
        msg = json.loads(line)
        if msg.get("type") != "hello":
            raise SystemExit(f"冻结 exe 首行不是 hello：{line[:200]!r}")
        err = proc.stderr.read() if proc.stderr is not None else ""
        if "ws://127.0.0.1:" not in err:
            raise SystemExit(f"冻结 exe 未启动 WS 音频面；stderr={err[-800:]}")
        print(f"[build] smoke OK: hello protocol={msg.get('protocol_version')} + ws")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建 Echoes sidecar ONEDIR（ADR-011）")
    parser.add_argument("--smoke", action="store_true", help="构建后跑 mock 冒烟")
    args = parser.parse_args(argv)
    exe = build()
    if args.smoke:
        smoke(exe)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
