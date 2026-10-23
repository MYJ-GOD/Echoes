"""turn 音频真链（3.4）：_run_turn 的 TTS chunk 逐帧 send_audio（第二周尾部接线）。

帧格式（1B 方向 / 4B seq LE / 1B flags / PCM16）由 test_transport_local_ws_audio
与 encode/decode 对拍背书；本文件锁编排面：synthesize 产出的每个 chunk 都进 WS
发送端；TTS 引擎错误 → turn_complete(status=FAILED) 收束（3.4.1 报错不降级）。
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.core.types import AudioChunk, Persona
from echoes_sidecar.engines.llm.mock import MockLLMProvider
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.main import _run_turn
from echoes_sidecar.session.session import Session


class _RecordingTransport:
    """4.1 Transport 替身：只记录 send 的 JSON 载荷（turn 面不消费 recv/close）。"""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


class _RecordingWS:
    """LocalWebSocketTransport 替身：记录 send_audio 的 chunk 序。"""

    def __init__(self) -> None:
        self.chunks: list[AudioChunk] = []

    async def send_audio(self, chunk: AudioChunk) -> None:
        self.chunks.append(chunk)


class _BoomTTSEngine(TTSEngine):
    """恒抛 EchoesError 的 TTS 替身（引擎错误不静默，3.4.1）。"""

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        raise EchoesError(ErrorCode.TTS_ENGINE_ERROR, "boom")
        yield AudioChunk(data=b"", seq=0)  # async generator 语法要求（不可达）

    async def clone(self, sample: Any) -> str:  # noqa: ARG002  test-only stub
        raise NotImplementedError


def _session() -> Session:
    now = time.time()
    persona = Persona(
        id="default", name="默认人设", system_prompt="s", created_at=now, updated_at=now
    )
    return Session(session_id="default", profile_id="default", persona=persona)


async def test_turn_pushes_tts_chunks_to_ws() -> None:
    """turn 内 synthesize 的每个 chunk 进 WS 发送端（mock TTS 恒产 1 帧静音）。"""
    transport = _RecordingTransport()
    ws = _RecordingWS()
    machine = StateMachine()
    machine.transition(AppState.READY)
    session = _session()

    await _run_turn(
        transport,
        machine,
        session,
        MockLLMProvider(),
        MockTTSEngine(),
        "你好",
        time.perf_counter(),
        ws,
    )

    assert ws.chunks == [AudioChunk(data=b"\x00\x00", seq=0, is_final=True)]
    assert session.turn_seq == 1
    assert machine.state is AppState.READY

    states = [payload["state"] for payload in transport.sent if "state" in payload]
    assert states == ["generating", "speaking", "ready"]
    completes = [payload for payload in transport.sent if "turn_seq" in payload]
    assert len(completes) == 1
    assert completes[0]["status"] == "SUCCESS"


async def test_turn_tts_error_marks_failed() -> None:
    """TTS 引擎异常 → turn FAILED 收束、状态机回 ready，进程不崩（非致命不进 3.5 error 态）。"""
    transport = _RecordingTransport()
    machine = StateMachine()
    machine.transition(AppState.READY)
    session = _session()

    await _run_turn(
        transport,
        machine,
        session,
        MockLLMProvider(),
        _BoomTTSEngine(),
        "你好",
        time.perf_counter(),
        None,
    )

    completes = [payload for payload in transport.sent if "turn_seq" in payload]
    assert completes[0]["status"] == "FAILED"
    assert machine.state is AppState.READY
    assert session.turn_seq == 1
