"""Runner 流程（阶段 -1）：mock provider 注入 → replies.jsonl / judge_scores.jsonl 导出协议。

真实 HTTP 通道（Ollama / OpenAI 兼容）不进 CI（本机跑）；CI 只锁导出格式与流程编排。
"""
from __future__ import annotations

import json
from pathlib import Path

from bench.runner import run_judge_channel, run_scenarios


class _FakeProvider:
    """按序吐预设回复的假 provider：只服务流程/导出协议测试。"""

    def __init__(self, replies: list[str]) -> None:
        self._replies = replies
        self.calls: list[str] = []

    async def chat(self, context: list[dict[str, str]], user: str, *, model: str) -> dict:
        self.calls.append(user)
        return {
            "reply": self._replies[len(self.calls) - 1],
            "first_token_ms": 123,
            "tok_s": 20.0,
            "model": model,
        }


class _FakeJudge:
    async def chat(self, context: list[dict[str, str]], user: str, *, model: str) -> dict:
        return {
            "reply": '{"score": 4, "points": [{"id": "x-1", "hit": true}]}',
            "first_token_ms": 50,
            "tok_s": 40.0,
            "model": model,
        }


SCENARIOS = {
    "persona_system_prompt": "你是 Echoes…",
    "scenarios": [
        {
            "id": "P01",
            "category": "persona_adherence",
            "context": [],
            "user": "今天好累",
            "expect_points": [
                {"id": "P01-1", "text": "共情"},
                {"id": "P01-2", "text": "简短"},
                {"id": "P01-3", "text": "语气自然"},
            ],
        }
    ],
}


async def test_run_scenarios_exports_parseable_jsonl(tmp_path: Path) -> None:
    out = tmp_path / "replies.jsonl"
    provider = _FakeProvider(["（fake）辛苦啦"])
    records = await run_scenarios(provider, SCENARIOS, model="fake-model", out_path=out)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "一行一轮"
    row = json.loads(lines[0])
    assert row["scenario_id"] == "P01"
    assert row["category"] == "persona_adherence"
    assert "reply" in row and "first_token_ms" in row and "tok_s" in row
    assert provider.calls == ["今天好累"], "user 消息必须喂给 provider"
    assert records[0]["reply"] == "（fake）辛苦啦"


async def test_run_judge_channel_tolerates_no_json(tmp_path: Path) -> None:
    """judge 回复缺 JSON 时该轮记 failure 行（score=None），批跑不中断（继续下一轮）。"""
    class _BadJudge:
        async def chat(
            self, context: list[dict[str, str]], user: str, *, model: str
        ) -> dict:
            return {
                "reply": "纯文本点评，没有 JSON",
                "first_token_ms": 1,
                "tok_s": 1.0,
                "model": model,
            }

    replies_path = tmp_path / "replies.jsonl"
    judge_path = tmp_path / "judge.jsonl"
    replies_path.write_text(
        json.dumps(
            {
                "scenario_id": "P01",
                "reply": "辛苦啦",
                "category": "persona_adherence",
                "first_token_ms": 1,
                "tok_s": 1.0,
                "model": "fake",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    rows = await run_judge_channel(
        _BadJudge(),
        SCENARIOS,
        replies_path=replies_path,
        judge_prompt="按要点打分",
        model="fake-judge",
        out_path=judge_path,
    )
    assert len(rows) == 1
    assert rows[0]["score"] is None
    assert rows[0]["hit_ratio"] is None
    assert rows[0]["error"].strip()
    row_from_file = json.loads(judge_path.read_text(encoding="utf-8").splitlines()[0])
    assert row_from_file["error"]


async def test_run_judge_channel_exports_intervals(tmp_path: Path) -> None:
    replies_path = tmp_path / "replies.jsonl"
    judge_path = tmp_path / "judge.jsonl"
    replies_path.write_text(
        json.dumps(
            {
                "scenario_id": "P01",
                "reply": "辛苦啦",
                "category": "persona_adherence",
                "first_token_ms": 1,
                "tok_s": 1.0,
                "model": "fake",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    rows = await run_judge_channel(
        _FakeJudge(),
        SCENARIOS,
        replies_path=replies_path,
        judge_prompt="按要点打分",
        model="fake-judge",
        out_path=judge_path,
    )
    assert len(rows) == 1
    row = json.loads(judge_path.read_text(encoding="utf-8").splitlines()[0])
    # judge 回复容错解析为结构化结果（scoring.extract_first_json）
    assert row["score"] == 4
    assert row["hit_ratio"] == 1.0
    assert row["scenario_id"] == "P01"
