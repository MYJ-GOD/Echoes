"""R3a 编排接线：三层注入、预算裁剪、来源回溯写 `turn_memory_ref`。"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from echoes_sidecar.core.types import Persona
from echoes_sidecar.db.repo import Storage
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.memory.index import TurnIndexer
from echoes_sidecar.memory.recall import RecallItem, RecallResult
from echoes_sidecar.orchestration.graph import (
    FACT_BUDGET_CHARS,
    SUMMARY_BUDGET_CHARS,
    TriggerSource,
)
from echoes_sidecar.session.session import Session
from tests.conftest import make_graph
from tests.fakes import BoomTTS


class CaptureLLM(LLMProvider):
    def __init__(self) -> None:
        self.messages: list[list[dict[str, str]]] = []

    @property
    def name(self) -> str:
        return "capture"

    async def health(self) -> bool:
        return True

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        _ = (stream, max_tokens, temperature)
        self.messages.append(messages)
        yield "嗯，我记得。"


class FakeRecall:
    def __init__(self, result: RecallResult) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def recall(self, **kwargs: Any) -> RecallResult:
        self.calls.append(kwargs)
        return self.result


def _setup(tmp_path: Path) -> tuple[Storage, Session]:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    now = time.time()
    persona = storage.personas.sync(
        persona_id="default", name="默认人设", system_prompt="s", now=now
    )
    row = storage.sessions.create(session_id="default", persona_id=persona.id, now=now)
    session = Session(
        session_id=row.id,
        profile_id=row.profile_id,
        persona=Persona(
            id=persona.id,
            name=persona.name,
            system_prompt=persona.system_prompt,
            created_at=persona.created_at,
            updated_at=persona.updated_at,
        ),
        created_at=row.started_at,
    )
    return storage, session


def _fact(storage: Storage, fact_id: str, text: str) -> RecallItem:
    storage.memories.insert(
        fact_id=fact_id,
        fact=text,
        category="preference",
        embedding=[0.0] * 512,
        now=time.time(),
    )
    return RecallItem("fact", fact_id, text)


async def test_three_layers_injected_and_refs_written(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    fact = _fact(storage, "fact-1", "用户喜欢猫")
    result = RecallResult(
        facts=(fact,),
        turns=(RecallItem("turn", "turn-x", "上次说的书是《小王子》", title="第 3 轮"),),
        summaries=(RecallItem("summary", "s-old", "上周聊了读书", title="读书"),),
    )
    llm = CaptureLLM()
    graph = make_graph(
        llm=llm,
        storage=storage,
        recall=FakeRecall(result),  # type: ignore[arg-type]
    )

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "上次说的书叫什么"}
    )

    assert outcome.status == "SUCCESS"
    system = llm.messages[0][0]["content"]
    assert "关于用户的已知信息" in system and "用户喜欢猫" in system
    assert "其他会话的相关摘要" in system and "上周聊了读书" in system
    assert "可能相关的历史原话" in system and "小王子" in system

    turns = storage.turns.list_session("default")
    assert turns, "turn 应已落盘"
    assert storage.turns.memory_refs(turns[-1].turn_id) == ["fact-1"]
    assert storage.turns.turns_for_fact("fact-1") == [turns[-1].turn_id]


async def test_layer_budgets_clip_oversized_blocks(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    huge = "事实" * 400
    result = RecallResult(
        facts=tuple(
            RecallItem("fact", f"f{i}", huge) for i in range(5)
        ),
        summaries=(RecallItem("summary", "s1", "摘要" * 500, title="长摘要"),),
        turns=(RecallItem("turn", "t1", "原文" * 500),),
    )
    llm = CaptureLLM()
    graph = make_graph(
        llm=llm,
        storage=storage,
        recall=FakeRecall(result),  # type: ignore[arg-type]
    )

    # 只走组装，不跑完整 turn（避免无关的 memory_fact 外键写入）
    composed = await graph._compose_turn(session, "随便问问")
    system = composed.messages[0]["content"]

    fact_block = system.split("别逐条复述）：\n", 1)[1].split("\n\n", 1)[0]
    assert len(fact_block) <= FACT_BUDGET_CHARS
    summary_block = system.split("其他会话的相关摘要：\n", 1)[1].split("\n\n", 1)[0]
    assert len(summary_block) <= SUMMARY_BUDGET_CHARS
    assert composed.fact_ids == ["f0"]


async def test_recall_failure_keeps_turn_clean(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)

    class BoomRecall:
        async def recall(self, **_: Any) -> RecallResult:
            raise RuntimeError("boom")

    llm = CaptureLLM()
    graph = make_graph(
        llm=llm,
        storage=storage,
        recall=BoomRecall(),  # type: ignore[arg-type]
    )

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "你好"}
    )

    assert outcome.status == "SUCCESS"
    assert llm.messages[0][0]["content"] == "s"
    assert storage.turns.memory_refs(storage.turns.list_session("default")[-1].turn_id) == []


async def test_rewritten_query_drives_recall(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)

    class FakeRewriter:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def rewrite(
            self, question: str, recent: Any, *, force: bool = False
        ) -> str:
            _ = (recent, force)
            self.calls.append(question)
            return "你上次说的《小王子》"

    class QueryRecall:
        def __init__(self) -> None:
            self.queries: list[str] = []

        async def recall(self, **kwargs: Any) -> RecallResult:
            self.queries.append(str(kwargs["query"]))
            return RecallResult(
                turns=(RecallItem("turn", "t1", "上次说的书是《小王子》"),)
            )

    rewriter = FakeRewriter()
    recall = QueryRecall()
    llm = CaptureLLM()
    graph = make_graph(
        llm=llm,
        storage=storage,
        recall=recall,  # type: ignore[arg-type]
        rewriter=rewriter,  # type: ignore[arg-type]
    )

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "它怎么样"})

    assert rewriter.calls == ["它怎么样"]
    assert recall.queries == ["你上次说的《小王子》"]
    assert "《小王子》" in llm.messages[0][0]["content"]


class FakeEmbedder:
    async def embed(self, texts: Any) -> list[list[float]]:
        return [[1.0] + [0.0] * 511 for _ in texts]


async def test_successful_turn_indexes_chunks(tmp_path: Path) -> None:
    """R3b 3.3b：turn 收尾后异步切块 + 嵌入，原文可被向量检索命中。"""
    storage, session = _setup(tmp_path)
    graph = make_graph(
        llm=CaptureLLM(),
        storage=storage,
        indexer=TurnIndexer(storage.chunks, FakeEmbedder()),  # type: ignore[arg-type]
    )

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "我在学吉他"}
    )
    await graph.wait_memory_idle()

    assert outcome.status == "SUCCESS"
    count = storage.conn.execute("SELECT count(*) FROM turn_chunk").fetchone()
    assert count is not None and int(count[0]) == 1
    hits = storage.chunks.search([1.0] + [0.0] * 511, k=5)
    assert len(hits) == 1
    assert "我在学吉他" in hits[0].text


async def test_failed_turn_does_not_index(tmp_path: Path) -> None:
    storage, session = _setup(tmp_path)
    graph = make_graph(
        tts=BoomTTS(),
        storage=storage,
        indexer=TurnIndexer(storage.chunks, FakeEmbedder()),  # type: ignore[arg-type]
    )

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "我在学吉他"}
    )
    await graph.wait_memory_idle()

    assert outcome.status == "FAILED"
    count = storage.conn.execute("SELECT count(*) FROM turn_chunk").fetchone()
    assert count is not None and int(count[0]) == 0
