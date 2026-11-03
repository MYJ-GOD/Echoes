"""R3b 3.4/3.6：实体加分口径 + reranker 权重探测。"""

from __future__ import annotations

from pathlib import Path

from echoes_sidecar.memory.entities import (
    ENTITY_BONUS_CAP,
    entity_bonus,
    entity_hits,
    query_entities,
)
from echoes_sidecar.memory.rerank import NoopReranker, make_reranker


def test_query_entities_skips_pronouns_and_keeps_nouns() -> None:
    entities = query_entities("上次说的那本吉他书叫什么")
    assert "吉他" in entities
    assert "什么" not in entities
    assert "上次" not in entities
    assert len(entities) <= 8


def test_entity_hits_and_bonus_cap() -> None:
    entities = ("吉他", "小王", "杭州")
    text = "我在学吉他，也想读小王"
    assert entity_hits(entities, text) == 2
    assert entity_bonus(entities, text) == 0.2
    assert entity_bonus(("吉他", "小王", "杭州", "猫"), "吉他 小王 杭州 猫") == ENTITY_BONUS_CAP
    assert entity_bonus(("吉他",), "今天喝咖啡") == 0.0


def test_reranker_is_noop_without_weights(tmp_path: Path) -> None:
    reranker = make_reranker(tmp_path / "bge-reranker-base")
    assert isinstance(reranker, NoopReranker)
    assert reranker.available is False
    assert reranker.score("q", ["a", "b"]) == [0.0, 0.0]
    assert make_reranker(None).available is False


def test_reranker_rejects_partial_directory(tmp_path: Path) -> None:
    model_dir = tmp_path / "bge-reranker-base"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    # 只有 config、没有权重：仍视为不可用（不要加载半个模型）
    assert make_reranker(model_dir).available is False
