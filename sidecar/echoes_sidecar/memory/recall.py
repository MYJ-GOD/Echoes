"""R3a 检索链：事实（向量）+ 原文（FTS）+ 摘要（LIKE）→ RRF 融合。

**为什么先落两路**：§4.2 的五段链路里，向量召回（R3b）与 rerank（R3b）还没
就位；R3a 用「向量查事实 + FTS 查原文 + 摘要查会话」覆盖三类问题：

| 问题 | 命中源 |
|---|---|
| 「我是谁 / 我喜欢什么」 | `memory_fact`（向量） |
| 「上次聊的那本书叫什么」 | `turn` 原文（`turn_fts` + jieba 分词） |
| 「我们上周在聊什么」 | `session_summary`（标题+摘要 LIKE + 时间过滤） |

**RRF（k=60）现在用来定「跨源优先级」**：预算紧张时按融合分裁掉最不相关的
条目；等 R3b 接入向量原文召回后，同一个 `rrf_fuse` 直接融合两路同源结果，
不用改调用方。

**失败语义**：单路检索失败只记 stderr，其余路照常返回；全部失败返回空结果。
记忆是增强项——错误记忆比没有记忆更毒，但「检索坏了就聊不了」也不可接受。
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, replace
from typing import Literal

from echoes_sidecar.db.chunk_repo import ChunkRepo
from echoes_sidecar.db.repo import SessionRepo, TurnRepo
from echoes_sidecar.memory.entities import entity_bonus, query_entities
from echoes_sidecar.memory.rerank import DEFAULT_MIN_SCORE, Reranker
from echoes_sidecar.memory.store import MemoryStore

RRF_K = 60
FACT_RECALL = 30
TURN_RECALL = 30
SUMMARY_RECALL = 20
# 原文命中进 prompt 的截断长度：一条 turn 可能很长，给「指代/回溯」只需片段
TURN_SNIPPET_CHARS = 120

RecallSource = Literal["fact", "turn", "summary"]


@dataclass(frozen=True)
class RecallItem:
    source: RecallSource
    ref_id: str
    text: str
    title: str = ""
    score: float = 0.0


@dataclass(frozen=True)
class RecallResult:
    facts: tuple[RecallItem, ...] = ()
    turns: tuple[RecallItem, ...] = ()
    summaries: tuple[RecallItem, ...] = ()
    fused: tuple[RecallItem, ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.facts or self.turns or self.summaries)


def rrf_fuse(ranked_lists: list[list[RecallItem]], *, k: int = RRF_K) -> tuple[RecallItem, ...]:
    """Reciprocal Rank Fusion：score = Σ 1/(k + rank)，rank 从 0 起。"""
    scores: dict[tuple[str, str], float] = {}
    items: dict[tuple[str, str], RecallItem] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked):
            key = (item.source, item.ref_id)
            items[key] = item
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    ordered = sorted(
        items.values(),
        key=lambda item: (-scores[(item.source, item.ref_id)], item.source, item.ref_id),
    )
    return tuple(
        replace(item, score=scores[(item.source, item.ref_id)]) for item in ordered
    )


class MemoryRecall:
    """三路检索的统一入口（组合根构造；编排层只拿 RecallResult）。"""

    def __init__(
        self,
        store: MemoryStore | None,
        turns: TurnRepo | None,
        sessions: SessionRepo | None,
        *,
        chunks: ChunkRepo | None = None,
        reranker: Reranker | None = None,
        rerank_top_n: int = 8,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> None:
        self._store = store
        self._turns = turns
        self._sessions = sessions
        self._chunks = chunks
        self._reranker = reranker
        self._rerank_top_n = rerank_top_n
        self._min_score = min_score

    async def recall(
        self,
        *,
        profile_id: str,
        query: str,
        since: float | None = None,
        facts_k: int = FACT_RECALL,
        turns_k: int = TURN_RECALL,
        summaries_k: int = SUMMARY_RECALL,
    ) -> RecallResult:
        text = query.strip()
        if not text:
            return RecallResult()

        fact_items = await self._facts(profile_id, text, facts_k)
        turn_items = await self._turn_hits(text, turns_k, profile_id)
        summary_items = await self._summary_hits(text, summaries_k, since)
        fact_items, turn_items, summary_items = await self._refine(
            text, fact_items, turn_items, summary_items
        )
        fused = rrf_fuse([list(fact_items), list(turn_items), list(summary_items)])
        return RecallResult(
            facts=tuple(fact_items),
            turns=tuple(turn_items),
            summaries=tuple(summary_items),
            fused=fused,
        )

    async def _refine(
        self,
        query: str,
        facts: list[RecallItem],
        turns: list[RecallItem],
        summaries: list[RecallItem],
    ) -> tuple[list[RecallItem], list[RecallItem], list[RecallItem]]:
        """R3b 3.4–3.6：精排 → 实体加分 → 阈值门禁（按层独立）。

        reranker 不可用（没装权重/加载失败）时原样返回：保留 RRF 顺序，
        绝不让「没下模型」变成「没有记忆」。
        """
        if self._reranker is None or not self._reranker.available:
            return facts, turns, summaries
        entities = query_entities(query)
        refined = [
            await self._refine_layer(query, entities, items)
            for items in (facts, turns, summaries)
        ]
        return refined[0], refined[1], refined[2]

    async def _refine_layer(
        self, query: str, entities: tuple[str, ...], items: list[RecallItem]
    ) -> list[RecallItem]:
        reranker = self._reranker
        if not items or reranker is None or not reranker.available:
            return items
        candidates = items[: max(1, self._rerank_top_n)]
        scores = await asyncio.to_thread(
            reranker.score, query, [item.text for item in candidates]
        )
        scored: list[RecallItem] = []
        for item, raw in zip(candidates, scores, strict=False):
            final = max(0.0, min(1.0, float(raw))) + entity_bonus(entities, item.text)
            if final < self._min_score:
                continue
            scored.append(replace(item, score=final))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored

    # ------------------------------ 三路 ------------------------------

    async def _facts(self, profile_id: str, query: str, k: int) -> list[RecallItem]:
        if self._store is None or k <= 0:
            return []
        try:
            facts = await self._store.search(profile_id, query, k=k)
        except Exception as exc:  # noqa: BLE001  单路失败不拖垮其它路
            print(f"[sidecar] 事实检索失败（本轮无事实层）: {exc}", file=sys.stderr)
            return []
        return [RecallItem("fact", fact.id, fact.fact) for fact in facts if fact.id]

    async def _turn_hits(
        self, query: str, k: int, profile_id: str
    ) -> list[RecallItem]:
        """原文两路：FTS（字面命中）+ chunk 向量（语义命中）→ RRF。"""
        if k <= 0:
            return []
        fts_items = await self._fts_turn_hits(query, k)
        vector_items = await self._vector_turn_hits(query, k, profile_id)
        if not vector_items:
            return fts_items
        return list(rrf_fuse([fts_items, vector_items]))

    async def _fts_turn_hits(self, query: str, k: int) -> list[RecallItem]:
        if self._turns is None:
            return []
        try:
            rows = await asyncio.to_thread(self._turns.search, query, limit=k)
        except Exception as exc:  # noqa: BLE001
            print(f"[sidecar] 原文检索失败（本轮无原文层）: {exc}", file=sys.stderr)
            return []
        items: list[RecallItem] = []
        for row in rows:
            if not row.turn_id:
                continue
            text = _snippet(row.user_text)
            if not text:
                continue
            items.append(RecallItem("turn", row.turn_id, text, title=f"第 {row.seq} 轮"))
        return items

    async def _vector_turn_hits(
        self, query: str, k: int, profile_id: str
    ) -> list[RecallItem]:
        if self._store is None or self._chunks is None:
            return []
        try:
            vector = await self._store.embed(query)
            hits = await asyncio.to_thread(
                self._chunks.search, vector, k=k, profile_id=profile_id
            )
        except Exception as exc:  # noqa: BLE001  向量路失败只丢这一路
            print(f"[sidecar] 原文向量检索失败（本轮退回 FTS）: {exc}", file=sys.stderr)
            return []
        items: list[RecallItem] = []
        for hit in hits:
            text = _snippet(hit.text)
            if not text:
                continue
            items.append(
                RecallItem("turn", hit.turn_id, text, title=f"第 {hit.seq} 轮")
            )
        return items

    async def _summary_hits(
        self, query: str, k: int, since: float | None
    ) -> list[RecallItem]:
        if self._sessions is None or k <= 0:
            return []
        try:
            rows = await asyncio.to_thread(
                self._sessions.search_summaries, query, limit=k, since=since
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[sidecar] 摘要检索失败（本轮无摘要层）: {exc}", file=sys.stderr)
            return []
        return [
            RecallItem(
                "summary",
                row.session_id,
                _snippet(row.summary),
                title=row.title or "未命名会话",
            )
            for row in rows
        ]


def _snippet(text: str, limit: int = TURN_SNIPPET_CHARS) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1] + "…"


__all__ = [
    "FACT_RECALL",
    "MemoryRecall",
    "RRF_K",
    "RecallItem",
    "RecallResult",
    "SUMMARY_RECALL",
    "TURN_RECALL",
    "rrf_fuse",
]
