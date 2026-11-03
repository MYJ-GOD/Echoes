"""R3a 3.9 检索评测：原文 / 摘要 / 事实三路 + 负例。

**与 `eval.py` 的分工**：那边评「事实抽取」（transcript → facts），这边评
「检索」（query → 命中）。R3b 的 rerank 阈值 θ 必须建立在两套集都扩充之后，
否则只能对事实层标定（§4.2 的门禁风险）。

**为什么先不接真库**：`MemoryRecall` 依赖 bge 权重 + 已落盘的 turn/摘要；
评测协议只要求 `recall(query)` 形状（`RecallLike`），测试用脚本化召回即可
锁定指标算法；真库/真模型扫分走 `scripts/eval_memory.py --retrieval`（待接）。

**负例是硬要求**：宁可不注入也不注入噪音（§4.2 ④）。负例越多，越能挡住
「FTS 命中一个常见词就把无关原文塞进 prompt」这类假阳性。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from echoes_sidecar.memory.recall import RecallItem, RecallResult

DEFAULT_CASES = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "memory_eval"
    / "retrieval_cases.jsonl"
)

MIN_TURN_RECALL = 0.80
MIN_SUMMARY_RECALL = 0.80
MIN_FACT_RECALL = 0.80
MIN_NEGATIVE_PRECISION = 1.0


class RecallLike(Protocol):
    async def recall(
        self, *, profile_id: str, query: str, **kwargs: object
    ) -> RecallResult: ...


@dataclass(frozen=True)
class RetrievalCase:
    id: str
    query: str
    turns: tuple[str, ...] = ()
    summaries: tuple[str, ...] = ()
    facts: tuple[str, ...] = ()
    expect_empty: bool = False


@dataclass(frozen=True)
class RetrievalCaseResult:
    case_id: str
    turn_hits: int
    turn_total: int
    summary_hits: int
    summary_total: int
    fact_hits: int
    fact_total: int
    negative_ok: bool
    expect_empty: bool = False
    error: str | None = None


@dataclass(frozen=True)
class RetrievalReport:
    cases: tuple[RetrievalCaseResult, ...]

    @property
    def turn_recall(self) -> float:
        return _ratio(
            sum(case.turn_hits for case in self.cases),
            sum(case.turn_total for case in self.cases),
        )

    @property
    def summary_recall(self) -> float:
        return _ratio(
            sum(case.summary_hits for case in self.cases),
            sum(case.summary_total for case in self.cases),
        )

    @property
    def fact_recall(self) -> float:
        return _ratio(
            sum(case.fact_hits for case in self.cases),
            sum(case.fact_total for case in self.cases),
        )

    @property
    def negative_precision(self) -> float:
        negatives = [case for case in self.cases if case.expect_empty]
        return _ratio(sum(1 for case in negatives if case.negative_ok), len(negatives))

    @property
    def errors(self) -> list[str]:
        return [
            f"{case.case_id}: {case.error}"
            for case in self.cases
            if case.error is not None
        ]


def _ratio(hits: int, total: int) -> float:
    return 1.0 if total == 0 else hits / total


def load_retrieval_cases(path: Path = DEFAULT_CASES) -> list[RetrievalCase]:
    """读 JSONL 检索评测集；结构错误在加载期报（fixture 坏不许混进指标）。"""
    cases: list[RetrievalCase] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no} 不是合法 JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"{path}:{line_no} 顶层必须是对象")
        case_id = raw.get("id")
        query = raw.get("query")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path}:{line_no} 缺 id")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{path}:{line_no}（{case_id}）缺 query")
        turns = _strings(raw.get("turns", []), path, line_no, case_id, "turns")
        summaries = _strings(
            raw.get("summaries", []), path, line_no, case_id, "summaries"
        )
        facts = _strings(raw.get("facts", []), path, line_no, case_id, "facts")
        expect_empty = bool(raw.get("expectEmpty", False))
        if expect_empty and (turns or summaries or facts):
            raise ValueError(
                f"{path}:{line_no}（{case_id}）expectEmpty 与期望命中互斥"
            )
        if not expect_empty and not (turns or summaries or facts):
            raise ValueError(
                f"{path}:{line_no}（{case_id}）缺期望命中（或标 expectEmpty）"
            )
        cases.append(
            RetrievalCase(
                id=case_id,
                query=query,
                turns=tuple(turns),
                summaries=tuple(summaries),
                facts=tuple(facts),
                expect_empty=expect_empty,
            )
        )
    return cases


def _strings(
    value: object, path: Path, line_no: int, case_id: str, field: str
) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{path}:{line_no}（{case_id}）{field} 必须是非空字符串数组")
    return [str(item) for item in value]


async def evaluate_retrieval(
    recall: RecallLike, cases: list[RetrievalCase]
) -> RetrievalReport:
    results: list[RetrievalCaseResult] = []
    for case in cases:
        error: str | None = None
        try:
            outcome = await recall.recall(profile_id="default", query=case.query)
        except Exception as exc:  # noqa: BLE001  评测记录失败而不是崩掉整轮
            outcome = RecallResult()
            error = f"{type(exc).__name__}: {exc}"
        turn_hits = _hits(case.turns, outcome.turns)
        summary_hits = _hits(case.summaries, outcome.summaries)
        fact_hits = _hits(case.facts, outcome.facts)
        negative_ok = (not case.expect_empty) or outcome.empty
        results.append(
            RetrievalCaseResult(
                case_id=case.id,
                turn_hits=turn_hits,
                turn_total=len(case.turns),
                summary_hits=summary_hits,
                summary_total=len(case.summaries),
                fact_hits=fact_hits,
                fact_total=len(case.facts),
                negative_ok=negative_ok,
                expect_empty=case.expect_empty,
                error=error,
            )
        )
    return RetrievalReport(cases=tuple(results))


def _hits(expected: tuple[str, ...], items: tuple[RecallItem, ...]) -> int:
    haystacks = [item.text.casefold() for item in items]
    return sum(
        1
        for needle in expected
        if any(needle.casefold() in haystack for haystack in haystacks)
    )


def gate_failures(report: RetrievalReport) -> list[str]:
    """返回未达标的项（空表 = 通过）；与 `eval.gate_failures` 同风格。"""
    failures: list[str] = []
    if report.turn_recall < MIN_TURN_RECALL:
        failures.append(
            f"原文召回 {report.turn_recall:.2f} < {MIN_TURN_RECALL:.2f}"
        )
    if report.summary_recall < MIN_SUMMARY_RECALL:
        failures.append(
            f"摘要召回 {report.summary_recall:.2f} < {MIN_SUMMARY_RECALL:.2f}"
        )
    if report.fact_recall < MIN_FACT_RECALL:
        failures.append(f"事实召回 {report.fact_recall:.2f} < {MIN_FACT_RECALL:.2f}")
    if report.negative_precision < MIN_NEGATIVE_PRECISION:
        failures.append(
            f"负例精确率 {report.negative_precision:.2f} < {MIN_NEGATIVE_PRECISION:.2f}"
        )
    if report.errors:
        failures.append(f"检索错误 {len(report.errors)} 条")
    return failures


__all__ = [
    "DEFAULT_CASES",
    "MIN_FACT_RECALL",
    "MIN_NEGATIVE_PRECISION",
    "MIN_SUMMARY_RECALL",
    "MIN_TURN_RECALL",
    "RecallLike",
    "RetrievalCase",
    "RetrievalCaseResult",
    "RetrievalReport",
    "evaluate_retrieval",
    "gate_failures",
    "load_retrieval_cases",
]
