"""分级就绪（3.4 v1.4 / 验收 1）：warmup 完成 → `hello` 重发 + 必需引擎齐了才 ready。

验收 1 的「秒数」要真机才有，但**载体**可以在这里锁死：`hello` 是分级就绪的唯一
信号，重发时机错了，壳侧「引擎就绪中」就会永远停着（或提前放开语音按钮都算坏）。
"""

from __future__ import annotations

import time
from typing import Any

from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.ipc import EngineState
from echoes_sidecar.main import _gate_engine_ready
from echoes_sidecar.transport.base import Transport


class _Transport(Transport):
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def recv(self) -> dict[str, Any] | None:
        return None

    async def send(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)

    async def close(self) -> None:
        return None


class _Engine:
    """最小 `_Warmable`：warmup 成功或抛错。"""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.warmed = False

    async def warmup(self) -> None:
        if self.fail:
            raise RuntimeError("权重缺失")
        self.warmed = True


def _states(*ready: tuple[str, bool]) -> list[EngineState]:
    return [EngineState(name=name, ready=ok) for name, ok in ready]


async def test_gate_resends_hello_and_flips_ready() -> None:
    """TTS 就绪（非必需引擎）：重发 hello，但状态机不动（仍 ready 之外不参与 gate）。"""
    transport = _Transport()
    machine = StateMachine()
    machine.transition(AppState.READY)
    states = _states(("asr", True), ("tts", False), ("llm", True))

    await _gate_engine_ready(transport, machine, "tts", _Engine(), states, time.perf_counter())

    assert [s.ready for s in states] == [True, True, True]
    hello = [m for m in transport.sent if m["type"] == "hello"]
    assert len(hello) == 1
    assert {e["name"]: e["ready"] for e in hello[0]["engines"]} == {
        "asr": True,
        "tts": True,
        "llm": True,
    }
    # 3.4：hello 之后紧跟一份 state（壳以最后一份为准）
    assert [m["type"] for m in transport.sent] == ["hello", "state"]
    assert transport.sent[1]["state"] == "ready"


async def test_gate_blocks_booting_until_required_engines_ready() -> None:
    """只剩 TTS 未就绪时，ASR 就绪不得让状态机进 ready（3.5 必需引擎集合）。"""
    transport = _Transport()
    machine = StateMachine()  # booting
    states = _states(("asr", False), ("tts", True), ("llm", False))

    await _gate_engine_ready(transport, machine, "asr", _Engine(), states, time.perf_counter())

    assert machine.state is AppState.BOOTING
    assert transport.sent[-1]["state"] == "booting"


async def test_gate_enters_ready_when_last_required_engine_arrives() -> None:
    transport = _Transport()
    machine = StateMachine()
    states = _states(("asr", True), ("tts", True), ("llm", False))

    await _gate_engine_ready(transport, machine, "llm", _Engine(), states, time.perf_counter())

    assert machine.state is AppState.READY
    assert [m["type"] for m in transport.sent] == ["hello", "state"]
    assert transport.sent[-1]["state"] == "ready"


async def test_warmup_failure_keeps_booting_and_does_not_lie(
    capsys: Any,
) -> None:
    """warmup 失败：不置 ready、不发 hello（3.4.1 报错不降级，不能假装好了）。"""
    transport = _Transport()
    machine = StateMachine()
    states = _states(("asr", False), ("tts", True), ("llm", True))

    await _gate_engine_ready(
        transport, machine, "asr", _Engine(fail=True), states, time.perf_counter()
    )

    assert states[0].ready is False
    assert machine.state is AppState.BOOTING
    assert transport.sent == []  # 没有「就绪变化」可报
    assert "warmup 失败" in capsys.readouterr().err
