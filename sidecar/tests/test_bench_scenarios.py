"""题集守卫（阶段 -1）：scenarios.json 结构与交付物完整性（文档 6/阶段 -1）。

数据先行：docs/benchmarks/scenarios.json 是文档点名的交付物本体，本测试锁：
20 轮三类齐全、要点清单非空、id 唯一、人设语与 sidecar 默认人设同源一致。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from echoes_sidecar.engines.llm.persona import PERSONA_SYSTEM_PROMPT

REPO = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = REPO / "docs" / "benchmarks" / "scenarios.json"

CATEGORIES = {"persona_adherence", "memory_reference", "emotional_resonance"}


def load_scenarios() -> dict[str, Any]:
    return json.loads(SCENARIOS_PATH.read_text(encoding="utf-8"))


def test_scenarios_parse_and_count_at_least_20() -> None:
    scenarios = load_scenarios()["scenarios"]
    assert len(scenarios) >= 20


def test_scenarios_cover_all_three_categories() -> None:
    seen = {s["category"] for s in load_scenarios()["scenarios"]}
    assert seen == CATEGORIES


def test_scenario_fields_complete_and_ids_unique() -> None:
    scenarios = load_scenarios()["scenarios"]
    ids = [s["id"] for s in scenarios]
    assert len(ids) == len(set(ids)), "场景 id 必须唯一"
    for s in scenarios:
        assert s["id"], "每轮必须有 id"
        assert s["user"].strip(), f"{s['id']} user 消息为空"
        assert len(s["expect_points"]) >= 3, f"{s['id']} 要点清单不足 3 条"
        for point in s["expect_points"]:
            assert point["id"].startswith(s["id"]), f"{s['id']} 要点 id 前缀错位"
            assert point["text"].strip(), f"{s['id']} 有点空要点"
        assert "  " not in s["user"], f"{s['id']} user 文本有连续空格（乱码残留嫌疑）"


def test_persona_prompt_consistent_with_sidecar() -> None:
    """人设语锁定（对拍升级 v1.4.1 后）：题集人设 == persona.py 单一来源常量。"""
    prompt = load_scenarios()["persona_system_prompt"]
    assert prompt == PERSONA_SYSTEM_PROMPT
    # 二轮复测条款在位：身份锁（P02）、诚实红线（P03）、输出格式（TTS 口径）
    assert "病假" in prompt
    assert "markdown" in prompt
    assert "Echoes" in prompt
