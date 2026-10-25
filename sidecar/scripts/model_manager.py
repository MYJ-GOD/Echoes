"""7.3 模型管理器 CLI（部署/首启引导）；运行时引擎不联网。

用法（cwd=sidecar）：

    python scripts/model_manager.py list
    python scripts/model_manager.py status bge-small-zh-v1.5
    python scripts/model_manager.py ensure bge-small-zh-v1.5 cosyvoice2-0.5b
    python scripts/model_manager.py verify
    python scripts/model_manager.py list --json

`ensure` 按 manifest 多源下载；repo 走 ModelScope/HuggingFace，file 直链断点续传，
Ollama 走 /api/pull。失败退出码 1（引导页可重试）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(_SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIDECAR_ROOT))

from echoes_sidecar.core.errors import EchoesError  # noqa: E402
from echoes_sidecar.models.manager import ModelManager, ModelStatus  # noqa: E402


def _print_table(statuses: list[ModelStatus]) -> None:
    print(f"{'ID':28} {'状态':8} {'体积':>8}  详情")
    for status in statuses:
        state = "已安装" if status.installed else "缺失"
        size = f"{status.entry.size_mb:.0f}MB"
        print(f"{status.entry.id:28} {state:8} {size:>8}  {status.detail}")


def _as_json(statuses: list[ModelStatus]) -> str:
    return json.dumps(
        [
            {
                "id": status.entry.id,
                "displayName": status.entry.display_name,
                "kind": status.entry.kind,
                "installed": status.installed,
                "path": str(status.path),
                "detail": status.detail,
                "sizeMb": status.entry.size_mb,
                "tier": status.entry.tier,
            }
            for status in statuses
        ],
        ensure_ascii=False,
        indent=2,
    )


def _manager(args: argparse.Namespace) -> ModelManager:
    return ModelManager.load(args.manifest, root=args.root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Echoes 模型管理器（7.3）")
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="模型缓存根（默认 ~/.cache/echoes/models）",
    )
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="列出全部模型状态")
    status_p = sub.add_parser("status", help="查看单个/全部模型")
    status_p.add_argument("model_id", nargs="?")
    ensure_p = sub.add_parser("ensure", help="确保模型可用（必要时下载）")
    ensure_p.add_argument("model_ids", nargs="+")
    sub.add_parser("verify", help="校验全部模型；有缺失则退出 1")

    args = parser.parse_args(argv)
    manager = _manager(args)

    try:
        if args.command == "ensure":
            last: dict[str, int] = {}

            def _progress(model_id: str, pct: int) -> None:
                if pct >= 100 or pct - last.get(model_id, -10) >= 10:
                    last[model_id] = pct
                    print(f"[models] {model_id}: {pct}%", file=sys.stderr)

            for model_id in args.model_ids:
                path = manager.ensure(model_id, _progress)
                print(f"OK {model_id} -> {path}")
            return 0

        if args.command == "status" and args.model_id:
            statuses = [manager.status(args.model_id)]
        else:
            statuses = manager.list_status()

        if args.json:
            print(_as_json(statuses))
        else:
            _print_table(statuses)

        if args.command == "verify" and any(not s.installed for s in statuses):
            return 1
        return 0
    except (KeyError, ValueError, EchoesError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
