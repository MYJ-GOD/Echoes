"""13.3 评测集覆盖与门禁口径（指标数学 + 失败路径）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from echoes_sidecar.memory.eval import (
    evaluate,
    gate_failures,
    load_cases,
)
from echoes_sidecar.memory.extractor import ExtractedFact


class ScriptedExtractor:
    """按 transcript 返回评测集期望：验证指标/门禁，不冒充模型质量。"""

    def __init__(self, cases: Sequence[dict[str, Any]]) -> None:
        self._by_transcript = {str(case["transcript"]): case for case in cases}

    async def extract(
        self,
        profile_id: str,
        transcript: str,
        *,
        active_facts: Sequence[Any] | None = None,
    ) -> list[ExtractedFact]:
        _ = (profile_id, active_facts)
        case = self._by_transcript[transcript]
        return [
            ExtractedFact(
                fact=str(item["fact"]),
                category=str(item["category"]),
                replaces=item.get("replaces"),
            )
            for item in case.get("expected", [])
        ]


class EmptyExtractor:
    async def extract(
        self,
        profile_id: str,
        transcript: str,
        *,
        active_facts: Sequence[Any] | None = None,
    ) -> list[ExtractedFact]:
        _ = (profile_id, transcript, active_facts)
        return []


class NoisyExtractor(ScriptedExtractor):
    async def extract(
        self,
        profile_id: str,
        transcript: str,
        *,
        active_facts: Sequence[Any] | None = None,
    ) -> list[ExtractedFact]:
        facts = await super().extract(profile_id, transcript, active_facts=active_facts)
        return facts + [ExtractedFact("用户喜欢无关的东西", "preference")]


class WrongReplaceExtractor(ScriptedExtractor):
    async def extract(
        self,
        profile_id: str,
        transcript: str,
        *,
        active_facts: Sequence[Any] | None = None,
    ) -> list[ExtractedFact]:
        facts = await super().extract(profile_id, transcript, active_facts=active_facts)
        return [
            ExtractedFact(fact=item.fact, category=item.category, replaces="f999")
            if item.replaces
            else item
            for item in facts
        ]


class BoomExtractor:
    async def extract(
        self,
        profile_id: str,
        transcript: str,
        *,
        active_facts: Sequence[Any] | None = None,
    ) -> list[ExtractedFact]:
        _ = (profile_id, transcript, active_facts)
        raise RuntimeError("模型吐了非 JSON")


def test_default_fixture_has_50_cases_and_all_categories() -> None:
    cases = load_cases()
    assert len(cases) >= 50
    ids = [str(case["id"]) for case in cases]
    assert len(ids) == len(set(ids))
    categories = {
        str(item["category"]) for case in cases for item in case.get("expected", [])
    }
    assert categories == {"preference", "event", "identity", "other"}
    assert sum(1 for case in cases if not case.get("expected")) >= 5
    assert (
        sum(
            1
            for case in cases
            for item in case.get("expected", [])
            if item.get("replaces")
        )
        >= 5
    )


async def test_expected_outputs_pass_the_gate() -> None:
    cases = load_cases()
    report = await evaluate(ScriptedExtractor(cases), cases)

    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.replacement_accuracy == 1.0
    assert gate_failures(report) == []


async def test_empty_predictions_fail_recall_and_replacement() -> None:
    cases = load_cases()
    report = await evaluate(EmptyExtractor(), cases)
    failures = gate_failures(report)

    assert report.recall == 0.0
    assert any("recall" in item for item in failures)
    assert any("替代正确率" in item for item in failures)


async def test_extra_predictions_fail_precision() -> None:
    cases = load_cases()
    report = await evaluate(NoisyExtractor(cases), cases)
    failures = gate_failures(report)

    assert report.precision < 0.85
    assert any("precision" in item for item in failures)


async def test_wrong_replaces_fails_replacement_accuracy() -> None:
    cases = load_cases()
    report = await evaluate(WrongReplaceExtractor(cases), cases)
    failures = gate_failures(report)

    assert report.precision == 1.0
    assert report.replacement_accuracy == 0.0
    assert any("替代正确率" in item for item in failures)


async def test_extractor_error_is_recorded_and_fails_gate() -> None:
    cases = load_cases()[:1]
    report = await evaluate(BoomExtractor(), cases)
    failures = gate_failures(report)

    assert report.errors
    assert any("抽取错误" in item for item in failures)


async def test_gate_requires_replacement_coverage() -> None:
    cases = [
        {
            "id": "only-normal",
            "transcript": "用户：我喜欢猫。",
            "active": [],
            "expected": [{"fact": "用户喜欢猫", "category": "preference"}],
        }
    ]
    report = await evaluate(ScriptedExtractor(cases), cases)

    assert report.replacement_total == 0
    assert any("替代用例" in item for item in gate_failures(report))
