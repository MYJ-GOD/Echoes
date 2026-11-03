"""R3b 3.3b 原文索引：turn 完成后切块 + 嵌入 + 落 vec0。

**为什么在 turn 收尾异步做**：嵌入是 CPU 前向（几十到几百毫秒），不能进 turn
关键路径；索引失败只记 stderr——下一轮检索少了这块原文，不影响已经完成的对话。

**chunk 口径**：按字符窗口（240 字，40 字重叠）切，而不是按句：原文检索要能
命中「中间那句」，句子边界由 `audio/chunker` 管的是 TTS，不是检索。重叠避免
关键短语正好落在切口上被切成两半。
"""

from __future__ import annotations

import asyncio
import time

from echoes_sidecar.db.chunk_repo import ChunkRepo
from echoes_sidecar.db.repo import TurnRow
from echoes_sidecar.memory.embedding import Embedder

CHUNK_CHARS = 240
CHUNK_OVERLAP = 40
EMBEDDING_MODEL_NAME = "bge-small-zh-v1.5"


def split_text(
    text: str, *, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """按窗口切块（空白归一；空白文本返回空表）。"""
    clean = " ".join(text.split())
    if not clean:
        return []
    if len(clean) <= size:
        return [clean]
    step = max(1, size - overlap)
    chunks: list[str] = []
    for start in range(0, len(clean), step):
        piece = clean[start : start + size].strip()
        if piece:
            chunks.append(piece)
        if start + size >= len(clean):
            break
    return chunks


class TurnIndexer:
    """turn 原文 → chunk 向量（幂等：同一 turn 重建时先删旧索引）。"""

    def __init__(
        self,
        chunks: ChunkRepo,
        embedder: Embedder,
        *,
        model: str = EMBEDDING_MODEL_NAME,
    ) -> None:
        self._chunks = chunks
        self._embedder = embedder
        self._model = model

    async def index_turn(self, turn: TurnRow, *, now: float | None = None) -> int:
        text = turn.user_text
        if turn.assistant_text:
            text = f"{text}\n{turn.assistant_text}"
        pieces = split_text(text)
        if not pieces:
            return 0
        vectors = await self._embedder.embed(pieces)
        return await asyncio.to_thread(
            self._chunks.upsert,
            turn.turn_id,
            list(zip(pieces, vectors, strict=True)),
            model=self._model,
            now=time.time() if now is None else now,
        )


__all__ = [
    "CHUNK_CHARS",
    "CHUNK_OVERLAP",
    "EMBEDDING_MODEL_NAME",
    "TurnIndexer",
    "split_text",
]
