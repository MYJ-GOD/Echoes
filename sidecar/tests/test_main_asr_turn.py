"""PTT 语音入口（3.4/§12 步骤 4）：WS 整段音频 → ASR → asr_final → turn。

口径：
- `next_utterance` 只在 is_final 帧收束；连接中断（EOF）的半段丢弃 → None；
- `asr_final` 与 `user_text` 等价触发 turn；booting 期/空段/空转写不形成 turn；
- ASR 失败经 error 事件上报（ASR_ENGINE_ERROR，非致命不进 3.5 error 态）。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.core.types import AudioChunk, Persona
from echoes_sidecar.engines.asr.base import ASREngine
from echoes_sidecar.engines.asr.mock import MockASREngine
from echoes_sidecar.engines.llm.mock import MockLLMProvider
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.main import _asr_turn_from_pcm, _transcribe_pcm
from echoes_sidecar.session.session import Session
from echoes_sidecar.transport.local_ws import (
    DIR_INPUT,
    LocalWebSocketTransport,
    encode_audio_frame,
)


class _RecordingTransport:
    """4.1 Transport 替身：记录 send 的 JSON 载荷。"""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


class _RecordingWS:
    """LocalWebSocketTransport 替身：记录 send_audio 的 chunk。"""

    def __init__(self) -> None:
        self.chunks: list[AudioChunk] = []

    async def send_audio(self, chunk: AudioChunk) -> None:
        self.chunks.append(chunk)


class _SegmentedASR(ASREngine):
    """两段 final 产出 + 记录收到的音频帧（验证整段输入口）。"""

    def __init__(self) -> None:
        self.received: list[AudioChunk] = []

    async def transcribe(self, audio: AudioInputStream) -> AsyncIterator[dict[str, Any]]:
        async for chunk in audio:
            self.received.append(chunk)
        yield {"text": "你好", "is_final": True, "start_ms": 0, "end_ms": 10}
        yield {"text": "世界", "is_final": True, "start_ms": 10, "end_ms": 20}


class _BoomASR(ASREngine):
    """恒抛 EchoesError 的 ASR 替身（引擎错误不静默，3.4.1）。"""

    async def transcribe(self, audio: AudioInputStream) -> AsyncIterator[dict[str, Any]]:
        raise EchoesError(ErrorCode.ASR_ENGINE_ERROR, "boom")
        yield {}  # async generator 语法要求（不可达）


def _session() -> Session:
    now = time.time()
    persona = Persona(
        id="default", name="默认人设", system_prompt="s", created_at=now, updated_at=now
    )
    return Session(session_id="default", profile_id="default", persona=persona)


def _ready_machine() -> StateMachine:
    machine = StateMachine()
    machine.transition(AppState.READY)
    return machine


async def test_next_utterance_collects_pcm_until_final() -> None:
    ws = LocalWebSocketTransport()
    ws._feed_audio(encode_audio_frame(DIR_INPUT, 0, 0, b"\x01\x00"))
    ws._feed_audio(encode_audio_frame(DIR_INPUT, 1, 1, b"\x02\x00"))  # is_final
    assert await ws.next_utterance() == b"\x01\x00\x02\x00"


async def test_next_utterance_empty_final_is_empty_bytes() -> None:
    """空 final 帧（PTT 松开无残留数据）是有效收束，不当作 EOF。"""
    ws = LocalWebSocketTransport()
    ws._feed_audio(encode_audio_frame(DIR_INPUT, 0, 1, b""))
    assert await ws.next_utterance() == b""


async def test_next_utterance_eof_discards_partial_segment() -> None:
    """连接中断时未收 final 的半段不构成有效输入（返回 None 由调用方丢弃）。"""
    ws = LocalWebSocketTransport()
    ws._feed_audio(encode_audio_frame(DIR_INPUT, 0, 0, b"\x01\x00"))
    ws._mark_eof()
    assert await ws.next_utterance() is None


async def test_transcribe_pcm_feeds_single_final_chunk_and_joins_segments() -> None:
    asr = _SegmentedASR()
    text = await _transcribe_pcm(asr, b"\x00\x01" * 8)
    assert text == "你好世界"
    assert [chunk.data for chunk in asr.received] == [b"\x00\x01" * 8]
    assert asr.received[0].is_final


async def test_asr_turn_emits_asr_final_then_runs_turn() -> None:
    transport = _RecordingTransport()
    ws = _RecordingWS()
    machine = _ready_machine()
    session = _session()

    formed = await _asr_turn_from_pcm(
        b"\x00\x00" * 16,
        transport,
        machine,
        session,
        MockASREngine(),
        MockLLMProvider(),
        MockTTSEngine(),
        time.perf_counter(),
        ws,
    )

    assert formed
    finals = [msg for msg in transport.sent if msg.get("type") == "asr_final"]
    assert len(finals) == 1
    assert finals[0]["text"] == "（mock）今天有点累，陪我聊聊"
    assert finals[0]["is_final"] is True
    assert transport.sent.index(finals[0]) < next(
        i for i, msg in enumerate(transport.sent) if msg.get("type") == "assistant_text"
    )
    completes = [msg for msg in transport.sent if msg.get("type") == "turn_complete"]
    assert len(completes) == 1
    assert completes[0]["status"] == "SUCCESS"
    assert session.turn_seq == 1
    assert machine.state is AppState.READY
    assert ws.chunks  # TTS chunk 已出 WS


async def test_asr_turn_empty_pcm_is_ignored() -> None:
    transport = _RecordingTransport()
    machine = _ready_machine()
    formed = await _asr_turn_from_pcm(
        b"",
        transport,
        machine,
        _session(),
        MockASREngine(),
        MockLLMProvider(),
        MockTTSEngine(),
        time.perf_counter(),
        None,
    )
    assert not formed
    assert transport.sent == []
    assert machine.state is AppState.READY


async def test_asr_turn_ignored_when_not_ready() -> None:
    """booting（asr 未就绪）期 PTT 音频不触发 turn（3.5 用户动作矩阵）。"""
    transport = _RecordingTransport()
    machine = StateMachine()  # booting
    formed = await _asr_turn_from_pcm(
        b"\x00\x00",
        transport,
        machine,
        _session(),
        MockASREngine(),
        MockLLMProvider(),
        MockTTSEngine(),
        time.perf_counter(),
        None,
    )
    assert not formed
    assert transport.sent == []
    assert machine.state is AppState.BOOTING


async def test_asr_failure_emits_error_without_turn() -> None:
    transport = _RecordingTransport()
    machine = _ready_machine()
    formed = await _asr_turn_from_pcm(
        b"\x00\x00",
        transport,
        machine,
        _session(),
        _BoomASR(),
        MockLLMProvider(),
        MockTTSEngine(),
        time.perf_counter(),
        None,
    )
    assert not formed
    assert [msg["type"] for msg in transport.sent] == ["error"]
    assert transport.sent[0]["code"] == "ASR_ENGINE_ERROR"
    assert transport.sent[0]["fatal"] is False
    assert machine.state is AppState.READY
