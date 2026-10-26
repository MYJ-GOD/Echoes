"""首启向导的命令面（ADR-011/016）：与壳的唯一接口是 stdout 的 JSON 行。

    echoes-sidecar --setup detect
    echoes-sidecar --setup install-runtime --profile cuda126
    echoes-sidecar --setup install-models
    echoes-sidecar --setup install-models --ids faster-whisper-small

输出（每行一个 JSON，壳逐行转发给前端）::

    {"type":"detect","report":{...}}
    {"type":"progress","step":"models","item":"cosyvoice2-0.5b","pct":42}
    {"type":"result","step":"runtime","ok":true,"report":{...}}
    {"type":"error","step":"runtime","code":"MODEL_NOT_LOADED","message":"..."}

**不复用聊天协议**：聊天面是 hello/state 的冻结契约（3.4），向导是一次性进程，
塞进去只会污染状态机。退出码：成功 0，失败 1。
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from echoes_sidecar import setup
from echoes_sidecar.core.errors import EchoesError


def _emit(payload: dict[str, object]) -> None:
    print(setup.json_line(payload), flush=True)


def _progress(step: str) -> setup.Progress:
    def _tick(item: str, pct: int) -> None:
        _emit({"type": "progress", "step": step, "item": item, "pct": pct})

    return _tick


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    args = [item for item in args if item != "--setup"]
    parser = argparse.ArgumentParser(prog="echoes-sidecar --setup")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("detect", help="硬件/依赖探测")

    runtime_cmd = sub.add_parser("install-runtime", help="下载并激活运行时档案")
    runtime_cmd.add_argument("--profile", default=None)

    models_cmd = sub.add_parser("install-models", help="下载缺失的模型权重")
    models_cmd.add_argument("--ids", default=None, help="逗号分隔；默认全部必需模型")

    parsed, unknown = parser.parse_known_args(args)
    if unknown:
        print(f"[setup] 忽略未知参数：{unknown}", file=sys.stderr)

    try:
        if parsed.action == "detect":
            _emit({"type": "detect", "report": setup.as_dict(setup.detect())})
            return 0

        if parsed.action == "install-runtime":
            report = setup.install_runtime(
                parsed.profile, progress=_progress("runtime")
            )
            _emit(
                {
                    "type": "result",
                    "step": "runtime",
                    "ok": True,
                    "report": setup.as_dict(report),
                }
            )
            return 0

        ids = (
            [item.strip() for item in parsed.ids.split(",") if item.strip()]
            if parsed.ids
            else list(setup.REQUIRED_MODELS)
        )
        detail = setup.install_models(ids, progress=_progress("models"))
        _emit({"type": "result", "step": "models", "ok": True, "detail": detail})
        return 0
    except EchoesError as exc:
        _emit(
            {
                "type": "error",
                "step": parsed.action,
                "code": exc.code.value,
                "message": exc.message,
            }
        )
        return 1
    except Exception as exc:  # noqa: BLE001  向导失败要给前端一句人话，不是栈
        _emit(
            {
                "type": "error",
                "step": parsed.action,
                "code": "INTERNAL_ERROR",
                "message": str(exc),
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
