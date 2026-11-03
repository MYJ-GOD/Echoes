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
    # soundfile 不再排除：R2a 2.14 的云端 TTS mp3/ogg 解码要它（libsndfile DLL
    # 随 --collect-all soundfile 一起打进去，约 2MB；scipy 仍归运行时包，
    # 重采样退回线性插值）。
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
    # 纯开发/可选依赖：被静态分析带进包会把运行时里的完整副本挡在 PYZ 后面，
    # 且 sidecar 自己一行都没用到（实测 rich 的残缺副本让 CosyVoice2 缺 rich.tree）。
    "rich",
    "pygments",
    "mypy",
]


def _data(source: Path, target: str) -> str:
    return f"{source}{os.pathsep}{target}"


def _stdlib_hidden_imports() -> list[str]:
    """运行时（torch/transformers）动态 import 的 stdlib 清单（见同名 txt）。"""
    manifest = ROOT / "scripts" / "stdlib_hidden_imports.txt"
    if not manifest.is_file():
        return []
    modules: list[str] = []
    for raw in manifest.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            modules.append(line)
    return modules


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
        # R2a 2.14：libsndfile 二进制在 soundfile/_soundfile_data，必须收全
        "--collect-all",
        "soundfile",
        # jieba 的词典是数据文件；不收集则冻结版 tokens 为空
        "--collect-data",
        "jieba",
        # 凭据后端是动态发现的：不显式收集，冻结版会在 import keyring 时缺 backend
        "--collect-submodules",
        "keyring.backends",
        "--collect-submodules",
        "win32ctypes",
        "--hidden-import",
        "keyring.backends.Windows",
        "--add-data",
        _data(ROOT / "echoes_sidecar" / "models" / "manifest.json", "echoes_sidecar/models"),
        "--add-data",
        _data(
            ROOT / "echoes_sidecar" / "runtime_manifest.json",
            "echoes_sidecar",
        ),
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
        # vendored CosyVoice2 源码（ADR-014）：_ensure_vendor_boot 按
        # `_MEIPASS/vendor/cosyvoice2` 解析；排除 --exclude-module 只是不做静态分析。
        "--add-data",
        _data(ROOT / "vendor" / "cosyvoice2", "vendor/cosyvoice2"),
        # 稳定 ABI 转发 DLL：tokenizers 这类 Py_LIMITED_API 扩展开在冻结版里找不到它
        # （dev 有 base Python 的 python3.dll 在 PATH 上，所以只会在安装包现形）。
        *(
            ["--add-binary", _data(Path(sys.base_prefix) / "python3.dll", ".")]
            if (Path(sys.base_prefix) / "python3.dll").is_file()
            else []
        ),
    ]
    for module in EXCLUDES:
        args.extend(["--exclude-module", module])
    for module in _stdlib_hidden_imports():
        args.extend(["--hidden-import", module])
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
