"""TTS 热切换（R2a 2.5）：判据 4「换引擎不重启，下一句话就是新声音」。"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.engines.tts.router import TtsRouter


class FakeTts(TTSEngine):
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.closed = False

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        yield AudioChunk(data=self.tag.encode(), seq=0, is_final=True)

    async def clone(self, sample: AudioInputStream) -> str:
        _ = sample
        return f"voice:{self.tag}"

    async def aclose(self) -> None:
        self.closed = True


class OneChunkStream(AudioInputStream):
    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        async def gen() -> AsyncIterator[AudioChunk]:
            yield AudioChunk(data=b"\x00\x00", seq=0, is_final=True)

        return gen()


class Factory:
    def __init__(self) -> None:
        self.built: dict[str, FakeTts] = {}
        self.fail = False

    def __call__(self, name: str, model: str, base_url: str | None) -> TTSEngine:
        _ = base_url
        if self.fail:
            raise RuntimeError("boom")
        engine = FakeTts(f"{name}:{model}")
        self.built[name] = engine
        return engine


def _router(
    local: FakeTts, factory: Factory, *, provider: str = "cosyvoice2"
) -> TtsRouter:
    return TtsRouter(
        local, local_provider="cosyvoice2", factory=factory, provider=provider
    )


async def _drain(engine: TTSEngine) -> bytes:
    chunks = [chunk async for chunk in engine.synthesize("你好", "builtin:default")]
    assert chunks[-1].is_final
    return b"".join(chunk.data for chunk in chunks)


async def test_switch_provider_takes_effect_on_next_sentence() -> None:
    local = FakeTts("local")
    router = _router(local, Factory())
    assert router.current == ("cosyvoice2", "")
    assert await _drain(router) == b"local"

    await router.apply(
        provider="openai", model="tts-1-mini", base_url="https://api.example/v1"
    )
    assert router.current == ("openai", "tts-1-mini")
    assert await _drain(router) == b"openai:tts-1-mini"

    # 切回本地：必须复用组合根那一个实例（权重不重建）
    await router.apply(provider="cosyvoice2", model="")
    assert router.current[0] == "cosyvoice2"
    assert await _drain(router) == b"local"


async def test_unknown_provider_keeps_current_engine() -> None:
    local = FakeTts("local")
    router = _router(local, Factory())
    await router.apply(provider="whisper", model="x")
    assert router.current[0] == "cosyvoice2"
    assert await _drain(router) == b"local"


async def test_factory_failure_keeps_current_engine() -> None:
    local = FakeTts("local")
    factory = Factory()
    factory.fail = True
    router = _router(local, factory)
    await router.apply(
        provider="openai", model="tts-1", base_url="https://api.example/v1"
    )
    assert router.current[0] == "cosyvoice2"
    assert await _drain(router) == b"local"


async def test_privacy_mode_blocks_public_cloud_tts() -> None:
    local = FakeTts("local")
    router = _router(local, Factory())
    await router.apply(
        provider="openai",
        model="tts-1",
        base_url="https://api.example/v1",
        allow_cloud=False,
    )
    with pytest.raises(EchoesError) as err:
        await _drain(router)
    assert err.value.code is ErrorCode.TTS_ENGINE_ERROR
    assert "隐私模式" in err.value.message

    # 环回端点不算出网：隐私模式放行
    await router.apply(
        provider="openai",
        model="tts-1",
        base_url="http://127.0.0.1:1234/v1",
        allow_cloud=False,
    )
    assert await _drain(router) == b"openai:tts-1"


async def test_clone_delegates_to_active_engine() -> None:
    local = FakeTts("local")
    router = _router(local, Factory())
    assert await router.clone(OneChunkStream()) == "voice:local"


async def test_close_closes_only_cloud_engines() -> None:
    local = FakeTts("local")
    factory = Factory()
    router = _router(local, factory)
    await router.apply(
        provider="openai", model="tts-1", base_url="https://api.example/v1"
    )
    await router.apply(provider="cosyvoice2", model="")
    cloud = factory.built["openai"]
    await router.aclose()
    assert cloud.closed
    assert not local.closed
