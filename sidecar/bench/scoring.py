"""评分纯函数：要点命中率 / judge 输出容错解析 / 双通道分歧 / 汇总。"""
from __future__ import annotations

import json
import statistics
from typing import Any


def extract_first_json(text: str) -> dict[str, Any]:
    """从模型回复中抽出第一个平衡 JSON 对象（容错：前置闲话/代码栏）。"""
    decoder = json.JSONDecoder()
    idx = text.find("{")
    while idx != -1:
        try:
            obj, _end = decoder.raw_decode(text[idx:])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
        idx = text.find("{", idx + 1)
    raise ValueError("回复中未找到 JSON 对象")


def hit_ratio(judge: dict[str, Any]) -> float:
    """主指标：要点命中率 = 命中要点数 / 总要点数；空清单=0.0。"""
    points = judge.get("points")
    if not isinstance(points, list) or not points:
        return 0.0
    hits = sum(1 for p in points if isinstance(p, dict) and p.get("hit") is True)
    return hits / len(points)


def divergences(
    judge_rows: list[dict[str, Any]],
    human_rows: list[dict[str, Any]],
    *, threshold: int = 2,
) -> list[dict[str, Any]]:
    """双通道分歧：|judge 评分 - 人工评分| ≥ threshold 的轮次（由本人终审仲裁）。"""
    human_by_id = {r["scenario_id"]: r["score"] for r in human_rows}
    flagged: list[dict[str, Any]] = []
    for row in judge_rows:
        sid = row["scenario_id"]
        if sid in human_by_id and abs(row["score"] - human_by_id[sid]) >= threshold:
            flagged.append(
                {"scenario_id": sid, "judge": row["score"], "human": human_by_id[sid]}
            )
    return flagged


def _p50(values: list[float], default: float | None = None) -> float | None:
    """P50 = 中位数；无有效样本时取 default（None 表示该辅指标缺测）。"""
    if not values:
        return default
    return statistics.median(values)


def join_latency(
    judge_rows: list[dict[str, Any]],
    replies_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """report 汇总输入构造：replies 的首 token/吞吐按 scenario_id 并进 judge 行。

    judge 缺席的 replies 行丢弃；replies 缺席（旧数据）的 judge 行延迟为 None。
    """
    latency = {r["scenario_id"]: (r.get("first_token_ms"), r.get("tok_s")) for r in replies_rows}
    return [
        {
            "scenario_id": j["scenario_id"],
            "hit_ratio": j.get("hit_ratio"),
            "first_token_ms": latency.get(j["scenario_id"], (None, None))[0],
            "tok_s": latency.get(j["scenario_id"], (None, None))[1],
        }
        for j in judge_rows
    ]


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总：命中率均值 + 延迟/吞吐 P50（缺测字段自动跳过）。"""
    first_tokens = [r["first_token_ms"] for r in rows if r.get("first_token_ms") is not None]
    tok_s = [r["tok_s"] for r in rows if r.get("tok_s") is not None]
    hit_ratios = [r["hit_ratio"] for r in rows if r.get("hit_ratio") is not None]
    return {
        "n": len(rows),
        "mean_hit_ratio": round(sum(hit_ratios) / len(hit_ratios), 4) if hit_ratios else None,
        "p50_first_token_ms": _p50([float(v) for v in first_tokens]),
        "p50_tok_s": _p50([float(v) for v in tok_s]),
    }
