"""OpenAI 兼容 TTS（R2a 2.3）：PCM 直取、分句、鉴权与错误口径。"""

from __future__ import annotations

import json

import httpx
import pytest

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import CloneError, EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.tts.openai_tts import OpenAITtsEngine


def _engine(handler, *, key: str | None = "sk-test") -> OpenAITtsEngine:
    return OpenAITtsEngine(
        base_url="https://api.example/v1",
        api_key=key,
        transport=httpx.MockTransport(handler),
    )


class OneChunkStream(AudioInputStream):
    def __aiter__(self):
        async def gen():
            yield AudioChunk(data=b"\x00\x00", seq=0, is_final=True)

        return gen()


async def _collect(engine: OpenAITtsEngine, text: str, voice: str = "builtin:default"):
    return [chunk async for chunk in engine.synthesize(text, voice)]


async def test_pcm_is_split_into_100ms_chunks_with_single_final() -> None:
    seen: list[dict] = []
    # 150ms @24k mono PCM16 = 7200 字节 → 两个 chunk（100ms + 50ms）
    payload = b"\x01\x00" * 3600

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, content=payload, request=request)

    engine = _engine(handler)
    chunks = await _collect(engine, "第一句。")
    assert b"".join(chunk.data for chunk in chunks) == payload
    assert [len(chunk.data) for chunk in chunks] == [4800, 2400]
    assert [chunk.is_final for chunk in chunks] == [False, True]
    assert [chunk.seq for chunk in chunks] == [0, 1]
    assert seen[0]["response_format"] == "pcm"
    assert seen[0]["voice"] == "alloy"
    assert seen[0]["input"] == "第一句。"


async def test_each_sentence_is_one_request_and_model_passthrough() -> None:
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, content=b"\x00\x00", request=request)

    engine = OpenAITtsEngine(
        base_url="https://api.example/v1",
        api_key="sk-test",
        model="gpt-4o-mini-tts",
        transport=httpx.MockTransport(handler),
    )
    chunks = await _collect(engine, "你好。今天怎么样？")
    assert len(bodies) == 2
    assert all(body["model"] == "gpt-4o-mini-tts" for body in bodies)
    assert chunks[-1].is_final


async def test_provider_voice_prefix_and_conflicting_clone_voice() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"\x00\x00", request=request)

    engine = _engine(handler)
    await _collect(engine, "你好。", "openai:nova")
    with pytest.raises(EchoesError) as err:
        await _collect(engine, "你好。", "clone:abc123")
    assert err.value.code is ErrorCode.TTS_ENGINE_ERROR
    assert "克隆" in err.value.message


async def test_missing_key_fails_loudly() -> None:
    engine = _engine(lambda request: httpx.Response(200, request=request), key=None)
    with pytest.raises(EchoesError) as err:
        await _collect(engine, "你好。")
    assert err.value.code is ErrorCode.TTS_ENGINE_ERROR
    assert "API key" in err.value.message


async def test_401_is_reported_as_engine_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key", request=request)

    engine = _engine(handler)
    with pytest.raises(EchoesError) as err:
        await _collect(engine, "你好。")
    assert err.value.code is ErrorCode.TTS_ENGINE_ERROR
    assert "401" in err.value.message


async def test_clone_is_not_supported() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request)

    engine = _engine(handler)
    with pytest.raises(CloneError):
        await engine.clone(OneChunkStream())


async def test_pcm_unsupported_falls_back_to_mp3_and_decodes() -> None:
    """2.14：只支持 mp3 的端点 → 请求 mp3 并本地解码成 PCM16。"""
    import io

    import numpy as np
    import soundfile as sf

    buffer = io.BytesIO()
    t = np.arange(int(24_000 * 0.15)) / 24_000
    tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype("float32")
    sf.write(buffer, tone, 24_000, format="MP3")
    mp3 = buffer.getvalue()

    formats: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        formats.append(body["response_format"])
        if body["response_format"] == "pcm":
            return httpx.Response(
                400,
                text="response_format 'pcm' is not supported by this model",
                request=request,
            )
        return httpx.Response(200, content=mp3, request=request)

    chunks = await _collect(_engine(handler), "你好。")
    assert formats == ["pcm", "mp3"]
    assert chunks[-1].is_final
    assert any(chunk.data for chunk in chunks)
    assert len(b"".join(chunk.data for chunk in chunks)) % 2 == 0
