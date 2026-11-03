"""memory store：事实写入 + sqlite-vec 检索（文档 5.1/5.2）。

检索时机（5.2）：每轮 turn 开始前，用用户输入 query 检索 top-k 相关 fact
（sqlite-vec 暴力扫描，k=5~8）拼进 system prompt。

边界：本模块只管「事实 ↔ 向量」的搬运与排序；**什么时候检索、怎么拼进 prompt
归编排层**（5.2 上下文预算在 `TurnGraph._compose_messages`），抽取归
`memory/extractor.py`（13.3 门禁在那条线上）。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Sequence

from echoes_sidecar.db.memory_repo import MemoryFact, MemoryRepo
from echoes_sidecar.memory.embedding import Embedder


class MemoryStore:
    """事实的写（insert/supersede/touch/delete）与读（retrieve）。"""

    def __init__(self, repo: MemoryRepo, embedder: Embedder) -> None:
        self._repo = repo
        self._embedder = embedder

    @property
    def embedder(self) -> Embedder:
        """组合根给原文索引器复用同一个嵌入器（避免加载两份 bge）。"""
        return self._embedder

    async def embed(self, text: str) -> list[float]:
        """query → 向量（原文 chunk 召回用）。"""
        [vector] = await self._embedder.embed([text])
        return vector

    async def search(
        self, profile_id: str, query: str, *, k: int = 5
    ) -> list[MemoryFact]:
        """向量检索原始行（含 id / 来源，供编排层做来源回溯；不直接进 prompt）。"""
        text = query.strip()
        if not text:
            return []
        [vector] = await self._embedder.embed([text])
        return await asyncio.to_thread(
            self._repo.search, vector, k=k, profile_id=profile_id
        )

    async def retrieve(
        self, profile_id: str, query: str, *, k: int = 5
    ) -> list[dict[str, str]]:
        """按向量相似度检索 top-k 事实（q：fact 文本域）。

        返回 `[{"fact": ..., "category": ...}]`：**只暴露这两列**——id / 来源会话
        是内部账，不该泄进 prompt（5.2 隐私面最小化）。
        """
        facts = await self.search(profile_id, query, k=k)
        return [{"fact": fact.fact, "category": fact.category} for fact in facts]

    async def remember(
        self,
        *,
        fact: str,
        category: str,
        profile_id: str = "default",
        source_session_id: str | None = None,
        source_turn: int | None = None,
        supersedes: str | None = None,
    ) -> MemoryFact:
        """落一条事实（`supersedes` 给了就走取代路径，历史保留可追溯）。"""
        [vector] = await self._embedder.embed([fact])
        now = time.time()
        fact_id = uuid.uuid4().hex
        if supersedes is None:
            return await asyncio.to_thread(
                lambda: self._repo.insert(
                    fact_id=fact_id,
                    fact=fact,
                    category=category,
                    embedding=vector,
                    now=now,
                    profile_id=profile_id,
                    source_session_id=source_session_id,
                    source_turn=source_turn,
                )
            )
        return await asyncio.to_thread(
            lambda: self._repo.supersede(
                supersedes,
                fact_id=fact_id,
                fact=fact,
                category=category,
                embedding=vector,
                now=now,
                profile_id=profile_id,
                source_session_id=source_session_id,
                source_turn=source_turn,
            )
        )

    async def active(
        self, profile_id: str = "default", *, limit: int = 200
    ) -> list[MemoryFact]:
        """当前有效事实（UI 的记忆管理面用）。"""
        return await asyncio.to_thread(self._repo.list_active, profile_id, limit=limit)

    async def forget(self, fact_id: str) -> None:
        """删除一条事实（16.2：软删标记 + 向量真删，删完检索不到）。"""
        await asyncio.to_thread(self._repo.delete, fact_id)

    def compose_hint(self, facts: Sequence[dict[str, str]]) -> str:
        """把检索结果拼成 system prompt 的一段（无命中返回空串，不塞空标签）。

        口径（5.2）：只陈述「关于用户的已知事实」，不解释来源、不编关联——
        提示词里多说一句，模型就可能多编一句。
        """
        lines = [f"- {item['fact']}" for item in facts if item.get("fact")]
        if not lines:
            return ""
        return "关于用户的已知信息（只在相关时自然提起，别逐条复述）：\n" + "\n".join(lines)


__all__ = ["MemoryStore"]
