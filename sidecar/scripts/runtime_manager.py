"""运行时包 CLI（ADR-011）：下载/装/验/看档位；运行时引擎不联网。

用法（cwd=sidecar）：

    python scripts/runtime_manager.py list
    python scripts/runtime_manager.py install cpu --from-bundle D:\\runtime-cpu.zip
    python scripts/runtime_manager.py install cuda126 --url https://... --sha256 <hex>
    python scripts/runtime_manager.py verify cpu
    python scripts/runtime_manager.py list --json

`install` 只解压预构建档案（不在用户机上跑 pip 解析）；装好后写 `active`
指针，冻结版 sidecar 启动时自动注入。失败退出码 1（首启引导可重试）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(_SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIDECAR_ROOT))

from echoes_sidecar import runtime  # noqa: E402

_BUNDLE_HINT = (
    "该档位还没有发布地址。先在构建机生成依赖清单与档案：\n"
    "    python scripts/runtime_manager.py export cpu > build/runtime-cpu.txt\n"
    "    uv pip install --target build/runtime-cpu/site-packages -r build/runtime-cpu.txt\n"
    "    # 压缩 build/runtime-cpu（根目录含 site-packages/），把 url/sha256 填进\n"
    "    # echoes_sidecar/runtime_manifest.json 后，用户机用 install <profile> 即可。"
)

_BUILD_HINT = (
    "构建机下一步：\n"
    "    uv pip install --target build/runtime-<profile>/site-packages -r <清单文件>\n"
    "    # 压缩 build/runtime-<profile>（根目录含 site-packages/）→ 上传 → 回填 url/sha256"
)


def _specs_or_die(manifest: Path | None) -> dict[str, runtime.RuntimeSpec]:
    try:
        return runtime.load_specs(manifest)
    except ValueError as exc:
        print(f"[runtime] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _list(args: argparse.Namespace) -> int:
    specs = _specs_or_die(args.manifest)
    installed = {item.profile: item for item in runtime.installed_profiles(args.root)}
    active = runtime.active_profile(args.root)
    base = (args.root or runtime.default_root()).expanduser()
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": spec.id,
                        "displayName": spec.display_name,
                        "python": spec.python,
                        "platform": spec.platform,
                        "sizeMb": spec.size_mb,
                        "installed": spec.id in installed,
                        "active": spec.id == active,
                        "path": str(base / spec.id),
                    }
                    for spec in specs.values()
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"{'档位':10} {'状态':8} {'体积':>8}  说明")
    for spec in specs.values():
        state = "当前" if spec.id == active else ("已装" if spec.id in installed else "未装")
        print(
            f"{spec.id:10} {state:8} {spec.size_mb:>6.0f}MB  "
            f"{spec.display_name}（Python {spec.python} / {spec.platform}）"
        )
    return 0


def _install(args: argparse.Namespace) -> int:
    specs = _specs_or_die(args.manifest)
    spec = specs.get(args.profile)
    if spec is None:
        print(f"[runtime] 未知档位 {args.profile}；可选 {', '.join(specs)}", file=sys.stderr)
        return 1
    if spec.platform and spec.platform != runtime.platform_tag():
        print(
            f"[runtime] {args.profile} 是 {spec.platform} 档案，当前 {runtime.platform_tag()}"
            "（跨平台装包不支持）",
            file=sys.stderr,
        )
        return 1

    archive: Path | None = Path(args.from_bundle) if args.from_bundle else None
    sha = args.sha256
    if archive is None and args.url:
        source = runtime.BundleSource(url=args.url, sha256=args.sha256)
        print(f"[runtime] 下载 {source.url}", file=sys.stderr)
        archive = runtime.download_bundle(source, progress=_progress(f"下载 {args.profile}"))
    if archive is None:
        for source in spec.bundles:
            if not source.url:
                continue
            print(f"[runtime] 下载 {source.url}", file=sys.stderr)
            archive = runtime.download_bundle(
                source, progress=_progress(f"下载 {args.profile}")
            )
            sha = sha or source.sha256
            break
    if archive is None:
        print(_BUNDLE_HINT, file=sys.stderr)
        return 1

    try:
        layout = runtime.install_bundle(
            archive,
            args.profile,
            root=args.root,
            force=args.force,
            expected_sha256=sha,
            spec=spec,
        )
    except (FileExistsError, FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"[runtime] 安装失败：{exc}", file=sys.stderr)
        return 1
    print(
        f"[runtime] 已安装 {layout.profile} → {layout.site_packages}"
        f"（{layout.installed.installed_at}）"
    )
    print("[runtime] 下一步：python scripts/runtime_manager.py verify " + layout.profile)
    return 0


def _verify(args: argparse.Namespace) -> int:
    layout = runtime.active_layout(args.root)
    if layout is None:
        print("[runtime] 没有已安装的运行时", file=sys.stderr)
        return 1
    if args.profile and layout.profile != args.profile:
        print(
            f"[runtime] 当前档位是 {layout.profile}，不是 {args.profile}"
            "（用 ECHOES_RUNTIME_PROFILE 指定）",
            file=sys.stderr,
        )
        return 1
    runtime.inject(root=args.root, force=True)
    failures = runtime.verify(layout)
    if failures:
        for item in failures:
            print(f"[runtime] 导入失败 {item}", file=sys.stderr)
        return 1
    print(f"[runtime] {layout.profile} 全部模块导入正常")
    return 0


def _export(args: argparse.Namespace) -> int:
    """把某档依赖导成 pip requirements（含 torch 索引），构建机据此产出档案。"""
    specs = _specs_or_die(args.manifest)
    spec = specs.get(args.profile)
    if spec is None:
        print(f"[runtime] 未知档位 {args.profile}；可选 {', '.join(specs)}", file=sys.stderr)
        return 1
    lines: list[str] = []
    if spec.index_url:
        lines.append(f"--index-url {spec.index_url}")
    if spec.extra_index_url:
        lines.append(f"--extra-index-url {spec.extra_index_url}")
    lines.extend(spec.requirements)
    text = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"[runtime] 已写出 {args.output}", file=sys.stderr)
    else:
        print(text, end="")
    if args.hint:
        print(_BUILD_HINT, file=sys.stderr)
    return 0


def _progress(label: str) -> runtime.Progress:
    last = -1

    def _tick(pct: int) -> None:
        nonlocal last
        if pct >= last + 10:
            last = pct
            print(f"[runtime] {label} {pct}%", file=sys.stderr)

    return _tick


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Echoes 运行时包管理器（ADR-011）")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--root", type=Path, default=None, help="运行时根（默认 ~/.cache/echoes/runtime）"
    )
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="列出档位与安装状态").set_defaults(func=_list)

    install = sub.add_parser("install", help="从预构建档案安装")
    install.add_argument("profile")
    install.add_argument("--from-bundle", type=Path, default=None)
    install.add_argument("--url", default=None)
    install.add_argument("--sha256", default=None)
    install.add_argument("--force", action="store_true")
    install.set_defaults(func=_install)

    verify = sub.add_parser("verify", help="逐个 import 自检当前档位")
    verify.add_argument("profile", nargs="?")
    verify.set_defaults(func=_verify)

    export = sub.add_parser("export", help="导出该档位的 pip requirements（构建机用）")
    export.add_argument("profile")
    export.add_argument("--output", type=Path, default=None)
    export.add_argument("--hint", action="store_true", help="附构建档案的步骤说明")
    export.set_defaults(func=_export)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
