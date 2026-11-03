"""R4 4.3 Grounding judge：JSON 容错、mock 跳过、空证据短路。"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.memory.grounding import GroundingResult, LLMGroundingJudge


class FakeLLM(LLMProvider):
    def __init__(self, reply: str = "{}", *, name: str = "fake") -> None:
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


async def test_parses_bare_and_fenced_json() -> None:
    payload = '{"faithful": false, "score": 0.4, "unsupported_claims": ["用户养了狗"]}'
    for reply in (payload, f"```json\n{payload}\n```", f"结果：{payload}"):
        judge = LLMGroundingJudge(FakeLLM(reply))  # type: ignore[arg-type]
        result = await judge.check("你养了狗吧", ["用户喜欢猫"])
        assert result == GroundingResult(False, 0.4, ("用户养了狗",))


async def test_invalid_output_raises() -> None:
    judge = LLMGroundingJudge(FakeLLM("看起来没问题"))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        await judge.check("回复", ["证据"])


async def test_score_is_clamped() -> None:
    judge = LLMGroundingJudge(
        FakeLLM('{"faithful": true, "score": 1.9, "unsupported_claims": []}')  # type: ignore[arg-type]
    )
    result = await judge.check("回复", ["证据"])
    assert result.score == 1.0 and result.faithful


async def test_mock_llm_is_unavailable_and_not_called() -> None:
    llm = FakeLLM('{"faithful": true, "score": 1}', name="mock")
    judge = LLMGroundingJudge(llm)  # type: ignore[arg-type]
    assert judge.available is False
    result = await judge.check("回复", ["证据"])
    assert result.faithful and result.score == 1.0
    assert llm.calls == []


async def test_empty_reply_or_evidence_short_circuits() -> None:
    llm = FakeLLM('{"faithful": false, "score": 0}')
    judge = LLMGroundingJudge(llm)  # type: ignore[arg-type]
    assert (await judge.check("   ", ["证据"])).faithful
    assert (await judge.check("回复", [])).faithful
    assert llm.calls == []


async def test_timeout_raises() -> None:
    class SlowLLM(FakeLLM):
        async def generate(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            _ = (args, kwargs)
            await asyncio.sleep(0.2)
            yield "{}"

    judge = LLMGroundingJudge(SlowLLM(), timeout=0.01)
    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await judge.check("回复", ["证据"])
