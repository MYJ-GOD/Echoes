"""评分纯函数（阶段 -1）：要点命中率 / 双通道分歧 / judge 输出容错解析。

协议（docs/benchmarks/README.md）：
- 主指标 = judge 要点命中率（hit/total）；辅指标 = 首 token 延迟、tok/s。
- 双通道 = judge(1-5) + 人工(1-5)；|背离| ≥2 的轮次由本人终审仲裁。
"""
from __future__ import annotations

import pytest

from bench.scoring import (
    aggregate,
    divergences,
    extract_first_json,
    hit_ratio,
)


def test_hit_ratio_full() -> None:
    judge = {"points": [{"hit": True}, {"hit": True}, {"hit": True}]}
    assert hit_ratio(judge) == 1.0


def test_hit_ratio_partial_and_empty() -> None:
    assert hit_ratio({"points": [{"hit": True}, {"hit": False}]}) == 0.5
    assert hit_ratio({"points": []}) == 0.0
    assert hit_ratio({}) == 0.0


def test_extract_first_json_tolerates_prose() -> None:
    """judge 模型回复带前言/代码栏时仍能抽出 JSON（容错解析）。"""
    noisy = '好的，以下是评分。\n```json\n{"score": 4, "points": [{"hit": true}]}\n```'
    assert extract_first_json(noisy) == {"score": 4, "points": [{"hit": True}]}


def test_extract_first_json_rejects_when_absent() -> None:
    with pytest.raises(ValueError):
        extract_first_json("这段回复没有 JSON")


def test_divergences_threshold_two() -> None:
    judge_rows = [
        {"scenario_id": "P01", "score": 5},
        {"scenario_id": "P02", "score": 3},
        {"scenario_id": "P03", "score": 4},
    ]
    human_rows = [
        {"scenario_id": "P01", "score": 5},  # 一致
        {"scenario_id": "P02", "score": 5},  # |Δ|=2 → 仲裁
        {"scenario_id": "P03", "score": 1},  # |Δ|=3 → 仲裁
    ]
    flagged = divergences(judge_rows, human_rows, threshold=2)
    assert [row["scenario_id"] for row in flagged] == ["P02", "P03"]
    assert flagged[0]["judge"] == 3 and flagged[0]["human"] == 5


def test_aggregate_summary_metrics() -> None:
    rows = [
        {"scenario_id": "P01", "hit_ratio": 1.0, "first_token_ms": 200, "tok_s": 30.0},
        {"scenario_id": "P02", "hit_ratio": 0.5, "first_token_ms": 400, "tok_s": 20.0},
    ]
    summary = aggregate(rows)
    assert summary["mean_hit_ratio"] == 0.75
    assert summary["p50_first_token_ms"] == 300  # 200/400 的中位（偶数取高半值规则见实现）
    assert summary["p50_tok_s"] == 25.0


def test_join_latency_merges_results_into_judge_rows() -> None:
    """report 汇总输入构造：replies 的首 token/吞吐按 scenario_id 并进 judge 行。"""
    from bench.scoring import join_latency

    judge_rows = [{"scenario_id": "P01", "hit_ratio": 1.0, "score": 5}]
    replies_rows = [
        {"scenario_id": "P01", "first_token_ms": 350, "tok_s": 18.5},
        {"scenario_id": "P02", "first_token_ms": 90, "tok_s": 30.0},  # judge 缺席 → 丢弃
    ]
    usable = join_latency(judge_rows, replies_rows)
    assert usable == [
        {"scenario_id": "P01", "hit_ratio": 1.0, "first_token_ms": 350, "tok_s": 18.5}
    ]

    # 无 replies 文件（旧数据）时不炸，延迟为 None
    assert join_latency(judge_rows, []) == [
        {"scenario_id": "P01", "hit_ratio": 1.0, "first_token_ms": None, "tok_s": None}
    ]
