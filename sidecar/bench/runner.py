"""Runner 流程编排：跑题 → replies.jsonl；judge 通道 → judge_scores.jsonl。

导出协议（每行一轮，UTF-8 JSONL，report 与人工评分表消费）：
  replies.jsonl     {scenario_id, category, model, reply, first_token_ms, tok_s, ts}
  judge_scores.jsonl {scenario_id, judge_model, score, hit_ratio, points_hit, ts}
                      解析失败轮：score/hit_ratio=None + error(raw 截断 500)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Protocol

from bench.scoring import extract_first_json, hit_ratio


class ProviderClient(Protocol):
    """最小 provider 协议：真实 HTTP 客户端与测试 Fake 同签名。"""

    async def chat(
        self, context: list[dict[str, str]], user: str, *, model: str
    ) -> dict[str, Any]: ...


async def run_scenarios(
    provider: ProviderClient,
    scenarios: dict[str, Any],
    *,
    model: str,
    out_path: Path,
) -> list[dict[str, Any]]:
    """对全部场景跑被测 provider，一行一轮写 replies.jsonl，返回记录列表。"""
    records: list[dict[str, Any]] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for scenario in scenarios["scenarios"]:
            result = await provider.chat(
                scenario.get("context", []),
                scenario["user"],
                model=model,
            )
            row = {
                "scenario_id": scenario["id"],
                "category": scenario["category"],
                "model": result.get("model", model),
                "reply": result["reply"],
                "first_token_ms": result.get("first_token_ms"),
                "tok_s": result.get("tok_s"),
                "ts": int(time.time()),
            }
            records.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return records


async def run_judge_channel(
    judge_client: ProviderClient,
    scenarios: dict[str, Any],
    *,
    replies_path: Path,
    judge_prompt: str,
    model: str,
    out_path: Path,
) -> list[dict[str, Any]]:
    """独立强模型按要点清单打分（LLM-as-judge，温度 0）；回复解析容错。"""
    scenario_by_id = {s["id"]: s for s in scenarios["scenarios"]}
    rows: list[dict[str, Any]] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with replies_path.open(encoding="utf-8") as src, out_path.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            reply_row = json.loads(line)
            scenario = scenario_by_id[reply_row["scenario_id"]]
            payload = {
                "scenario_id": scenario["id"],
                "user_message": scenario["user"],
                "context": scenario.get("context", []),
                "expect_points": [p["text"] for p in scenario["expect_points"]],
                "notes": scenario.get("notes", ""),
                "candidate_reply": reply_row["reply"],
            }
            result = await judge_client.chat(
                [{"role": "system", "content": judge_prompt}],
                json.dumps(payload, ensure_ascii=False),
                model=model,
            )
            # 解析容错：judge 偶发不守输出格式时该轮记 failure（不中断批跑，report 可见）
            raw = result["reply"]
            row: dict[str, Any] = {
                "scenario_id": reply_row["scenario_id"],
                "judge_model": result.get("model", model),
                "score": None,
                "hit_ratio": None,
                "points_hit": {},
                "error": None,
                "raw": None,
            }
            try:
                parsed = extract_first_json(raw)
            except ValueError as exc:
                row["error"] = str(exc)
                row["raw"] = raw[:500]
            else:
                row["score"] = parsed.get("score")
                row["hit_ratio"] = hit_ratio(parsed)
                row["points_hit"] = {
                    str(p.get("id")): bool(p.get("hit")) for p in parsed.get("points", [])
                }
            row["ts"] = int(time.time())
            rows.append(row)
            dst.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows
