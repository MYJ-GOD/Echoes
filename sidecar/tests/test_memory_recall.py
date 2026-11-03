"""R3a 检索链（3.3/3.3a）：三路检索 + RRF 融合 + 单路失败隔离。"""

from __future__ import annotations

from dataclasses import dataclass

from echoes_sidecar.db.chunk_repo import ChunkHit
from echoes_sidecar.memory.recall import (
    MemoryRecall,
    RecallItem,
    rrf_fuse,
)


@dataclass
class Fact:
    id: str
    fact: str


@dataclass
class Turn:
    turn_id: str
    user_text: str
    seq: int


@dataclass
class Summary:
    session_id: str
    title: str | None
    summary: str
    updated_at: float


class FakeStore:
    def __init__(self, facts: list[Fact] | None = None, *, error: Exception | None = None) -> None:
        self.facts = facts or []
        self.error = error
        self.calls: list[tuple[str, str, int]] = []

    async def search(self, profile_id: str, query: str, *, k: int = 5) -> list[Fact]:
        self.calls.append((profile_id, query, k))
        if self.error is not None:
            raise self.error
        return self.facts

    async def embed(self, text: str) -> list[float]:
        _ = text
        return [0.0] * 512


class FakeTurns:
    def __init__(self, rows: list[Turn] | None = None, *, error: Exception | None = None) -> None:
        self.rows = rows or []
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, limit: int = 20) -> list[Turn]:
        self.calls.append((query, limit))
        if self.error is not None:
            raise self.error
        return self.rows


class FakeSessions:
    def __init__(
        self, rows: list[Summary] | None = None, *, error: Exception | None = None
    ) -> None:
        self.rows = rows or []
        self.error = error
        self.calls: list[tuple[str, int, float | None]] = []

    def search_summaries(
        self, query: str, *, limit: int = 10, since: float | None = None
    ) -> list[Summary]:
        self.calls.append((query, limit, since))
        if self.error is not None:
            raise self.error
        return self.rows


def test_rrf_prefers_items_hit_by_multiple_routes() -> None:
    fact = RecallItem("fact", "f1", "x")
    turn = RecallItem("turn", "t1", "y")
    fused = rrf_fuse([[fact], [turn, fact]])
    assert [item.ref_id for item in fused] == ["f1", "t1"]
    assert fused[0].score > fused[1].score
    # k 越大，名次差带来的分差越小
    flat = rrf_fuse([[fact], [turn, fact]], k=10_000)
    assert flat[0].score - flat[1].score < fused[0].score - fused[1].score


async def test_recall_merges_three_routes_and_truncates_snippets() -> None:
    store = FakeStore([Fact("f1", "用户喜欢猫")])
    turns = FakeTurns([Turn("t1", "长" * 500, 3)])
    sessions = FakeSessions([Summary("s1", "读书", "上周聊了《小王子》", 1.0)])
    recall = MemoryRecall(store, turns, sessions)  # type: ignore[arg-type]

    result = await recall.recall(
        profile_id="default", query="上次说的书", since=12.0
    )

    assert [item.ref_id for item in result.facts] == ["f1"]
    assert len(result.turns[0].text) == 120
    assert result.turns[0].text.endswith("…")
    assert result.turns[0].title == "第 3 轮"
    assert result.summaries[0].title == "读书"
    assert result.fused
    assert store.calls == [("default", "上次说的书", 30)]
    assert turns.calls == [("上次说的书", 30)]
    assert sessions.calls == [("上次说的书", 20, 12.0)]


async def test_empty_query_skips_every_route() -> None:
    store = FakeStore([Fact("f1", "x")])
    turns = FakeTurns([Turn("t1", "y", 1)])
    sessions = FakeSessions([Summary("s1", None, "z", 1.0)])
    recall = MemoryRecall(store, turns, sessions)  # type: ignore[arg-type]

    result = await recall.recall(profile_id="default", query="   ")

    assert result.empty
    assert store.calls == []
    assert turns.calls == []
    assert sessions.calls == []


async def test_one_route_failure_keeps_the_others() -> None:
    store = FakeStore(error=RuntimeError("bge missing"))
    turns = FakeTurns([Turn("t1", "上次说的书", 2)])
    sessions = FakeSessions([Summary("s1", "读书", "聊了书", 1.0)])
    recall = MemoryRecall(store, turns, sessions)  # type: ignore[arg-type]

    result = await recall.recall(profile_id="default", query="书")

    assert result.facts == ()
    assert [item.ref_id for item in result.turns] == ["t1"]
    assert [item.ref_id for item in result.summaries] == ["s1"]
    assert result.fused


async def test_memory_off_still_retrieves_turns_and_summaries() -> None:
    turns = FakeTurns([Turn("t1", "上次说的书", 2)])
    sessions = FakeSessions([])
    recall = MemoryRecall(None, turns, sessions)  # type: ignore[arg-type]

    result = await recall.recall(profile_id="default", query="书")

    assert result.facts == ()
    assert result.turns


class FakeReranker:
    """按文本给固定分；`available` 可控以验证降级。"""

    def __init__(self, scores: dict[str, float], *, available: bool = True) -> None:
        self.scores = scores
        self.available = available
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def score(self, query: str, texts) -> list[float]:
        self.calls.append((query, tuple(texts)))
        return [self.scores.get(text, 0.0) for text in texts]


async def test_rerank_orders_layers_and_adds_entity_bonus() -> None:
    """R3b 3.4/3.6：final = sigmoid 分 + min(实体命中×0.1, 0.3)，按层重排。"""
    turns = FakeTurns(
        [
            Turn("plain", "今天喝咖啡", 1),
            Turn("entity", "我在学吉他", 2),
        ]
    )
    reranker = FakeReranker({"今天喝咖啡": 0.20, "我在学吉他": 0.15})
    recall = MemoryRecall(
        None, turns, FakeSessions([]), reranker=reranker  # type: ignore[arg-type]
    )

    result = await recall.recall(profile_id="default", query="上次说的吉他书")

    # 0.15 + 0.1（吉他命中）= 0.25 > 0.20
    assert [item.ref_id for item in result.turns] == ["entity", "plain"]
    assert result.turns[0].score == 0.25
    assert reranker.calls


async def test_min_score_filters_low_relevance() -> None:
    turns = FakeTurns(
        [
            Turn("keep", "上周聊过吉他", 1),
            Turn("drop", "今天喝咖啡", 2),
        ]
    )
    reranker = FakeReranker({"上周聊过吉他": 0.80, "今天喝咖啡": 0.05})
    recall = MemoryRecall(
        None,
        turns,
        FakeSessions([]),  # type: ignore[arg-type]
        reranker=reranker,
        min_score=0.5,
    )

    result = await recall.recall(profile_id="default", query="吉他")

    assert [item.ref_id for item in result.turns] == ["keep"]


async def test_unavailable_reranker_keeps_rrf_order() -> None:
    turns = FakeTurns([Turn("t1", "第一条", 1), Turn("t2", "第二条", 2)])
    reranker = FakeReranker({"第二条": 0.99}, available=False)
    recall = MemoryRecall(
        None, turns, FakeSessions([]), reranker=reranker  # type: ignore[arg-type]
    )

    result = await recall.recall(profile_id="default", query="看看")

    assert [item.ref_id for item in result.turns] == ["t1", "t2"]
    assert reranker.calls == []


class FakeChunks:
    def __init__(self, hits: list[ChunkHit], *, error: Exception | None = None) -> None:
        self.hits = hits
        self.error = error
        self.calls: list[tuple[int, str]] = []

    def search(self, vector, *, k: int, profile_id: str) -> list[ChunkHit]:
        _ = vector
        self.calls.append((k, profile_id))
        if self.error is not None:
            raise self.error
        return self.hits


async def test_vector_turn_hits_fuse_with_fts() -> None:
    """R3b 3.3b：FTS 与 chunk 向量各一路 → RRF；双路命中的 turn 排最前。"""
    turns = FakeTurns([Turn("t1", "我在学吉他", 1)])
    chunks = FakeChunks(
        [
            ChunkHit("c1", "t1", "s1", 1, "第一块：我在学吉他", 0.05),
            ChunkHit("c2", "t2", "s1", 2, "第二块：那很好", 0.20),
        ]
    )
    recall = MemoryRecall(
        FakeStore([]), turns, FakeSessions([]), chunks=chunks  # type: ignore[arg-type]
    )

    result = await recall.recall(profile_id="default", query="吉他")

    assert [item.ref_id for item in result.turns] == ["t1", "t2"]
    assert chunks.calls == [(30, "default")]


async def test_vector_route_failure_falls_back_to_fts() -> None:
    turns = FakeTurns([Turn("t1", "我在学吉他", 1)])
    chunks = FakeChunks([], error=RuntimeError("vec missing"))
    recall = MemoryRecall(
        FakeStore([]), turns, FakeSessions([]), chunks=chunks  # type: ignore[arg-type]
    )

    result = await recall.recall(profile_id="default", query="吉他")

    assert [item.ref_id for item in result.turns] == ["t1"]
