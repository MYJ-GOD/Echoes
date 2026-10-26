"""构建运行时档案（ADR-011）：按档位装依赖 → 打 zip → 给出 manifest 片段。

用法（cwd=sidecar）：

    # 1) 构建（耗时与体积都大：CPU ~1.2GB / CUDA ~3.5GB）
    .venv\\Scripts\\python.exe scripts\\build_runtime_bundle.py --profile cpu

    # 2) 上传 zip，把打印出的 url/sha256 回填 echoes_sidecar/runtime_manifest.json

    # 3) 本机先验证（file:// 支持离线档案）
    .venv\\Scripts\\python.exe scripts\\runtime_manager.py install cpu \\
        --url file:///D:/dist/runtime/runtime-cpu-win_amd64.zip
    .venv\\Scripts\\python.exe scripts\\runtime_manager.py verify cpu

**为什么不在用户机上跑 pip**：解析/构建隔离/证书全要另造，且用户机没有编译工具链。
档案是 CI/构建机的产物，用户机只下载+解压（ADR-011 补充）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(_SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIDECAR_ROOT))

from echoes_sidecar import runtime  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _requirements(spec: runtime.RuntimeSpec, target: Path) -> Path:
    lines: list[str] = []
    if spec.index_url:
        lines.append(f"--index-url {spec.index_url}")
    if spec.extra_index_url:
        lines.append(f"--extra-index-url {spec.extra_index_url}")
    lines.extend(spec.requirements)
    path = target / "requirements.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _install(spec: runtime.RuntimeSpec, site: Path, python: Path) -> None:
    staging = site.parent
    # cwd 会切到 staging，参数必须绝对路径，否则 -r 相对路径解析错位
    reqs = _requirements(spec, staging).resolve()
    site = site.resolve()
    command = [
        "uv",
        "pip",
        "install",
        "--target",
        str(site),
        "--python",
        str(python),
        # 少数纯 Python 依赖只有 sdist（antlr4-python3-runtime 等），不能强制 wheel
        "--no-compile",
        "--index-strategy",
        "unsafe-best-match",
        "-r",
        str(reqs),
    ]
    print("[bundle] " + " ".join(command), flush=True)
    started = time.time()
    result = subprocess.run(command, cwd=staging)
    if result.returncode != 0:
        raise SystemExit(f"uv pip install 失败（exit={result.returncode}）")
    print(f"[bundle] 依赖安装完成，用时 {time.time() - started:.0f}s", flush=True)


def _zip(site: Path, out: Path) -> None:
    total = sum(p.stat().st_size for p in site.rglob("*") if p.is_file())
    print(f"[bundle] 打包 {total / 1e9:.2f} GB → {out.name}", flush=True)
    started = time.time()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(site.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(site.parent).as_posix())
    print(f"[bundle] 打包完成，用时 {time.time() - started:.0f}s", flush=True)


def build(profile: str, *, out_dir: Path, python: Path, keep: bool) -> Path:
    spec = runtime.load_specs().get(profile)
    if spec is None:
        raise SystemExit(f"未知档位 {profile}（可选 cpu / cuda126）")
    if spec.platform != runtime.platform_tag():
        raise SystemExit(
            f"{profile} 是 {spec.platform} 档案，当前 {runtime.platform_tag()}；不支持交叉构建"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    staging = out_dir / f".staging-{profile}-{int(time.time())}"
    site = staging / "site-packages"
    site.mkdir(parents=True)
    try:
        _install(spec, site, python)
        target = out_dir / f"runtime-{profile}-{spec.platform}.zip"
        if target.exists():
            target.unlink()
        _zip(site, target)
    finally:
        if not keep:
            shutil.rmtree(staging, ignore_errors=True)

    digest = _sha256(target)
    size_mb = round(target.stat().st_size / 1e6, 1)
    report = {
        "profile": profile,
        "platform": spec.platform,
        "python": spec.python,
        "file": target.name,
        "sha256": digest,
        "size_mb": size_mb,
        "manifest_patch": {
            "profiles": {
                profile: {
                    "bundles": [
                        {"url": "<上传后填这里>", "sha256": digest}
                    ]
                }
            }
        },
    }
    (out_dir / f"runtime-{profile}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[bundle] OK {target}  {size_mb:.1f} MB")
    print(f"[bundle] sha256 {digest}")
    print("[bundle] 把 url + sha256 回填 runtime_manifest.json；本机可先用 file:// 验证：")
    print(
        "  .venv\\Scripts\\python.exe scripts\\runtime_manager.py install "
        f"{profile} --url {target.absolute().as_uri()}"
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建 Echoes 运行时档案（ADR-011）")
    parser.add_argument("--profile", required=True, choices=["cpu", "cuda126"])
    parser.add_argument(
        "--out",
        type=Path,
        default=_SIDECAR_ROOT.parent / "tmp" / "runtime",
        help="输出目录（默认仓库 tmp/runtime；不要放 sidecar/dist，会被 ONEDIR 构建清空）",
    )
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--keep", action="store_true", help="保留解压后的 site-packages")
    args = parser.parse_args(argv)
    build(
        args.profile,
        out_dir=args.out,
        python=args.python,
        keep=args.keep,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
