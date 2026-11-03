"""R3b 3.5 θ 标定：标注对解析与阈值扫分。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError
from echoes_sidecar.memory.calibrate import Pair, load_pairs, score_pairs, sweep
from echoes_sidecar.memory.rerank import NoopReranker


class FakeReranker:
    available = True

    def __init__(self, table: dict[str, float]) -> None:
        self._table = table

    def score(self, query: str, texts: list[str]) -> list[float]:
        _ = query
        return [self._table[text] for text in texts]


def test_load_pairs_skips_blank_and_rejects_bad_rows(tmp_path: Path) -> None:
    path = tmp_path / "pairs.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"query": "q", "passage": "p", "relevant": True}),
                "",
                json.dumps({"query": "q2", "passage": "p2", "relevant": False}),
            ]
        ),
        encoding="utf-8",
    )
    pairs = load_pairs(path)
    assert pairs == [
        Pair("q", "p", True),
        Pair("q2", "p2", False),
    ]

    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"query": "q"}\n', encoding="utf-8")
    with pytest.raises(EchoesError) as err:
        load_pairs(bad)
    assert "第 1 行" in err.value.message


def test_sweep_picks_threshold_with_best_f1() -> None:
    samples = [(0.91, True), (0.82, True), (0.21, False), (0.65, False)]
    best = sweep(samples, (0.1, 0.3, 0.5, 0.7, 0.8, 0.9))
    assert best.threshold == 0.8
    assert best.precision == 1.0
    assert best.recall == 1.0
    assert best.f1 == 1.0


def test_sweep_rejects_empty_or_no_positive() -> None:
    with pytest.raises(EchoesError):
        sweep([])
    with pytest.raises(EchoesError):
        sweep([(0.5, False), (0.9, False)])


def test_score_pairs_requires_available_reranker() -> None:
    with pytest.raises(EchoesError) as err:
        score_pairs([Pair("q", "p", True)], NoopReranker())
    assert "bge-reranker-base" in err.value.message


def test_score_pairs_preserves_input_order_across_queries() -> None:
    pairs = [
        Pair("q1", "a", True),
        Pair("q1", "b", False),
        Pair("q2", "c", True),
    ]
    scored = score_pairs(
        pairs, FakeReranker({"a": 0.9, "b": 0.1, "c": 0.7})
    )
    assert scored == [(0.9, True), (0.1, False), (0.7, True)]
