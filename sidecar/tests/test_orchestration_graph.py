"""编排层（4.3/10）：三节点的顺序、收尾不变式与上下文预算。

口径：
- 一次 turn 恒有且只有一条 `turn_complete`，状态机恒回 `ready`（异常也不例外）；
- `assistant_text` 是"截至当前全量"（v1.4.1），音频只经 `AudioEgress` 出壳；
- 引擎错误 → FAILED + `error` 事件（3.4.1 报错不降级），不吞成 SUCCESS；
- 非 USER_INPUT 触发源一律拒绝（4.3 冻结面），预算裁剪只丢历史、不丢本轮输入。
"""

from __future__ import annotations

import time

import pytest

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.engines.llm.mock import MockLLMProvider
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.orchestration.graph import (
    MAX_CONTEXT_CHARS,
    TriggerSource,
    TurnDeps,
    TurnGraph,
)
from echoes_sidecar.session.manager import SessionManager, TurnInFlightError
from tests.conftest import (
    RecordingEgress,
    RecordingTransport,
    make_graph,
    make_session,
    ready_machine,
)
from tests.fakes import BoomLLM, BoomTTS, CountingTTS, FixedLLM


def _run(machine: StateMachine | None = None):
    transport = RecordingTransport()
    egress = RecordingEgress()
    session = make_session()
    graph = make_graph(transport, egress=egress, machine=machine)
    return graph, transport, egress, session


async def test_turn_emits_states_text_and_audio() -> None:
    """happy path：generating → speaking → ready，音频逐帧出 egress。"""
    graph, transport, egress, session = _run()

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "你好"}
    )

    assert outcome.status == "SUCCESS"
    assert outcome.turn_seq == 1
    assert transport.states() == ["generating", "speaking", "ready"]
    assert transport.only_turn_complete()["status"] == "SUCCESS"
    assert graph.machine.state is AppState.READY
    assert session.turn_seq == 1
    assert [c.data for c in egress.chunks] == [b"\x00\x00"]


async def test_assistant_text_is_cumulative() -> None:
    """v1.4.1：text 是截至当前的全量，前端可直接替换渲染。"""
    transport = RecordingTransport()
    graph = make_graph(transport, llm=FixedLLM(["今天", "有点", "累。"]))
    session = make_session()

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "在吗"})

    texts = [msg["text"] for msg in transport.of_type("assistant_text")]
    assert texts == ["今天", "今天有点", "今天有点累。"]


async def test_tts_error_marks_failed_and_returns_ready() -> None:
    """TTS 引擎异常 → FAILED + error 事件；进程不崩、状态机回 ready（非致命）。"""
    transport = RecordingTransport()
    graph = make_graph(transport, tts=BoomTTS())
    session = make_session()

    outcome = await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "你好"})

    assert outcome.status == "FAILED"
    assert graph.machine.state is AppState.READY
    assert transport.only_turn_complete()["status"] == "FAILED"
    errors = transport.of_type("error")
    assert [e["code"] for e in errors] == ["TTS_ENGINE_ERROR"]
    assert errors[0]["fatal"] is False


async def test_llm_error_marks_failed_without_speaking() -> None:
    """LLM 不可达 → FAILED，且没有进 speaking（没内容可念）。"""
    transport = RecordingTransport()
    graph = make_graph(transport, llm=BoomLLM())
    session = make_session()

    outcome = await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "你好"})

    assert outcome.status == "FAILED"
    assert transport.states() == ["generating", "ready"]
    assert [e["code"] for e in transport.of_type("error")] == ["LLM_PROVIDER_UNAVAILABLE"]


async def test_non_user_input_trigger_is_rejected() -> None:
    """4.3 冻结面：其余触发源未实现就必须炸，不能悄悄当成 USER_INPUT。"""
    graph, transport, _egress, session = _run()
    with pytest.raises(NotImplementedError):
        await graph.run_turn(session, TriggerSource.TIMER, {"text": "x"})
    assert transport.sent == []


