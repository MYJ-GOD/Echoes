"""ADR-012 延迟基线的口径锁（脚本里的纯函数，不 spawn 进程）。

最易错的一点：`timings.*` 是 sidecar 单调时钟的**绝对刻度**（3.4），分段必须与
`state(generating).t` / 首 token 刻度做差。这里把这个减法钉住——数字算错会让
验收「看起来通过」，比没有基准更糟。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bench_latency.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_latency", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bench = _load()


def _state(t: int) -> dict[str, object]:
    return {"type": "state", "state": "generating", "session_id": "default", "t": t}


def _complete(total: int, first_token: int | None, first_audio: int | None) -> dict[str, object]:
    return {
        "type": "turn_complete",
        "session_id": "default",
        "turn_seq": 1,
        "status": "SUCCESS",
        "timings": {
            "total_ms": total,
            "llm_first_token_ms": first_token,
            "tts_first_audio_ms": first_audio,
        },
    }


def test_segments_are_differences_not_absolute_marks() -> None:
    """绝对刻度 30000/30400/30650 → 首 token 400ms、首音频 250ms、总 650ms。"""
    turns = bench.turns_from_msgs([_state(30_000), _complete(30_650, 30_400, 30_650)])

    assert len(turns) == 1
    assert turns[0]["first_token"] == 400
    assert turns[0]["first_audio"] == 250
    assert turns[0]["turn_total"] == 650


def test_missing_marks_yield_none_instead_of_zero() -> None:
    """FAILED/CANCELLED 没有首音频：留 None（不参与统计），不能记成 0ms 好成绩。"""
    turns = bench.turns_from_msgs([_state(1_000), _complete(1_500, 1_200, None)])

    assert turns[0]["first_token"] == 200
    assert turns[0]["first_audio"] is None
    assert turns[0]["turn_total"] == 500


def test_turn_without_state_mark_keeps_null_baseline() -> None:
    """没有 state(generating) 就无法定起点：宁可 None，也不要拿 sidecar 启动时刻当起点。"""
    turns = bench.turns_from_msgs([_complete(99_999, 99_500, 99_600)])

    assert turns[0]["first_token"] is None
    assert turns[0]["turn_total"] is None


def test_malformed_timings_are_skipped_not_mis_computed() -> None:
    turns = bench.turns_from_msgs(
        [_state(10), {"type": "turn_complete", "status": "SUCCESS", "timings": "oops"}]
    )
    assert turns == []


def test_multiple_turns_are_paired_in_order() -> None:
    turns = bench.turns_from_msgs(
        [
            _state(1_000),
            _complete(1_400, 1_200, 1_350),
            _state(2_000),
            _complete(2_600, 2_300, 2_550),
        ]
    )
    assert [t["turn_total"] for t in turns] == [400, 600]


def test_percentile_handles_single_and_multi() -> None:
    assert bench.percentile([], 0.5) == 0.0
    assert bench.percentile([7.0], 0.95) == 7.0
    # 10 个样本：P50 = 5.5（线性插值），P95 = 9.55
    assert bench.percentile([float(i) for i in range(1, 11)], 0.5) == 5.5
    assert round(bench.percentile([float(i) for i in range(1, 11)], 0.95), 2) == 9.55


def test_summary_counts_only_available_segments() -> None:
    turns = [
        {"first_token": 100, "first_audio": 200, "turn_total": 900},
        {"first_token": 300, "first_audio": None, "turn_total": 700},
    ]
    report = bench.summarize(turns)

    assert report["first_token"]["n"] == 2
    assert report["first_audio"]["n"] == 1
    assert report["first_audio"]["p50"] == 200.0


def test_verdict_flags_budget_breach() -> None:
    """判定面：超 P50 预算、超 P95 预算、达标三种都要能区分。"""
    assert bench._verdict("turn_total", 2_400, 3_900) == "✅"
    assert bench._verdict("turn_total", 2_600, 3_000) == "❌ 超预算"
    assert bench._verdict("turn_total", 2_000, 4_500) == "❌ P95 超预算"
    assert bench._verdict("first_token", 0, 0) == "—"
