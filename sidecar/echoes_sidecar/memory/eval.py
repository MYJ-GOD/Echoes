"""13.3 记忆抽取评测：50 条评测集 + precision / recall / 替代正确率门禁。

指标口径（写死在这里，改口径必须同时改测试）：

- 一条预测事实与一条期望事实「匹配」= 类别相同且归一化文本相似度 ≥
  `MATCH_THRESHOLD`；一对一贪心匹配（按相似度从高到低），避免一条预测重复计 TP。
- `precision = TP / (TP + FP)`，`recall = TP / (TP + FN)`。
- 替代正确率 = 期望里带 `replaces` 的条目中，匹配到的预测 `replaces` 与期望一致的
  占比；评测集没有替代用例时门禁直接失败（不能让「没有替代」混过）。
- 抽取抛错/输出不可解析：该 case 记为 0 预测（期望全 FN），并记入 `errors`；
  门禁失败——质量门禁不接受「模型今天不听话」。

阈值来自母文档 13.3：precision ≥0.85、recall ≥0.7、替代正确率 ≥0.9。
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Protocol

from echoes_sidecar.db.memory_repo import CATEGORIES
from echoes_sidecar.memory.extractor import ExtractedFact

MATCH_THRESHOLD = 0.75
MIN_PRECISION = 0.85
MIN_RECALL = 0.70
MIN_REPLACEMENT = 0.90

DEFAULT_CASES = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "memory_eval" / "cases.jsonl"
)


class ExtractorLike(Protocol):
    """只要求 extract 形状：评测不需要 store / 写入。"""

    async def extract(
        self,
        profile_id: str,
        transcript: str,
        *,
        active_facts: Sequence[Any] | None = None,
    ) -> list[ExtractedFact]: ...


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    expected: tuple[dict[str, Any], ...]
    predicted: tuple[ExtractedFact, ...]
    tp: int
    fp: int
    fn: int
    replacement_total: int
    replacement_ok: int
    error: str | None = None


@dataclass(frozen=True)
class EvalReport:
    cases: tuple[CaseResult, ...]
    tp: int
    fp: int
    fn: int
    replacement_total: int
    replacement_ok: int

    @property
    def precision(self) -> float:
        denominator = self.tp + self.fp
        return 1.0 if denominator == 0 else self.tp / denominator

    @property
    def recall(self) -> float:
        denominator = self.tp + self.fn
        return 1.0 if denominator == 0 else self.tp / denominator

    @property
    def replacement_accuracy(self) -> float:
        return (
            1.0
            if self.replacement_total == 0
            else self.replacement_ok / self.replacement_total
        )

    @property
    def errors(self) -> list[str]:
        return [
            f"{case.case_id}: {case.error}" for case in self.cases if case.error is not None
        ]


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, Any]]:
    """读 JSONL 评测集；结构/类别/替代引用在加载期校验（fixture 错误不许混进指标）。"""
    cases: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no} 不是合法 JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"{path}:{line_no} 顶层必须是对象")
        case = raw
        case_id = case.get("id")
        transcript = case.get("transcript")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path}:{line_no} 缺 id")
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError(f"{path}:{line_no}（{case_id}）缺 transcript")
        active = case.get("active", [])
        expected = case.get("expected", [])
        if not isinstance(active, list) or not isinstance(expected, list):
            raise ValueError(f"{path}:{line_no}（{case_id}）active/expected 必须是数组")
        active_ids = {str(item.get("id")) for item in active if isinstance(item, dict)}
        for item in expected:
            if not isinstance(item, dict):
                raise ValueError(f"{path}:{line_no}（{case_id}）expected 条目必须是对象")
            fact = item.get("fact")
            category = item.get("category")
            if not isinstance(fact, str) or not fact.strip():
                raise ValueError(f"{path}:{line_no}（{case_id}）expected 缺 fact")
            if category not in CATEGORIES:
                raise ValueError(f"{path}:{line_no}（{case_id}）未知类别 {category!r}")
            replaces = item.get("replaces")
            if replaces is not None and str(replaces) not in active_ids:
                raise ValueError(
                    f"{path}:{line_no}（{case_id}）replaces={replaces!r} 不在 active 中"
                )
        cases.append(case)
    return cases


async def evaluate(
    extractor: ExtractorLike, cases: Sequence[dict[str, Any]]
) -> EvalReport:
    results: list[CaseResult] = []
    total_tp = total_fp = total_fn = 0
    total_replacement = total_replacement_ok = 0

    for case in cases:
        expected = tuple(case.get("expected", []))
        error: str | None = None
        try:
            predicted = tuple(
                await extractor.extract(
                    "default",
                    str(case["transcript"]),
                    active_facts=case.get("active", []),
                )
            )
        except Exception as exc:  # noqa: BLE001  评测要记录失败而不是崩掉整轮
            predicted = ()
            error = f"{type(exc).__name__}: {exc}"

        tp, fp, replacement_total, replacement_ok = _match(expected, predicted)
        total_tp += tp
        total_fp += fp
        total_fn += len(expected) - tp
        total_replacement += replacement_total
        total_replacement_ok += replacement_ok
        results.append(
            CaseResult(
                case_id=str(case["id"]),
                expected=expected,
                predicted=predicted,
                tp=tp,
                fp=fp,
                fn=len(expected) - tp,
                replacement_total=replacement_total,
                replacement_ok=replacement_ok,
                error=error,
            )
        )

    return EvalReport(
        cases=tuple(results),
        tp=total_tp,
        fp=total_fp,
        fn=total_fn,
        replacement_total=total_replacement,
        replacement_ok=total_replacement_ok,
    )


def gate_failures(
    report: EvalReport,
    *,
    min_precision: float = MIN_PRECISION,
    min_recall: float = MIN_RECALL,
    min_replacement: float = MIN_REPLACEMENT,
) -> list[str]:
    """返回门禁失败原因；空列表 = 通过（13.3）。"""
    failures: list[str] = []
    if report.errors:
        failures.append(f"抽取错误 {len(report.errors)} 条（解析/调用失败不算通过）")
    if report.replacement_total == 0:
        failures.append("评测集缺少替代用例：替代正确率无法判定")
    if report.precision < min_precision:
        failures.append(
            f"precision {report.precision:.3f} < {min_precision:.2f}"
        )
    if report.recall < min_recall:
        failures.append(f"recall {report.recall:.3f} < {min_recall:.2f}")
    if (
        report.replacement_total > 0
        and report.replacement_accuracy < min_replacement
    ):
        failures.append(
            f"替代正确率 {report.replacement_accuracy:.3f} < {min_replacement:.2f}"
        )
    return failures


def _match(
    expected: Sequence[dict[str, Any]], predicted: Sequence[ExtractedFact]
) -> tuple[int, int, int, int]:
    """返回 (tp, fp, replacement_total, replacement_ok)。"""
    used: set[int] = set()
    tp = 0
    replacement_total = 0
    replacement_ok = 0

    for expected_item in expected:
        expected_fact = str(expected_item.get("fact", ""))
        expected_category = str(expected_item.get("category", ""))
        if expected_item.get("replaces"):
            replacement_total += 1

        best_index: int | None = None
        best_score = MATCH_THRESHOLD
        for index, predicted_item in enumerate(predicted):
            if index in used or predicted_item.category != expected_category:
                continue
            score = _similarity(expected_fact, predicted_item.fact)
            if score >= best_score:
                best_index = index
                best_score = score
        if best_index is None:
            continue

        used.add(best_index)
        tp += 1
        expected_replaces = expected_item.get("replaces")
        if expected_replaces and predicted[best_index].replaces == expected_replaces:
            replacement_ok += 1

    return tp, len(predicted) - len(used), replacement_total, replacement_ok


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _normalize(left), _normalize(right)).ratio()


def _normalize(text: str) -> str:
    return "".join(
        char.lower()
        for char in text
        if not char.isspace() and char not in "，。！？、；：,.!?;:（）()【】[]“”\"'"
    )


__all__ = [
    "DEFAULT_CASES",
    "MATCH_THRESHOLD",
    "MIN_PRECISION",
    "MIN_RECALL",
    "MIN_REPLACEMENT",
    "CaseResult",
    "EvalReport",
    "ExtractorLike",
    "evaluate",
    "gate_failures",
    "load_cases",
]
