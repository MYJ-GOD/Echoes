"""MemoryExtractor：严格 JSON 解析、隐私过滤、替代语义与写入编排（5.2/13.3）。"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.memory.extractor import (
    MAX_FACTS_PER_TURN,
    ExtractedFact,
    MemoryExtractor,
)


class ScriptedLLM(LLMProvider):
    """按预设文本产出的 provider（抽取测试只关心解析与编排，不测模型）。"""

    def __init__(self, reply: str, *, name: str = "scripted") -> None:
        self.reply = reply
        self._name = name
        self.calls: list[list[dict[str, str]]] = []

    @property
    def name(self) -> str:
        return self._name

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
        self.calls.append(messages)
        yield self.reply


class FakeStore:
    """只记录写入参数的 MemoryStore 替身（不碰 SQLite / 嵌入）。"""

    def __init__(self, active: list[dict[str, str]] | None = None) -> None:
        self.active_facts = active or []
        self.writes: list[dict[str, Any]] = []
        self.active_calls = 0

    async def active(self, profile_id: str, *, limit: int = 200) -> list[dict[str, str]]:
        _ = (profile_id, limit)
        self.active_calls += 1
        return list(self.active_facts)

    async def remember(self, **kwargs: Any) -> object:
        self.writes.append(kwargs)
        return object()


def _reply(items: list[dict[str, Any]]) -> str:
    return json.dumps(items, ensure_ascii=False)


async def test_extract_parses_facts_and_injects_active_candidates() -> None:
    llm = ScriptedLLM(
        _reply(
            [
                {"fact": "用户喜欢手冲咖啡", "category": "preference", "replaces": None},
                {"fact": "用户下周去上海出差", "category": "event", "replaces": None},
            ]
        )
    )
    extractor = MemoryExtractor(llm)

    facts = await extractor.extract(
        "default",
        "用户：我每天都要喝手冲咖啡，下周去上海出差。",
        active_facts=[{"id": "f1", "fact": "用户养了一只猫", "category": "identity"}],
    )

    assert facts == [
        ExtractedFact("用户喜欢手冲咖啡", "preference"),
        ExtractedFact("用户下周去上海出差", "event"),
    ]
    prompt = llm.calls[0]
    assert prompt[0]["role"] == "system"
    assert "[f1] 用户养了一只猫（identity）" in prompt[1]["content"]


async def test_extract_accepts_markdown_fence() -> None:
    llm = ScriptedLLM(
        "```json\n" + _reply([{"fact": "用户喜欢猫", "category": "preference"}]) + "\n```"
    )
    facts = await MemoryExtractor(llm).extract("default", "用户：我喜欢猫。")
    assert facts == [ExtractedFact("用户喜欢猫", "preference")]


async def test_extract_rejects_non_json_output() -> None:
    llm = ScriptedLLM("好的，我记住了。")
    with pytest.raises(EchoesError) as exc_info:
        await MemoryExtractor(llm).extract("default", "用户：我喜欢猫。")
    assert exc_info.value.code is ErrorCode.INTERNAL_ERROR


async def test_extract_rejects_top_level_object() -> None:
    llm = ScriptedLLM('{"facts": [{"fact": "用户喜欢猫", "category": "preference"}]}')
    with pytest.raises(EchoesError):
        await MemoryExtractor(llm).extract("default", "用户：我喜欢猫。")


async def test_invalid_items_are_dropped_not_fatal() -> None:
    llm = ScriptedLLM(
        _reply(
            [
                {"fact": "用户喜欢猫", "category": "preference"},
                {"fact": "", "category": "preference"},
                {"fact": "用户住在杭州", "category": "bogus"},
                {"fact": "用户的密码是 abc123", "category": "identity"},
                {"fact": "用户手机号 13800138000", "category": "identity"},
                {"fact": "助手喜欢狗", "category": "preference"},
            ]
        )
    )
    facts = await MemoryExtractor(llm).extract("default", "用户：我喜欢猫。")
    assert facts == [ExtractedFact("用户喜欢猫", "preference")]


async def test_duplicate_facts_are_collapsed() -> None:
    llm = ScriptedLLM(
        _reply(
            [
                {"fact": "用户喜欢猫。", "category": "preference"},
                {"fact": "用户喜欢猫", "category": "preference"},
            ]
        )
    )
    facts = await MemoryExtractor(llm).extract("default", "用户：我喜欢猫。")
    assert facts == [ExtractedFact("用户喜欢猫。", "preference")]


async def test_replaces_only_accepts_known_ids() -> None:
    llm = ScriptedLLM(
        _reply(
            [
                {"fact": "面试改到周四", "category": "event", "replaces": "f1"},
                {"fact": "用户搬到上海", "category": "identity", "replaces": "f9"},
            ]
        )
    )
    facts = await MemoryExtractor(llm).extract(
        "default", "用户：面试改到周四，我搬到上海了。", active_facts=[
            {"id": "f1", "fact": "用户下周有面试", "category": "event"}
        ]
    )
    assert facts[0].replaces == "f1"
    assert facts[1].replaces is None


async def test_empty_transcript_skips_llm() -> None:
    llm = ScriptedLLM("[]")
    assert await MemoryExtractor(llm).extract("default", "   ") == []
    assert llm.calls == []


async def test_privacy_mode_skips_cloud_provider() -> None:
    llm = ScriptedLLM(
        _reply([{"fact": "用户喜欢猫", "category": "preference"}]),
        name="cloud:deepseek",
    )
    facts = await MemoryExtractor(llm, privacy_mode=True).extract("default", "用户：我喜欢猫。")
    assert facts == []
    assert llm.calls == []


async def test_extract_uses_store_active_when_not_given() -> None:
    store = FakeStore([{"id": "f1", "fact": "用户下周有面试", "category": "event"}])
    llm = ScriptedLLM("[]")
    await MemoryExtractor(llm, store=store).extract("default", "用户：你好。")  # type: ignore[arg-type]
    assert store.active_calls == 1


async def test_ingest_writes_supersede_and_degrades_on_conflict() -> None:
    store = FakeStore([{"id": "f1", "fact": "用户下周有面试", "category": "event"}])
    llm = ScriptedLLM(
        _reply(
            [
                {"fact": "面试改到周四", "category": "event", "replaces": "f1"},
                {"fact": "面试改到周五", "category": "event", "replaces": "f1"},
            ]
        )
    )
    extractor = MemoryExtractor(llm, store=store)  # type: ignore[arg-type]

    await extractor.ingest(
        "default",
        "用户：面试改到周四了，不对，是周五。",
        source_session_id="s1",
        source_turn=3,
    )

    assert [w["supersedes"] for w in store.writes] == ["f1", None]
    assert all(w["source_session_id"] == "s1" and w["source_turn"] == 3 for w in store.writes)


class _ConflictStore(FakeStore):
    """目标已被别的路径取代：带 supersedes 的写入抛错，验证退化新增。"""

    async def remember(self, **kwargs: Any) -> object:
        if kwargs.get("supersedes") is not None:
            self.writes.append(kwargs)
            raise EchoesError(ErrorCode.STORAGE_ERROR, "目标已不活跃")
        return await super().remember(**kwargs)


async def test_ingest_falls_back_when_supersede_target_is_gone() -> None:
    store = _ConflictStore([{"id": "f1", "fact": "用户下周有面试", "category": "event"}])
    llm = ScriptedLLM(
        _reply([{"fact": "面试改到周四", "category": "event", "replaces": "f1"}])
    )
    await MemoryExtractor(llm, store=store).ingest("default", "用户：面试改到周四了。")  # type: ignore[arg-type]
    assert [w.get("supersedes") for w in store.writes] == ["f1", None]


async def test_ingest_without_store_is_an_error() -> None:
    extractor = MemoryExtractor(ScriptedLLM("[]"))
    with pytest.raises(EchoesError):
        await extractor.ingest("default", "用户：你好。")


async def test_max_facts_per_turn_is_enforced() -> None:
    llm = ScriptedLLM(
        _reply(
            [
                {"fact": f"用户喜欢第{i}种茶", "category": "preference"}
                for i in range(MAX_FACTS_PER_TURN + 3)
            ]
        )
    )
    facts = await MemoryExtractor(llm).extract("default", "用户：我喜欢很多茶。")
    assert len(facts) == MAX_FACTS_PER_TURN
