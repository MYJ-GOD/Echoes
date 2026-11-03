"""R3a 3.9 检索评测：指标算法、负例门禁与 fixture 校验。"""

from __future__ import annotations

from typing import Any

from echoes_sidecar.memory.recall import RecallItem, RecallResult
from echoes_sidecar.memory.retrieval_eval import (
    evaluate_retrieval,
    gate_failures,
    load_retrieval_cases,
)


class ScriptedRecall:
    def __init__(self, results: dict[str, RecallResult] | None = None) -> None:
        self.results = results or {}
        self.calls: list[tuple[str, str]] = []

    async def recall(
        self, *, profile_id: str, query: str, **_: Any
    ) -> RecallResult:
        self.calls.append((profile_id, query))
        return self.results.get(query, RecallResult())


def _expected_results() -> dict[str, RecallResult]:
    results: dict[str, RecallResult] = {}
    for case in load_retrieval_cases():
        results[case.query] = RecallResult(
            turns=tuple(
                RecallItem("turn", f"{case.id}-t{index}", text, title="第 1 轮")
                for index, text in enumerate(case.turns)
            ),
            summaries=tuple(
                RecallItem("summary", f"{case.id}-s{index}", text, title="会话")
                for index, text in enumerate(case.summaries)
            ),
            facts=tuple(
                RecallItem("fact", f"{case.id}-f{index}", text)
                for index, text in enumerate(case.facts)
            ),
        )
    return results


def test_fixture_covers_three_routes_and_negatives() -> None:
    cases = load_retrieval_cases()
    assert len(cases) >= 12
    assert len({case.id for case in cases}) == len(cases)
    assert any(case.turns for case in cases)
    assert any(case.summaries for case in cases)
    assert any(case.facts for case in cases)
    assert sum(1 for case in cases if case.expect_empty) >= 2


async def test_expected_results_pass_the_gate() -> None:
    cases = load_retrieval_cases()
    recall = ScriptedRecall(_expected_results())
    report = await evaluate_retrieval(recall, cases)

    assert report.turn_recall == 1.0
    assert report.summary_recall == 1.0
    assert report.fact_recall == 1.0
    assert report.negative_precision == 1.0
    assert gate_failures(report) == []
    assert len(recall.calls) == len(cases)


async def test_empty_recall_fails_route_thresholds_but_keeps_negatives() -> None:
    cases = load_retrieval_cases()
    report = await evaluate_retrieval(ScriptedRecall(), cases)

    assert report.turn_recall == 0.0
    assert report.summary_recall == 0.0
    assert report.fact_recall == 0.0
    assert report.negative_precision == 1.0
    failures = gate_failures(report)
    assert any("原文召回" in item for item in failures)
    assert not any("负例" in item for item in failures)


async def test_false_positives_on_negative_cases_fail_the_gate() -> None:
    cases = load_retrieval_cases()
    noise = {
        case.query: RecallResult(
            turns=(RecallItem("turn", "noise", "今天天气不错，适合出门走走"),)
        )
        for case in cases
        if case.expect_empty
    }
    report = await evaluate_retrieval(ScriptedRecall(noise), cases)

    assert report.negative_precision < 1.0
    assert any("负例精确率" in item for item in gate_failures(report))


async def test_recall_error_is_reported_and_fails_gate() -> None:
    cases = load_retrieval_cases()[:2]

    class BoomRecall:
        async def recall(self, **_: Any) -> RecallResult:
            raise RuntimeError("db locked")

    report = await evaluate_retrieval(BoomRecall(), cases)

    assert len(report.errors) == len(cases)
    assert any("检索错误" in item for item in gate_failures(report))
