"""13.3 记忆抽取评测：50 条评测集 + precision / recall / 替代正确率门禁。

指标口径（写死在这里，改口径必须同时改测试）：

- 一条预测事实与一条期望事实「匹配」= 文本等价。默认用字符串相似度
  （类别相同 + 归一化文本相似度 ≥ `MATCH_THRESHOLD`）；传入 `Judge` 时改由
  独立模型判定（措辞不同但事实相同算匹配，实体/否定/时间变化算不匹配）。
- 一对一贪心匹配（按相似度从高到低），避免一条预测重复计 TP。
- `precision = TP / (TP + FP)`，`recall = TP / (TP + FN)`。
- 替代正确率 = 期望里带 `replaces` 的条目中，匹配到的预测 `replaces` 与期望一致的
  占比；评测集没有替代用例时门禁直接失败（不能让「没有替代」混过）。
- 抽取抛错/输出不可解析：该 case 记为 0 预测（期望全 FN），并记入 `errors`；
  judge 抛错同样记入 `errors`；门禁失败。

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
from echoes_sidecar.memory.extractor import ExtractedFact, FactLLM, collect_text

MATCH_THRESHOLD = 0.75
MIN_PRECISION = 0.85
MIN_RECALL = 0.70
MIN_REPLACEMENT = 0.90

DEFAULT_CASES = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "memory_eval" / "cases.jsonl"
)

_JUDGE_SYSTEM = (
    "你是严格的事实等价判断器。判断「期望事实」与「抽取事实」是否表达同一条关于用户的长期事实。\n"
    "YES：核心实体、属性、否定、时间/更新关系一致；抽取事实可以更详细或措辞不同。\n"
    "NO：实体不同（如猫/狗）、否定相反、时间或计划被改变、抽取事实只部分相关，\n"
    "    或添加了原文没有的信息。\n"
    "只输出 YES 或 NO。"
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


class Judge(Protocol):
    """事实等价判定（独立模型；避免字符串相似度误杀正确转述）。"""

    async def equivalent(self, expected: str, predicted: str) -> bool: ...


class LLMPairJudge:
    """用独立 LLM 判两条事实是否等价；结果按 (expected, predicted) 缓存。"""

    def __init__(self, llm: FactLLM) -> None:
        self._llm = llm
        self._cache: dict[tuple[str, str], bool] = {}

    async def equivalent(self, expected: str, predicted: str) -> bool:
        key = (expected.strip(), predicted.strip())
        if key in self._cache:
            return self._cache[key]
        messages = [
            {"role": "system", "content": _JUDGE_SYSTEM},
            {
                "role": "user",
                "content": f"期望事实：{expected}\n抽取事实：{predicted}",
            },
        ]
        raw = await collect_text(
            self._llm.generate(messages, stream=False, temperature=0.0, max_tokens=8)
        )
        answer = raw.strip().upper()
        if answer.startswith("YES"):
            result = True
        elif answer.startswith("NO"):
            result = False
        else:
            raise RuntimeError(f"judge 输出无法判定：{raw[:80]!r}")
        self._cache[key] = result
        return result


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
    extractor: ExtractorLike,
    cases: Sequence[dict[str, Any]],
    *,
    judge: Judge | None = None,
) -> EvalReport:
    results: list[CaseResult] = []
    total_tp = total_fp = total_fn = 0
    total_replacement = total_replacement_ok = 0

    # 两遍：先全部抽取，再统一判定。避免 extractor/judge 两个模型逐例交替导致
    # Ollama 在 8G 显存上反复换入换出（第二遍才加载 judge 模型）。
    extracted: list[tuple[dict[str, Any], tuple[ExtractedFact, ...], str | None]] = []
    for case in cases:
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
        extracted.append((case, predicted, error))

    for case, predicted, error in extracted:
        expected = tuple(case.get("expected", []))
        tp, fp, replacement_total, replacement_ok, match_error = await _match(
            expected, predicted, judge
        )
        if match_error is not None:
            error = f"{error}; {match_error}" if error else match_error
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
        failures.append(f"抽取/判定错误 {len(report.errors)} 条（解析/调用失败不算通过）")
    if report.replacement_total == 0:
        failures.append("评测集缺少替代用例：替代正确率无法判定")
    if report.precision < min_precision:
        failures.append(f"precision {report.precision:.3f} < {min_precision:.2f}")
    if report.recall < min_recall:
        failures.append(f"recall {report.recall:.3f} < {min_recall:.2f}")
    if report.replacement_total > 0 and report.replacement_accuracy < min_replacement:
        failures.append(
            f"替代正确率 {report.replacement_accuracy:.3f} < {min_replacement:.2f}"
        )
    return failures


async def _match(
    expected: Sequence[dict[str, Any]],
    predicted: Sequence[ExtractedFact],
    judge: Judge | None,
) -> tuple[int, int, int, int, str | None]:
    """返回 (tp, fp, replacement_total, replacement_ok, judge_error)。"""
    used: set[int] = set()
    tp = 0
    replacement_total = 0
    replacement_ok = 0
    judge_error: str | None = None

    for expected_item in expected:
        expected_fact = str(expected_item.get("fact", ""))
        expected_category = str(expected_item.get("category", ""))
        if expected_item.get("replaces"):
            replacement_total += 1

        matched_index: int | None = None
        if judge is None:
            best_score = MATCH_THRESHOLD
            for index, predicted_item in enumerate(predicted):
                if index in used or predicted_item.category != expected_category:
                    continue
                score = _similarity(expected_fact, predicted_item.fact)
                if score >= best_score:
                    matched_index = index
                    best_score = score
        else:
            for index, predicted_item in enumerate(predicted):
                if index in used:
                    continue
                try:
                    if await judge.equivalent(expected_fact, predicted_item.fact):
                        matched_index = index
                        break
                except Exception as exc:  # noqa: BLE001  判定失败要进报告
                    judge_error = f"judge: {type(exc).__name__}: {exc}"

        if matched_index is None:
            continue
        used.add(matched_index)
        tp += 1
        expected_replaces = expected_item.get("replaces")
        if expected_replaces and predicted[matched_index].replaces == expected_replaces:
            replacement_ok += 1

    return tp, len(predicted) - len(used), replacement_total, replacement_ok, judge_error


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
    "Judge",
    "LLMPairJudge",
    "evaluate",
    "gate_failures",
    "load_cases",
]
