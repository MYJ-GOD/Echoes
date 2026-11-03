"""ASR 热切换（R2a 2.5）：PTT 边界换引擎、隐私拦截、失败保留。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.asr.base import ASREngine
from echoes_sidecar.engines.asr.router import AsrRouter


class FakeAsr(ASREngine):
    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def transcribe(self, audio: AudioInputStream) -> AsyncIterator[dict[str, Any]]:
        async for _ in audio:
            pass
        yield {"text": self.tag, "is_final": True, "start_ms": 0, "end_ms": 0}


class Stream(AudioInputStream):
    def __aiter__(self):
        async def gen():
            yield AudioChunk(data=b"\x00\x00", seq=0, is_final=True)

        return gen()


class Factory:
    def __init__(self) -> None:
        self.fail = False
        self.built: dict[str, FakeAsr] = {}

    def __call__(self, provider: str, model: str, base_url: str | None) -> ASREngine:
        _ = base_url
        if self.fail:
            raise RuntimeError("boom")
        engine = FakeAsr(f"{provider}:{model}")
        self.built[provider] = engine
        return engine


def _router(local: FakeAsr, factory: Factory | None = None, *, provider="whisper"):
    return AsrRouter(
        local,
        local_provider="whisper",
        factory=factory or Factory(),
        provider=provider,
    )


async def _text(engine: ASREngine) -> str:
    segments = [seg async for seg in engine.transcribe(Stream())]
    assert segments[-1]["is_final"]
    return "".join(str(seg["text"]) for seg in segments)


async def test_switch_asr_takes_effect_on_next_utterance() -> None:
    local = FakeAsr("local")
    router = _router(local)
    assert router.current == ("whisper", "")
    assert await _text(router) == "local"

    await router.apply(
        provider="openai", model="whisper-1", base_url="https://api.example/v1"
    )
    assert router.current == ("openai", "whisper-1")
    assert await _text(router) == "openai:whisper-1"

    await router.apply(provider="whisper", model="small")
    assert await _text(router) == "local"


async def test_unknown_provider_and_failure_keep_current() -> None:
    local = FakeAsr("local")
    factory = Factory()
    router = _router(local, factory)
    await router.apply(provider="sensevoice", model="x")
    assert router.current[0] == "whisper"

    factory.fail = True
    await router.apply(
        provider="openai", model="whisper-1", base_url="https://api.example/v1"
    )
    assert router.current[0] == "whisper"
    assert await _text(router) == "local"


async def test_privacy_mode_blocks_public_cloud_asr() -> None:
    local = FakeAsr("local")
    router = _router(local, Factory())
    await router.apply(
        provider="openai",
        model="whisper-1",
        base_url="https://api.example/v1",
        allow_cloud=False,
    )
    with pytest.raises(EchoesError) as err:
        await _text(router)
    assert err.value.code is ErrorCode.ASR_ENGINE_ERROR
    assert "隐私模式" in err.value.message

    # 环回端点不算出网
    await router.apply(
        provider="openai",
        model="whisper-1",
        base_url="http://127.0.0.1:1234/v1",
        allow_cloud=False,
    )
    assert await _text(router) == "openai:whisper-1"


async def test_switching_to_unassembled_whisper_keeps_mock() -> None:
    local = FakeAsr("mock-local")
    router = AsrRouter(local, local_provider="mock", provider="mock")
    await router.apply(provider="whisper", model="small")
    assert router.current[0] == "mock"
    assert await _text(router) == "mock-local"
