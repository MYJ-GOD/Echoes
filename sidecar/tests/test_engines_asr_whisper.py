"""WhisperASREngine：4.5 契约实现测试（阶段 0 第二周-4）。

口径（PTT 整段形态，阶段 0 简化）：
- 消费 AudioInputStream 到流尾（壳侧 PTT 松开 = 流结束），拼接 PCM16 →
  faster-whisper 整段转写（asyncio.to_thread，3.2 事件循环内禁长阻塞）→
  逐段产出 {"text", "is_final": True, "start_ms", "end_ms"}。
- 空流（无任何 chunk 数据）→ 无产出帧（编排层不应收到空转写事件）。
- 模型加载 lazy（warmup() 由组合根调用；单测桩替换 _transcribe_sync 不触真模型）。
- 真模型 smoke 标记 heavy：pytest -m heavy（权重运行时下载 ~240MB，手动跑）。
"""

from __future__ import annotations

import math
import struct
from collections.abc import AsyncIterator

import pytest

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.asr.whisper import WhisperASREngine


class FakeAudioStream(AudioInputStream):
    """测试用音频流容器：list[AudioChunk] → 异步产出。"""

    def __init__(self, chunks: list[AudioChunk]) -> None:
        self._chunks = chunks

    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        async def _gen() -> AsyncIterator[AudioChunk]:
            for chunk in self._chunks:
                yield chunk

        return _gen()


def pcm16(ms: int, freq: int = 440) -> bytes:
    """合成 PCM16 LE 单声道正弦波（16kHz），模拟壳侧采集。"""
    n = int(16000 * ms / 1000)
    return b"".join(
        struct.pack("<h", int(20000 * math.sin(2 * math.pi * freq * i / 16000)))
        for i in range(n)
    )


@pytest.fixture
def engine() -> WhisperASREngine:
    """轻构造引擎（不触真模型）；桩替换 _transcribe_sync。"""
    return WhisperASREngine()


async def _collect(engine: WhisperASREngine, stream: AudioInputStream) -> list[dict]:
    return [frame async for frame in engine.transcribe(stream)]


@pytest.mark.asyncio
async def test_transcribe_yields_final_frames(engine: WhisperASREngine) -> None:
    engine._transcribe_sync = lambda pcm: [("你好", 0, 1000), ("辛苦啦", 1000, 2400)]  # type: ignore[method-assign]
    frames = await _collect(engine, FakeAudioStream([AudioChunk(pcm16(600), seq=0)]))
    assert frames == [
        {"text": "你好", "is_final": True, "start_ms": 0, "end_ms": 1000},
        {"text": "辛苦啦", "is_final": True, "start_ms": 1000, "end_ms": 2400},
    ]


@pytest.mark.asyncio
async def test_transcribe_concatenates_stream_chunks(engine: WhisperASREngine) -> None:
    """多 chunk（壳侧分帧推送）→ 整段拼接后一次转写（PTT 整段形态）。"""
    seen: list[bytes] = []

    def fake_sync(pcm: bytes) -> list[tuple[str, int, int]]:
        seen.append(pcm)
        return [("整段", 0, 1500)]

    engine._transcribe_sync = fake_sync  # type: ignore[method-assign]
    frames = await _collect(
        engine,
        FakeAudioStream([AudioChunk(pcm16(200), seq=0), AudioChunk(pcm16(300), seq=1)]),
    )
    assert len(seen[0]) == len(pcm16(200)) + len(pcm16(300))
    assert frames == [{"text": "整段", "is_final": True, "start_ms": 0, "end_ms": 1500}]


@pytest.mark.asyncio
async def test_transcribe_empty_stream_yields_nothing(engine: WhisperASREngine) -> None:
    engine._transcribe_sync = lambda pcm: pytest.fail("空流不应触发转写")  # type: ignore[method-assign, return-value]
    assert await _collect(engine, FakeAudioStream([])) == []


@pytest.mark.asyncio
async def test_transcribe_blank_text_filtered(engine: WhisperASREngine) -> None:
    """faster-whisper 对静音段可能产出空串/纯空白——不产出空文本帧。"""
    engine._transcribe_sync = lambda pcm: [("", 0, 800), ("有内容", 800, 1600)]  # type: ignore[method-assign]
    frames = await _collect(engine, FakeAudioStream([AudioChunk(pcm16(500), seq=0)]))
    assert frames == [{"text": "有内容", "is_final": True, "start_ms": 800, "end_ms": 1600}]


@pytest.mark.asyncio
async def test_transcribe_sync_decodes_int16_le_to_float32(engine: WhisperASREngine) -> None:
    """PCM16 LE 直读：int16 → float32 归一（faster-whisper 期望 [-1..1]）。"""
    import numpy as np

    captured: dict = {}

    class FakeModel:
        def transcribe(self, audio, language):  # noqa: ANN001
            captured["audio"] = audio
            captured["language"] = language

            class Seg:
                text = " 喂 "

                def __init__(self, s: float, e: float) -> None:
                    self.start, self.end = s, e

            return iter([Seg(0.0, 1.5)]), None

    engine._model = FakeModel()  # type: ignore[assignment]
    result = engine._transcribe_sync(pcm16(1000))
    audio = captured["audio"]
    assert isinstance(audio, np.ndarray) and audio.dtype == np.float32
    assert float(np.max(np.abs(audio))) <= 1.0
    assert captured["language"] == "zh"
    assert result == [("喂", 0, 1500)]


@pytest.mark.heavy
def test_real_model_handles_sine_smoke() -> None:
    """真模型冒烟（手动跑：pytest -m heavy）；~0.5s 正弦输入，不出错即可。"""
    import asyncio

    engine = WhisperASREngine()
    asyncio.run(engine.warmup())
    stream = FakeAudioStream([AudioChunk(pcm16(500), seq=0)])
    frames = asyncio.run(_collect(engine, stream))  # type: ignore[arg-type]
    assert all(f["is_final"] for f in frames)
