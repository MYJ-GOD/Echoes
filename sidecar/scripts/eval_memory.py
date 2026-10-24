"""13.3 记忆抽取评测门禁（CLI）。

用法（cwd=sidecar）：

    .venv\\Scripts\\python.exe scripts\\eval_memory.py --provider ollama
    .venv\\Scripts\\python.exe scripts\\eval_memory.py --provider scripted  # 只验证评测管线

`scripted` 用评测集自身的期望输出喂给抽取器，**不是质量证据**；真正的 13.3 门禁
必须用 `--provider ollama`（需要 11434 与本机模型）。低于阈值时退出码 1。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(_SIDECAR_ROOT) not in sys.path:  # 脚本直跑：把 sidecar/ 放进 import 根
    sys.path.insert(0, str(_SIDECAR_ROOT))

from echoes_sidecar.memory.eval import (  # noqa: E402
    DEFAULT_CASES,
    EvalReport,
    evaluate,
    gate_failures,
    load_cases,
)
from echoes_sidecar.memory.extractor import MemoryExtractor  # noqa: E402


class ScriptedLLM:
    """按评测集 transcript 回放期望 JSON：只验证解析/指标/门禁，不测模型质量。"""

    def __init__(self, replies: dict[str, str]) -> None:
        self._replies = replies

    @property
    def name(self) -> str:
        return "scripted"

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        _ = (stream, max_tokens, temperature)
        content = messages[-1]["content"]
        for transcript, reply in self._replies.items():
            if transcript in content:
                yield reply
                return
        yield "[]"


def _print_report(report: EvalReport, failures: list[str], *, provider: str) -> None:
    print("记忆抽取评测（13.3）")
    print(f"  provider : {provider}")
    print(f"  cases    : {len(report.cases)}")
    print(f"  precision: {report.precision:.3f}  (TP={report.tp} FP={report.fp})")
    print(f"  recall   : {report.recall:.3f}  (FN={report.fn})")
    print(
        "  replace  : "
        f"{report.replacement_accuracy:.3f} "
        f"({report.replacement_ok}/{report.replacement_total})"
    )
    if report.errors:
        print("  错误：")
        for error in report.errors:
            print(f"    - {error}")
    if failures:
        print("  gate     : FAIL")
        for failure in failures:
            print(f"    - {failure}")
        print("  失败用例：")
        for case in report.cases:
            if case.fp or case.fn or case.error or (
                case.replacement_total and case.replacement_ok < case.replacement_total
            ):
                print(f"    [{case.case_id}]")
                print(f"      expected : {list(case.expected)}")
                print(f"      predicted: {list(case.predicted)}")
    else:
        print("  gate     : PASS")


async def _run(args: argparse.Namespace) -> int:
    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("评测集为空", file=sys.stderr)
        return 2

    llm: ScriptedLLM | object
    if args.provider == "scripted":
        replies = {
            str(case["transcript"]): json.dumps(
                case.get("expected", []), ensure_ascii=False
            )
            for case in cases
        }
        llm = ScriptedLLM(replies)
        print(
            "⚠ scripted 只验证评测管线，不是模型质量证据；真门禁用 --provider ollama",
            file=sys.stderr,
        )
    else:
        from echoes_sidecar.engines.llm.ollama import OllamaLLMProvider

        llm = OllamaLLMProvider(model=args.model, think=False)

    extractor = MemoryExtractor(llm, privacy_mode=True)  # type: ignore[arg-type]
    try:
        report = await evaluate(extractor, cases)
    finally:
        aclose = getattr(llm, "aclose", None)
        if aclose is not None:
            await aclose()

    failures = gate_failures(report)
    _print_report(report, failures, provider=args.provider)
    return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="13.3 记忆抽取评测门禁")
    parser.add_argument("--provider", choices=["scripted", "ollama"], default="scripted")
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条（调试用）")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
