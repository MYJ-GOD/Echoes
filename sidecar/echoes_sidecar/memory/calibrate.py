"""R3b 3.5 θ 标定：在标注对上扫 reranker 分数，给出建议门禁线。

**为什么要单独的工具**：θ 是「低于它就不算相关」的业务阈值，写死在代码里只能
靠感觉调。把「query → passage 是否相关」的标注对喂进来，跑一遍真实 reranker，
按 F1 选阈值，再把结果回填 `DEFAULT_MIN_SCORE`（或设置项的覆盖值）。

**输入格式**（JSONL，一行一个对象）::

    {"query": "用户喜欢什么音乐", "passage": "用户喜欢在雨天听爵士", "relevant": true}
    {"query": "用户喜欢什么音乐", "passage": "用户住在杭州", "relevant": false}

**边界**：本模块只做纯计算，模型加载在 `scripts/calibrate_theta.py`；没有权重时
脚本会明确报错，不伪造分数。
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.memory.rerank import Reranker

DEFAULT_GRID: tuple[float, ...] = tuple(round(0.05 * index, 2) for index in range(20))


@dataclass(frozen=True)
class Pair:
    query: str
    passage: str
    relevant: bool


@dataclass(frozen=True)
class SweepResult:
    threshold: float
    precision: float
    recall: float
    f1: float


def load_pairs(path: Path) -> list[Pair]:
    """读 JSONL 标注对；空行跳过，坏行给出「第几行」的明确报错。"""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EchoesError(
            ErrorCode.STORAGE_ERROR, f"标注文件不可读：{path}（{exc}）"
        ) from exc
    pairs: list[Pair] = []
    for number, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise EchoesError(
                ErrorCode.STORAGE_ERROR, f"第 {number} 行不是合法 JSON：{exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise EchoesError(ErrorCode.STORAGE_ERROR, f"第 {number} 行必须是对象")
        query = str(raw.get("query") or "").strip()
        passage = str(raw.get("passage") or "").strip()
        relevant = raw.get("relevant")
        if not query or not passage or not isinstance(relevant, bool):
            raise EchoesError(
                ErrorCode.STORAGE_ERROR,
                f"第 {number} 行缺 query / passage / relevant(bool)",
            )
        pairs.append(Pair(query=query, passage=passage, relevant=relevant))
    if not pairs:
        raise EchoesError(ErrorCode.STORAGE_ERROR, f"标注文件没有有效行：{path}")
    return pairs


def score_pairs(
    pairs: Sequence[Pair], reranker: Reranker
) -> list[tuple[float, bool]]:
    """逐 query 调 reranker；返回 `(score, relevant)`（顺序与输入一致）。"""
    if not reranker.available:
        raise EchoesError(
            ErrorCode.MODEL_NOT_LOADED,
            "reranker 不可用：请先安装 bge-reranker-base"
            "（--setup install-models --ids bge-reranker-base）",
        )
    scored: list[tuple[float, bool]] = []
    by_query: dict[str, list[Pair]] = {}
    for pair in pairs:
        by_query.setdefault(pair.query, []).append(pair)
    for query, group in by_query.items():
        scores = reranker.score(query, [pair.passage for pair in group])
        if len(scores) != len(group):
            raise EchoesError(
                ErrorCode.INTERNAL_ERROR,
                f"reranker 返回分数数量不匹配（{len(scores)} != {len(group)}）",
            )
        scored.extend(zip(scores, (pair.relevant for pair in group), strict=True))
    return scored


def sweep(
    samples: Iterable[tuple[float, bool]], grid: Sequence[float] = DEFAULT_GRID
) -> SweepResult:
    """按 F1 选阈值；并列时取更高的阈值（更保守，少误召）。"""
    items = list(samples)
    if not items:
        raise EchoesError(ErrorCode.STORAGE_ERROR, "没有可扫分的样本")
    positives = sum(1 for _, relevant in items if relevant)
    if positives == 0:
        raise EchoesError(ErrorCode.STORAGE_ERROR, "标注对里没有 relevant=true 的样本")

    best: SweepResult | None = None
    for threshold in grid:
        true_positive = false_positive = false_negative = 0
        for score, relevant in items:
            predicted = score >= threshold
            if predicted and relevant:
                true_positive += 1
            elif predicted:
                false_positive += 1
            elif relevant:
                false_negative += 1
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        recall = true_positive / (true_positive + false_negative)
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        candidate = SweepResult(threshold, precision, recall, f1)
        if best is None or (candidate.f1, candidate.threshold) > (best.f1, best.threshold):
            best = candidate
    assert best is not None
    return best


__all__ = [
    "DEFAULT_GRID",
    "Pair",
    "SweepResult",
    "load_pairs",
    "score_pairs",
    "sweep",
]