async def test_missing_text_payload_is_rejected_before_state_change() -> None:
    """payload 缺 text = 协议违约：在动状态机之前就报错（不留半截 generating）。"""
    graph, transport, _egress, session = _run()
    with pytest.raises(EchoesError) as excinfo:
        await graph.run_turn(session, TriggerSource.USER_INPUT, {})
    assert "text" in str(excinfo.value)
    assert transport.sent == []
    assert graph.machine.state is AppState.READY


async def test_budget_keeps_user_input_and_drops_history() -> None:
    """5.2：超预算先丢历史，**永不裁本轮输入**。"""
    graph, transport, _egress, session = _run()
    user_text = "这" * (MAX_CONTEXT_CHARS // 2)

    messages = await graph._compose_messages(session, user_text)
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": user_text}

    # 塞超量历史：只该丢历史，末条输入必须原样保留
    messages = [
        {"role": "system", "content": "s" * 100},
        {"role": "user", "content": "旧" * (MAX_CONTEXT_CHARS // 2)},
        {"role": "assistant", "content": "旧" * (MAX_CONTEXT_CHARS // 2)},
        {"role": "user", "content": user_text},
    ]
    graph._fit_budget(messages)
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": user_text}
    assert sum(len(m["content"]) for m in messages) <= MAX_CONTEXT_CHARS


async def test_graph_uses_session_voice_when_bound() -> None:
    """2.5：会话绑定过音色就用它（编排层解析，引擎不做状态判断）。"""
    transport = RecordingTransport()
    tts = CountingTTS()
    graph = make_graph(transport, tts=tts)
    session = make_session()
    session.voice_id = "voice:clone-abc"

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "你好"})

    assert tts.texts and tts.texts[0][1] == "voice:clone-abc"


async def test_unbound_session_falls_back_to_builtin_voice() -> None:
    transport = RecordingTransport()
    tts = CountingTTS()
    graph = make_graph(transport, tts=tts)
    session = make_session()
    assert session.voice_id is None

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "你好"})

    assert tts.texts[0][1] == "builtin:default"


async def test_serialize_turn_guard_passes_normal_turn() -> None:
    """4.6 串行化：正常单 in-flight 时守卫放行（它是断言，不是限流器）。"""
    manager = SessionManager()
    session = make_session()
    manager.create(session)
    graph = TurnGraph(
        TurnDeps(
            transport=RecordingTransport(),
            llm=MockLLMProvider(),
            tts=MockTTSEngine(),
            t0=time.perf_counter(),
        ),
        ready_machine(),
        manager=manager,
    )

    await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "你好"})
    assert manager.in_flight == frozenset()


def test_serialize_turn_rejects_concurrent_entry() -> None:
    """4.6：同一 session 并发进入回合 → 抛错（不变式被绕开时必须响）。"""
    manager = SessionManager()
    session = make_session()
    manager.create(session)

    with manager.serialize_turn(session.session_id):
        assert manager.in_flight == frozenset({"default"})
        with pytest.raises(TurnInFlightError), manager.serialize_turn(session.session_id):
            pass
    assert manager.in_flight == frozenset()


async def test_failed_turn_still_persists_and_releases_guard() -> None:
    """收尾不变式：失败 turn 也要落库并释放 4.6 守卫（否则后续 turn 全被拒）。"""
    manager = SessionManager()
    session = make_session()
    manager.create(session)
    graph = TurnGraph(
        TurnDeps(
            transport=RecordingTransport(),
            llm=BoomLLM(),
            tts=MockTTSEngine(),
            t0=time.perf_counter(),
        ),
        ready_machine(),
        manager=manager,
    )

    outcome = await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "你好"})
    assert outcome.status == "FAILED"
    assert manager.in_flight == frozenset()
    assert session.turn_seq == 1


def test_error_code_matches_ipc_contract() -> None:
    """错误码是 3.4.1 冻结表：编排层引用的必须是 IPC 层同一份枚举。"""
    assert ErrorCode.TTS_ENGINE_ERROR.value == "TTS_ENGINE_ERROR"
