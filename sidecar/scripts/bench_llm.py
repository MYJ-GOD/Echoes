"""阶段 -1 对话质量基准 CLI（文档 6/阶段 -1、§12 步骤 3）。

子命令：
  run     跑被测 provider 输出 replies.jsonl（--provider mock|ollama|openai）
  judge   独立强模型按要点清单打分（LLM-as-judge，入库 prompt 复现）
  human   生成人工 1-5 分评分表模板（human_scores.csv，本人填写）
  report  汇总：命中率 / 延迟 P50 / 双通道分歧表 → summary.json

用法示例（本机，cwd=sidecar）：
  run   --provider ollama --model qwen2.5:7b-instruct
  judge --provider openai --model deepseek-chat --replies <replies.jsonl 路径>
（本机工具：不进 CI；结果提交 docs/benchmarks/results/）
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any

# 直跑引导：scripts/ 不是包，把 sidecar/ 根（bench 包所在目录）加入 sys.path
_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(_SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIDECAR_ROOT))

from bench import scenarios as bench_scenarios  # noqa: E402
from bench import scoring  # noqa: E402
from bench.client import OllamaClient, OpenAICompatClient  # noqa: E402
from bench.runner import ProviderClient, run_judge_channel, run_scenarios  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = REPO_ROOT / "docs" / "benchmarks" / "results"
JUDGE_PROMPT_PATH = REPO_ROOT / "docs" / "benchmarks" / "judge_prompt.md"


class _MockProvider:
    """零依赖回路（pipeline 自检/CI 冒烟）：回复恒定，指标为占位值。"""

    def __init__(self, tag: str) -> None:
        self._tag = tag

    async def chat(
        self, context: list[dict[str, str]], user: str, *, model: str
    ) -> dict[str, Any]:
        return {
            "reply": f"[{self._tag}] 这是 mock 回复（流程自检用）。",
            "first_token_ms": 10,
            "tok_s": 100.0,
            "model": model,
        }


class _MockJudge:
    """judge 通道零依赖 mock：按 payload 要点数生成全命中 JSON（链路自检用）。"""

    async def chat(
        self, context: list[dict[str, str]], user: str, *, model: str
    ) -> dict[str, Any]:
        payload = json.loads(user)
        points = [
            {"id": f"{payload['scenario_id']}-{i + 1}", "hit": True, "evidence": "自检"}
            for i in range(len(payload.get("expect_points", [])))
        ]
        reply = json.dumps(
            {"score": 4, "points": points, "rationale": "mock 链路自检"},
            ensure_ascii=False,
        )
        return {"reply": reply, "first_token_ms": 10, "tok_s": 100.0, "model": model}


def _make_provider(name: str, model: str | None, base_url: str | None) -> ProviderClient:
    if name == "mock":
        return _MockProvider("mock")
    if name == "ollama":
        return OllamaClient(base_url=base_url or "http://127.0.0.1:11434")
    if name == "openai":
        return OpenAICompatClient(base_url=base_url or "https://api.deepseek.com")
    raise SystemExit(f"未知 provider: {name}（候选 mock|ollama|openai）")


def _slug(provider: str, model: str) -> str:
    return f"{provider}-{model.replace(':', '-')}"


def cmd_run(args: argparse.Namespace) -> int:
    data = bench_scenarios.load()
    model = args.model or ("mock" if args.provider == "mock" else None)
    if not model:
        raise SystemExit("run 需要 --model")
    out_dir = RESULTS_ROOT / _slug(args.provider, model)
    provider = _make_provider(args.provider, model, args.base_url)
    records = asyncio.run(
        run_scenarios(provider, data, model=model, out_path=out_dir / "replies.jsonl")
    )
    print(f"run 完成：{len(records)} 轮 → {out_dir / 'replies.jsonl'}")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    data = bench_scenarios.load()
    replies_path = Path(args.replies)
    out_path = replies_path.parent / "judge_scores.jsonl"
    judge: ProviderClient
    if args.provider == "mock":
        judge = _MockJudge()
    else:
        judge = _make_provider(args.provider, args.model, args.base_url)
    rows = asyncio.run(
        run_judge_channel(
            judge,
            data,
            replies_path=replies_path,
            judge_prompt=JUDGE_PROMPT_PATH.read_text(encoding="utf-8"),
            model=args.model or "mock",
            out_path=out_path,
        )
    )
    print(f"judge 完成：{len(rows)} 轮 → {out_path}")
    return 0


def cmd_human(args: argparse.Namespace) -> int:
    """生成本人 1-5 分评分表模板（Excel 友好编码）。"""
    replies_path = Path(args.replies)
    out_path = replies_path.parent / "human_scores.csv"
    with replies_path.open(encoding="utf-8") as src, out_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as dst:
        writer = csv.writer(dst)
        writer.writerow(["scenario_id", "score", "notes"])
        for line in src:
            if line.strip():
                writer.writerow([json.loads(line)["scenario_id"], "", ""])
    print(f"模板已生成：{out_path}（1-5 分逐轮填写 notes 记录；分歧 ≥2 详见 report）")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    result_dir = Path(args.dir)
    judge_path = result_dir / "judge_scores.jsonl"
    judge_rows = [
        json.loads(line)
        for line in judge_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    replies_rows: list[dict[str, Any]] = []
    replies_path = result_dir / "replies.jsonl"
    if replies_path.exists():
        replies_rows = [
            json.loads(line)
            for line in replies_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    usable = scoring.join_latency(judge_rows, replies_rows)
    failed = sum(1 for r in judge_rows if r.get("error"))
    summary: dict[str, Any] = {**scoring.aggregate(usable), "judge_n": len(judge_rows)}
    if failed:
        summary["judge_parse_errors"] = failed

    human_path = result_dir / "human_scores.csv"
    if human_path.exists():
        with human_path.open(encoding="utf-8-sig") as f:
            human_rows = [
                {"scenario_id": r["scenario_id"], "score": int(r["score"])}
                for r in csv.DictReader(f)
                if r["score"].strip()
            ]
        summary["human_n"] = len(human_rows)
        summary["divergences"] = scoring.divergences(
            judge_rows, human_rows, threshold=args.threshold
        )
    (result_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"→ {result_dir / 'summary.json'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="阶段 -1 对话质量基准")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run")
    run.add_argument("--provider", choices=["mock", "ollama", "openai"], required=True)
    run.add_argument("--model", default=None)
    run.add_argument("--base-url", default=None)

    judge = sub.add_parser("judge")
    judge.add_argument("--provider", choices=["mock", "ollama", "openai"], required=True)
    judge.add_argument("--model", default=None)
    judge.add_argument("--base-url", default=None)
    judge.add_argument("--replies", required=True)

    human = sub.add_parser("human")
    human.add_argument("--replies", required=True)

    report = sub.add_parser("report")
    report.add_argument("--dir", required=True)
    report.add_argument("--threshold", type=int, default=2)

    args = parser.parse_args()
    handlers = {"run": cmd_run, "judge": cmd_judge, "human": cmd_human, "report": cmd_report}
    return int(handlers[args.command](args))


if __name__ == "__main__":
    sys.exit(main())
