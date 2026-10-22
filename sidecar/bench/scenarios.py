"""题集加载与守卫（docs/benchmarks/scenarios.json）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = REPO_ROOT / "docs" / "benchmarks" / "scenarios.json"


def load(path: Path = SCENARIOS_PATH) -> dict[str, Any]:
    """加载题集；结构性损坏即抛异常（报错而非降级）。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or len(scenarios) < 20:
        raise ValueError(f"题集轮次不足 20: {len(scenarios or [])}")
    ids = [s["id"] for s in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("场景 id 重复")
    return data
