"""MemoryStore / 嵌入工具：写入、检索、取代、删除与提示词拼装。

用 `_FakeEmbedder` 把「语义相似」变成可控的固定向量——真 bge 权重属 7.3 下载
边界，测试不该依赖它；这里锁的是**编排语义**（谁被召回、返回什么列、删了还查不
查得到），不是模型质量。模型质量的守护在 13.3 的 50 条评测集（阶段 1 门禁）。
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db.memory_repo import EMBEDDING_DIM
from echoes_sidecar.db.repo import Storage
from echoes_sidecar.memory.embedding import TransformersEmbedder, normalize
from echoes_sidecar.memory.store import MemoryStore

pytest.importorskip("sqlite_vec", reason="记忆向量表需要 sqlite-vec（0002 迁移 -- requires）")

# 关键词 → 语义轴（够表达「相近的事实被召回」这件事）
_AXES = {"面试": 0, "工作": 0, "咖啡": 1, "茶": 1, "猫": 2}


class _FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            vector = [0.0] * EMBEDDING_DIM
            for keyword, axis in _AXES.items():
                if keyword in text:
                    vector[axis] = 1.0
            if not any(vector):
                vector[3] = 1.0  # 兜底轴：既不命中也不全零
            vectors.append(normalize(vector))
        return vectors


def _store(tmp_path: Path) -> tuple[MemoryStore, _FakeEmbedder]:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    embedder = _FakeEmbedder()
    return MemoryStore(storage.memories, embedder), embedder


def test_normalize_gives_unit_length() -> None:
    vector = normalize([3.0, 4.0] + [0.0] * (EMBEDDING_DIM - 2))
    assert math.isclose(sum(v * v for v in vector) ** 0.5, 1.0, rel_tol=1e-9)


def test_normalize_rejects_zero_vector() -> None:
    with pytest.raises(EchoesError) as exc_info:
        normalize([0.0] * EMBEDDING_DIM)
    assert exc_info.value.code is ErrorCode.INTERNAL_ERROR


async def test_retrieve_returns_semantically_near_facts(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    await store.remember(fact="用户下周有面试", category="event")
    await store.remember(fact="用户喜欢喝咖啡", category="preference")

    hits = await store.retrieve("default", "面试准备得怎么样", k=1)
    assert hits == [{"fact": "用户下周有面试", "category": "event"}]


async def test_retrieve_exposes_only_fact_and_category(tmp_path: Path) -> None:
    """隐私面最小化：id / 来源会话不泄进 prompt。"""
    store, _ = _store(tmp_path)
    await store.remember(fact="用户养了一只猫", category="identity", source_session_id="s1")
    [hit] = await store.retrieve("default", "猫", k=1)
    assert set(hit) == {"fact", "category"}


async def test_empty_query_skips_embedding_and_db(tmp_path: Path) -> None:
    """空 query 直接返回空：不白跑一次前向，也不返回「任意 top-k」。"""
    store, embedder = _store(tmp_path)
    await store.remember(fact="用户下周有面试", category="event")
    embedder.calls.clear()

    assert await store.retrieve("default", "   ") == []
    assert embedder.calls == []


async def test_supersede_hides_old_fact_from_retrieval(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    old = await store.remember(fact="用户下周有面试", category="event")
    new = await store.remember(
        fact="面试改到周四了", category="event", supersedes=old.id
    )

    hits = await store.retrieve("default", "面试", k=5)
    assert [h["fact"] for h in hits] == [new.fact]


async def test_forget_removes_from_retrieval(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    fact = await store.remember(fact="用户住在杭州", category="identity")
    await store.forget(fact.id)

    assert await store.retrieve("default", "面试", k=5) == []
    assert await store.active() == []


async def test_compose_hint_is_empty_when_nothing_recalled() -> None:
    store = MemoryStore.__new__(MemoryStore)  # 只测纯拼装，不需要库
    assert store.compose_hint([]) == ""


async def test_compose_hint_lists_facts(tmp_path: Path) -> None:
    store, _ = _store(tmp_path)
    hint = store.compose_hint(
        [{"fact": "用户下周有面试", "category": "event"}, {"fact": "", "category": "other"}]
    )
    assert hint.startswith("关于用户的已知信息")
    assert "- 用户下周有面试" in hint
    assert hint.count("\n- ") == 1  # 空 fact 不产生空行


async def test_missing_embedding_weights_raise_model_not_loaded(tmp_path: Path) -> None:
    """权重缺失 → MODEL_NOT_LOADED，且不 import transformers（防 hub 回退联网）。"""
    embedder = TransformersEmbedder(model_dir=tmp_path / "bge-small-zh-v1.5")
    with pytest.raises(EchoesError) as exc_info:
        await embedder.embed(["你好"])
    assert exc_info.value.code is ErrorCode.MODEL_NOT_LOADED
    assert embedder._model is None
