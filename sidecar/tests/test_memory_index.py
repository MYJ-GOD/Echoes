"""R3b 3.3b：切块口径 + turn 原文索引器。"""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path

from echoes_sidecar.db.repo import Storage
from echoes_sidecar.memory.index import CHUNK_CHARS, TurnIndexer, split_text


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[1.0] + [0.0] * 511 for _ in texts]


def test_split_text_short_long_and_blank() -> None:
    assert split_text("  我在学吉他  ") == ["我在学吉他"]
    assert split_text("   ") == []
    long = "字" * (CHUNK_CHARS + 100)
    pieces = split_text(long)
    assert len(pieces) == 2
    assert all(piece for piece in pieces)
    # 重叠：第一块尾部出现在第二块里（避免关键短语正好被切口切断）
    first, second = pieces
    assert first[-10:] in second


async def test_indexer_rebuilds_and_reports_chunk_count(tmp_path: Path) -> None:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    now = time.time()
    persona = storage.personas.sync(
        persona_id="default", name="人设", system_prompt="s", now=now
    )
    storage.sessions.create(session_id="s1", persona_id=persona.id, now=now)
    turn = storage.turns.insert(session_id="s1", user_text="我在学吉他", now=now)
    storage.turns.finish(
        turn.turn_id, assistant_text="那很好", status="complete", now=now
    )
    row = storage.turns.get(turn.turn_id)
    assert row is not None

    embedder = FakeEmbedder()
    indexer = TurnIndexer(storage.chunks, embedder)
    assert await indexer.index_turn(row, now=1.0) == 1
    assert embedder.calls == [["我在学吉他 那很好"]]

    hits = storage.chunks.search([1.0] + [0.0] * 511, k=5)
    assert [hit.turn_id for hit in hits] == [turn.turn_id]
    assert "那很好" in hits[0].text

    # 幂等重建：同一 turn 再索引仍是 1 块
    assert await indexer.index_turn(row, now=2.0) == 1
    count = storage.conn.execute(
        "SELECT count(*) FROM turn_chunk WHERE turn_id = ?", (turn.turn_id,)
    ).fetchone()
    assert count is not None and int(count[0]) == 1
