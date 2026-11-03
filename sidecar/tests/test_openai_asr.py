"""OpenAI 兼容 ASR（R2a 2.1）：WAV 容器、multipart、鉴权与错误口径。"""

from __future__ import annotations

import io
import wave

import httpx
import pytest

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.asr.openai_audio import OpenAIAudioASREngine


class PcmStream(AudioInputStream):
    def __init__(self, pcm: bytes) -> None:
        self._pcm = pcm

    def __aiter__(self):
        async def gen():
            yield AudioChunk(data=self._pcm, seq=0, is_final=True)

        return gen()


def _engine(handler, *, key: str | None = "sk-test") -> OpenAIAudioASREngine:
    return OpenAIAudioASREngine(
        base_url="https://api.example/v1",
        api_key=key,
        transport=httpx.MockTransport(handler),
    )


async def _collect(engine: OpenAIAudioASREngine, pcm: bytes = b"\x00\x00" * 160):
    return [seg async for seg in engine.transcribe(PcmStream(pcm))]


async def test_uploads_wav_container_not_raw_pcm() -> None:
    captured: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={"text": " 你好 "}, request=request)

    engine = _engine(handler)
    segments = await _collect(engine)
    assert segments == [{"text": "你好", "is_final": True, "start_ms": 0, "end_ms": 0}]

    body = captured["body"]
    assert b"RIFF" in body and b"WAVE" in body
    assert b"audio.wav" in body
    assert b"whisper-1" in body
    # 16k mono PCM16 的 WAV 头：采样率 16000、声道 1
    assert b"\x80\x3e\x00\x00" in body  # 16000 little-endian


async def test_empty_audio_produces_no_segment() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("空音频不应发请求")

    engine = _engine(handler)
    assert await _collect(engine, pcm=b"") == []


async def test_missing_key_fails_loudly() -> None:
    engine = _engine(lambda request: httpx.Response(200, request=request), key=None)
    with pytest.raises(EchoesError) as err:
        await _collect(engine)
    assert err.value.code is ErrorCode.ASR_ENGINE_ERROR
    assert "API key" in err.value.message


async def test_401_and_429_are_engine_errors() -> None:
    for status in (401, 429):
        engine = _engine(
            lambda request, status=status: httpx.Response(
                status, text="nope", request=request
            )
        )
        with pytest.raises(EchoesError) as err:
            await _collect(engine)
        assert err.value.code is ErrorCode.ASR_ENGINE_ERROR
        assert str(status) in err.value.message


async def test_wav_header_round_trips() -> None:
    captured: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, json={"text": "ok"}, request=request)

    pcm = b"\x01\x00" * 100
    await _collect(_engine(handler), pcm=pcm)
    start = captured["body"].index(b"RIFF")
    # WAV 头 44 字节后紧跟原始 PCM（multipart 里 file 部分无额外编码）
    header = captured["body"][start : start + 44]
    with wave.open(io.BytesIO(header), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == 16_000
