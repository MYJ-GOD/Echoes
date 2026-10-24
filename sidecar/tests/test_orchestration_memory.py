"""编排层记忆接线（5.2）：检索进 system、成功后异步抽取、失败不反噬 turn。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.orchestration.graph import TriggerSource
from tests.conftest import RecordingTransport, make_graph, make_session
from tests.fakes import BoomTTS


class CaptureLLM(LLMProvider):
    """记录每次调用收到的 messages，并按预设片段产出。"""

    def __init__(self, pieces: list[str] | None = None) -> None:
        self.pieces = pieces or ["今天有点累。"]
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
        for piece in self.pieces:
            yield piece


class FakeMemory:
    """MemoryStore 替身：只关心检索参数与返回 hint。"""

    def __init__(
        self,
        hits: list[dict[str, str]] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.hits = hits or []
        self.error = error
        self.calls: list[tuple[str, str, int]] = []

    async def retrieve(
        self, profile_id: str, query: str, *, k: int = 5
    ) -> list[dict[str, str]]:
        self.calls.append((profile_id, query, k))
        if self.error is not None:
            raise self.error
        return self.hits

    def compose_hint(self, facts: list[dict[str, str]]) -> str:
        if not facts:
            return ""
        return "关于用户的已知信息（只在相关时自然提起，别逐条复述）：\n" + "\n".join(
            f"- {item['fact']}" for item in facts
        )


class FakeExtractor:
    """MemoryExtractor 替身：记录 ingest 参数；可注入失败。"""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def ingest(
        self,
        profile_id: str,
        transcript: str,
        *,
        active_facts: Any = None,
        source_session_id: str | None = None,
        source_turn: int | None = None,
    ) -> list[object]:
        _ = active_facts
        self.calls.append(
            {
                "profile_id": profile_id,
                "transcript": transcript,
                "source_session_id": source_session_id,
                "source_turn": source_turn,
            }
        )
        if self.error is not None:
            raise self.error
        return []


async def test_retrieval_hint_is_injected_into_system_prompt() -> None:
    llm = CaptureLLM()
    memory = FakeMemory([{"fact": "用户喜欢猫", "category": "preference"}])
    graph = make_graph(llm=llm, memory=memory)  # type: ignore[arg-type]
    session = make_session()

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "我最近怎么样"}
    )

    assert outcome.status == "SUCCESS"
    assert memory.calls == [("default", "我最近怎么样", 5)]
    system, user = llm.messages[0]
    assert system["role"] == "system"
    assert system["content"].startswith("s")
    assert "- 用户喜欢猫" in system["content"]
    assert user == {"role": "user", "content": "我最近怎么样"}


async def test_empty_retrieval_injects_nothing() -> None:
    llm = CaptureLLM()
    memory = FakeMemory([])
    graph = make_graph(llm=llm, memory=memory)  # type: ignore[arg-type]

    await graph.run_turn(make_session(), TriggerSource.USER_INPUT, {"text": "你好"})

    assert llm.messages[0][0]["content"] == "s"


async def test_retrieval_failure_keeps_turn_successful() -> None:
    """bge 权重缺失/库坏：本轮无记忆继续聊，不产生 error 帧。"""
    transport = RecordingTransport()
    llm = CaptureLLM()
    memory = FakeMemory(error=EchoesError(ErrorCode.MODEL_NOT_LOADED, "bge missing"))
    graph = make_graph(transport, llm=llm, memory=memory)  # type: ignore[arg-type]

    outcome = await graph.run_turn(
        make_session(), TriggerSource.USER_INPUT, {"text": "你好"}
    )

    assert outcome.status == "SUCCESS"
    assert transport.only_turn_complete()["status"] == "SUCCESS"
    assert transport.of_type("error") == []
    assert llm.messages[0][0]["content"] == "s"


async def test_successful_turn_schedules_extraction() -> None:
    extractor = FakeExtractor()
    graph = make_graph(llm=CaptureLLM(["今天", "有点累。"]), extractor=extractor)  # type: ignore[arg-type]
    session = make_session()

    outcome = await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "在吗"})
    await graph.wait_memory_idle()

    assert outcome.status == "SUCCESS"
    assert extractor.calls == [
        {
            "profile_id": "default",
            "transcript": "用户：在吗\n助手：今天有点累。",
            "source_session_id": "default",
            "source_turn": 1,
        }
    ]


async def test_extraction_failure_does_not_affect_turn() -> None:
    transport = RecordingTransport()
    extractor = FakeExtractor(error=RuntimeError("boom"))
    graph = make_graph(transport, extractor=extractor)  # type: ignore[arg-type]

    outcome = await graph.run_turn(
        make_session(), TriggerSource.USER_INPUT, {"text": "你好"}
    )
    await graph.wait_memory_idle()

    assert outcome.status == "SUCCESS"
    assert transport.only_turn_complete()["status"] == "SUCCESS"
    assert transport.of_type("error") == []
    assert graph.machine.state.value == "ready"


async def test_failed_turn_skips_extraction() -> None:
    extractor = FakeExtractor()
    graph = make_graph(tts=BoomTTS(), extractor=extractor)  # type: ignore[arg-type]

    outcome = await graph.run_turn(
        make_session(), TriggerSource.USER_INPUT, {"text": "你好"}
    )
    await graph.wait_memory_idle()

    assert outcome.status == "FAILED"
    assert extractor.calls == []
