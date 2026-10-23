"""三跳打断（3.4）：协作式取消令牌 / 可抢先取项 / turn 槽 / CANCELLED 收尾。

口径：
- 打断是**协作式**的：令牌置位后 turn 在下一个安全检查点停下并正常收尾，
  绝不强杀（否则 `turn_complete`/`state` 写不出去，壳侧永远卡在 generating）；
- 被打断的 turn 必须以 `turn_complete(status=CANCELLED)` 结束，且状态机回 ready；
- 取消后不再向 WS 产出音频（在途 chunk 丢弃），LLM/TTS 流都要被关闭。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.core.cancel import (
    CancelToken,
    StreamOutcome,
    TurnCancelled,
    aclose,
    pull,
)
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.core.types import AudioChunk, Persona
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.llm.mock import MockLLMProvider
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.main import _run_turn
from echoes_sidecar.orchestration.turn import TurnRunner
from echoes_sidecar.session.session import Session


class _RecordingTransport:
    """4.1 Transport 替身：只记录 send 的 JSON 载荷。"""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)


class _RecordingWS:
    """LocalWebSocketTransport 替身：记录 send_audio 的 chunk。"""

    def __init__(self, token: CancelToken | None = None, cancel_after: int = 0) -> None:
        self.chunks: list[AudioChunk] = []
        self._token = token
        self._cancel_after = cancel_after

    async def send_audio(self, chunk: AudioChunk) -> None:
        self.chunks.append(chunk)
        if self._token is not None and self._cancel_after == len(self.chunks):
            self._token.cancel()  # 模拟壳侧三跳：收到第 N 帧后打断


class _EndlessTTS(TTSEngine):
    """永不结束的 TTS（验证取消后立刻断流，不是跑完再看标志）。"""

    def __init__(self) -> None:
        self.produced = 0

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        while True:
            yield AudioChunk(data=b"\x00\x00", seq=self.produced)
            self.produced += 1

    async def clone(self, sample: Any) -> str:  # noqa: ARG002  test-only stub
        raise NotImplementedError


class _SlowLLM(LLMProvider):
    """首片后长时间阻塞的 LLM（验证令牌能插队到 pending 取项之前）。"""

    @property
    def name(self) -> str:
        return "slow"

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
        _ = (messages, stream, max_tokens, temperature)
        yield "第一片"
        await asyncio.sleep(30)
        yield "不该产出"


class _BoomLLM(LLMProvider):
    """恒抛 EchoesError 的 LLM（turn FAILED + error 事件，3.4.1）。"""

    @property
    def name(self) -> str:
        return "boom"

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
        _ = (messages, stream, max_tokens, temperature)
        raise EchoesError(ErrorCode.LLM_PROVIDER_UNAVAILABLE, "boom")
        yield ""  # async generator 语法要求（不可达）


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


def _summarize(sent: list[dict[str, Any]]) -> tuple[list[str], dict[str, Any]]:
    states = [payload["state"] for payload in sent if payload.get("type") == "state"]
    completes = [payload for payload in sent if payload.get("type") == "turn_complete"]
    assert len(completes) == 1, f"turn 必须恒有且只有一条 turn_complete：{completes}"
    return states, completes[0]


# ---------------------------- 令牌与取项原语 ----------------------------


async def test_cancel_token_is_idempotent_and_wakes_waiters() -> None:
    token = CancelToken()
    assert not token.cancelled
    waiter = token.waiter()
    assert not waiter.done()
    token.cancel()
    token.cancel()  # 幂等
    assert token.cancelled
    assert await asyncio.wait_for(waiter, 1.0) is True
    await token.close()


async def test_pull_reads_items_then_reports_end() -> None:
    async def _stream() -> AsyncIterator[int]:
        yield 1
        yield 2

    token = CancelToken()
    stream = _stream()
    assert await pull(stream, token) == (StreamOutcome.ITEM, 1)
    assert await pull(stream, token) == (StreamOutcome.ITEM, 2)
    assert await pull(stream, token) == (StreamOutcome.END, None)
    await token.close()


async def test_pull_returns_cancelled_without_touching_stream() -> None:
    """令牌已置位时不再向引擎要数据（省掉一次可能上百毫秒的引擎调用）。"""

    async def _stream() -> AsyncIterator[int]:
        raise AssertionError("已取消的取项不得触碰流")
        yield 0  # pragma: no cover

    token = CancelToken()
    token.cancel()
    assert await pull(_stream(), token) == (StreamOutcome.CANCELLED, None)
    await token.close()


async def test_pull_preempts_pending_anext() -> None:
    """令牌抢在 pending `__anext__` 之前返回：三跳 ≤150ms 的关键。"""

    async def _stream() -> AsyncIterator[int]:
        await asyncio.sleep(30)
        yield 0

    token = CancelToken()
    loop = asyncio.get_running_loop()
    loop.call_later(0.05, token.cancel)
    started = time.perf_counter()
    outcome, _ = await pull(_stream(), token)
    assert outcome is StreamOutcome.CANCELLED
    assert time.perf_counter() - started < 2.0, "取消应插队到慢引擎之前"
    await token.close()


async def test_aclose_ignores_streams_without_aclose() -> None:
    class _Bare:
        pass

    await aclose(_Bare())  # 不抛
    await aclose(object())


# ------------------------------- turn 槽 -------------------------------


async def test_runner_interrupt_without_turn_returns_false() -> None:
    runner = TurnRunner()
    assert not runner.busy
    assert await runner.interrupt() is False


async def test_runner_start_cancels_previous_turn() -> None:
    """3.5：单会话单在途 turn——新 turn 起来前旧 turn 必须收束。"""
    runner = TurnRunner()
    seen: list[str] = []

    async def _first(token: CancelToken) -> None:
        try:
            await asyncio.wait_for(token.waiter(), 30)  # 协作式：等令牌而非死睡
        finally:
            seen.append("first-done")

    async def _second(token: CancelToken) -> None:
        seen.append("second")

    first = await runner.start(_first)
    assert runner.busy
    await asyncio.sleep(0.01)
    second = await runner.start(_second)
    await runner.wait(second)
    assert first.done(), "旧 turn 必须在新 turn 起来前收束"
    assert seen == ["first-done", "second"]
    assert not runner.busy


async def test_runner_grace_timeout_does_not_block_new_turn() -> None:
    """引擎不配合令牌时（卡在模型里）：等满宽限期就放行，新 turn 不被永久堵死。"""
    runner = TurnRunner(cancel_grace_seconds=0.2)

    async def _stubborn(token: CancelToken) -> None:
        _ = token
        await asyncio.sleep(0.6)  # 全程不看令牌

    async def _next(token: CancelToken) -> None:
        _ = token

    stubborn = await runner.start(_stubborn)
    started = time.perf_counter()
    following = await runner.start(_next)
    elapsed = time.perf_counter() - started
    await runner.wait(following)
    assert 0.15 <= elapsed < 0.6, f"应等满宽限期即放行（实测 {elapsed:.2f}s）"
    await runner.wait(stubborn)


async def test_runner_swallows_factory_exception() -> None:
    """任务壳兜住意外异常：否则任务静默死掉，状态机永远停在 generating。"""
    runner = TurnRunner()

    async def _boom(token: CancelToken) -> None:
        raise RuntimeError("引擎炸了")

    task = await runner.start(_boom)
    await runner.wait(task)
    assert task.done()
    assert not runner.busy


async def test_runner_interrupt_stops_endless_turn() -> None:
    runner = TurnRunner()
    stopped: list[bool] = []

    async def _endless(token: CancelToken) -> None:
        stream = _EndlessTTS().synthesize("x", "v")
        while True:
            outcome, _chunk = await pull(stream, token)
            if outcome is not StreamOutcome.ITEM:
                stopped.append(token.cancelled)
                return

    task = await runner.start(_endless)
    await asyncio.sleep(0.02)
    assert await runner.interrupt() is True
    await runner.wait(task)
    assert stopped == [True]


# --------------------------- turn 的 CANCELLED ---------------------------


async def test_turn_cancelled_mid_tts_emits_cancelled_and_stops_audio() -> None:
    """三跳：取消后立刻断流，只发已产出的那一帧，收尾 CANCELLED + 回 ready。"""
    transport = _RecordingTransport()
    machine = _ready_machine()
    session = _session()
    token = CancelToken()
    ws = _RecordingWS(token, cancel_after=1)
    tts = _EndlessTTS()

    await _run_turn(
        transport,
        machine,
        session,
        MockLLMProvider(),
        tts,
        "你好",
        time.perf_counter(),
        ws,
        token=token,
    )

    states, complete = _summarize(transport.sent)
    assert complete["status"] == "CANCELLED"
    assert states == ["generating", "speaking", "ready"]
    assert machine.state is AppState.READY
    assert session.turn_seq == 1
    assert len(ws.chunks) == 1, "取消后不得再向 WS 产出音频"
    assert tts.produced <= 2, "取消后不应继续向引擎要数据"


async def test_turn_cancel_preempts_slow_llm() -> None:
    """LLM 卡在下一片时被打断：turn 在秒级内收尾，而不是等满 30s。"""
    transport = _RecordingTransport()
    machine = _ready_machine()
    session = _session()
    token = CancelToken()
    loop = asyncio.get_running_loop()
    loop.call_later(0.05, token.cancel)

    started = time.perf_counter()
    await _run_turn(
        transport,
        machine,
        session,
        _SlowLLM(),
        MockTTSEngine(),
        "你好",
        time.perf_counter(),
        None,
        token=token,
    )
    elapsed = time.perf_counter() - started

    states, complete = _summarize(transport.sent)
    assert complete["status"] == "CANCELLED"
    assert states == ["generating", "ready"], "未进入 speaking 即被打断"
    assert elapsed < 5.0, f"取消未插队到 pending 取项之前（耗时 {elapsed:.1f}s）"
    assert complete["timings"]["llm_first_token_ms"] is not None
    assert complete["timings"]["tts_first_audio_ms"] is None
    assert machine.state is AppState.READY


async def test_turn_cancelled_before_start_produces_no_audio() -> None:
    """令牌在 turn 开始前就已置位：不出音频、不发 assistant_text，仍按 CANCELLED 收尾。"""
    transport = _RecordingTransport()
    machine = _ready_machine()
    session = _session()
    token = CancelToken()
    token.cancel()
    ws = _RecordingWS()

    await _run_turn(
        transport,
        machine,
        session,
        MockLLMProvider(),
        MockTTSEngine(),
        "你好",
        time.perf_counter(),
        ws,
        token=token,
    )

    _states, complete = _summarize(transport.sent)
    assert complete["status"] == "CANCELLED"
    assert ws.chunks == []
    assert [p for p in transport.sent if p.get("type") == "assistant_text"] == []
    assert machine.state is AppState.READY


async def test_turn_llm_error_marks_failed_and_reports_error() -> None:
    """LLM 不可达 → FAILED + error 事件（非致命），状态机照常回 ready。"""
    transport = _RecordingTransport()
    machine = _ready_machine()
    session = _session()

    await _run_turn(
        transport,
        machine,
        session,
        _BoomLLM(),
        MockTTSEngine(),
        "你好",
        time.perf_counter(),
        None,
    )

    _states, complete = _summarize(transport.sent)
    assert complete["status"] == "FAILED"
    errors = [p for p in transport.sent if p.get("type") == "error"]
    assert [e["code"] for e in errors] == ["LLM_PROVIDER_UNAVAILABLE"]
    assert errors[0]["fatal"] is False
    assert machine.state is AppState.READY


async def test_turn_cancelled_exception_is_not_reported_as_error() -> None:
    """打断不是错误：不得产生 error 事件（壳侧只该看到 CANCELLED 收尾）。"""
    transport = _RecordingTransport()
    machine = _ready_machine()
    token = CancelToken()
    token.cancel()

    await _run_turn(
        transport,
        machine,
        _session(),
        MockLLMProvider(),
        MockTTSEngine(),
        "你好",
        time.perf_counter(),
        None,
        token=token,
    )
    assert [p for p in transport.sent if p.get("type") == "error"] == []
    assert isinstance(TurnCancelled(), Exception)
