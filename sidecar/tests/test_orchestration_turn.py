"""三跳打断（3.4）与其取消原语：`CancelToken` / `pull` / `TurnRunner` / 编排层 CANCELLED 收尾。

口径（三跳分摊表末行）：被打断的 turn 必须以
`turn_complete(status=CANCELLED)` 收束、状态机回 `ready`，且**不发 error 事件**
（打断是用户意图，不是故障）。

本文件分三段：原语（core.cancel）→ 任务槽（TurnRunner）→ 编排层端到端（TurnGraph）。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable

from echoes_sidecar.core.cancel import CancelToken, StreamOutcome, TurnCancelled, aclose, pull
from echoes_sidecar.orchestration.graph import TriggerSource
from echoes_sidecar.orchestration.turn import TurnRunner
from tests.conftest import RecordingEgress, RecordingTransport, make_graph, make_session
from tests.fakes import EndlessTTS, FixedLLM, SlowLLM

# ------------------------------ 原语 ------------------------------


async def test_token_cancel_is_idempotent() -> None:
    token = CancelToken()
    assert not token.cancelled
    token.cancel()
    token.cancel()
    assert token.cancelled


async def test_token_waiter_is_reused_across_pulls() -> None:
    """逐片新建任务会让一次回复多出上千个对象——同一轮必须复用一个句柄。"""
    token = CancelToken()
    assert token.waiter() is token.waiter()
    await token.close()


async def test_token_close_allows_fresh_waiter_afterwards() -> None:
    """`close()` 释放句柄；若同一令牌被复用（不该发生），至少不能拿到死的那个。"""
    token = CancelToken()
    first = token.waiter()
    await token.close()
    assert first.cancelled()
    assert token.waiter() is not first
    await token.close()


async def test_token_close_without_waiter_is_noop() -> None:
    await CancelToken().close()  # 不抛即可（收尾路径必然会调它）


async def test_pull_returns_item_then_end() -> None:
    async def gen() -> AsyncIterator[str]:
        yield "a"
        yield "b"

    token = CancelToken()
    stream = gen()
    assert await pull(stream, token) == (StreamOutcome.ITEM, "a")
    assert await pull(stream, token) == (StreamOutcome.ITEM, "b")
    assert await pull(stream, token) == (StreamOutcome.END, None)
    await token.close()


async def test_pull_does_not_touch_stream_when_already_cancelled() -> None:
    """令牌已置位就不再向引擎要数据（不启动 `__anext__`）。"""
    entered = False

    async def gen() -> AsyncIterator[str]:
        nonlocal entered
        entered = True
        yield "x"

    outcome, item = await pull(gen(), _cancelled_token())
    assert (outcome, item) == (StreamOutcome.CANCELLED, None)
    assert not entered


async def test_pull_cancels_pending_anext_and_releases_stream() -> None:
    """取消必须抢在「引擎吐完当前片」之前：pending 的 `__anext__` 要被 cancel 掉，
    生成器的 `finally` 才会跑（资源释放，而不是挂在那里等 GC）。"""
    released = asyncio.Event()

    async def gen() -> AsyncIterator[str]:
        try:
            await asyncio.sleep(30)  # 真实 TTS 卡在模型里的等价物
            yield "不该产出"
        finally:
            released.set()

    token = CancelToken()
    task = asyncio.create_task(pull(gen(), token))
    await asyncio.sleep(0.01)  # 让 __anext__ 真正挂起
    token.cancel()

    outcome, item = await asyncio.wait_for(task, 1.0)
    assert (outcome, item) == (StreamOutcome.CANCELLED, None)
    assert released.is_set()
    await token.close()


async def test_aclose_tolerates_stream_without_aclose() -> None:
    await aclose(object())


async def test_aclose_swallows_engine_close_error() -> None:
    class _Bad:
        async def aclose(self) -> None:
            raise RuntimeError("close 炸了")

    await aclose(_Bad())  # 收尾路径不允许被关闭异常带偏


async def test_turn_cancelled_is_not_an_echoes_error() -> None:
    """打断不映射 error 事件（3.4）：它是内部信号，不是故障码。"""
    assert not hasattr(TurnCancelled, "code")


# ------------------------------ 任务槽 ------------------------------


async def test_runner_start_cancels_previous_turn() -> None:
    """3.5「generating/speaking + 新输入 = 打断重入」：新 turn 起跑前先收掉旧的。"""
    runner = TurnRunner()
    seen: list[str] = []

    async def first(token: CancelToken) -> None:
        await token.waiter()
        seen.append("first-cancelled")

    async def second(token: CancelToken) -> None:
        seen.append("second-done")

    task1 = await runner.start(first)
    await asyncio.sleep(0)
    task2 = await runner.start(second)
    await runner.wait(task1)
    await runner.wait(task2)

    assert seen == ["first-cancelled", "second-done"]
    assert not runner.busy


async def test_runner_grace_timeout_does_not_block_new_turn() -> None:
    """引擎没在安全检查点停下（不看令牌）时，宽限到点就放新 turn 走，不能挂住用户。"""
    runner = TurnRunner(cancel_grace_seconds=0.05)

    async def stubborn(token: CancelToken) -> None:
        await asyncio.sleep(0.3)  # 故意无视令牌

    async def nxt(token: CancelToken) -> None:
        return None

    task1 = await runner.start(stubborn)
    started = time.perf_counter()
    task2 = await runner.start(nxt)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.25, f"宽限期未生效（等了 {elapsed:.2f}s）"
    await runner.wait(task2)
    await runner.wait(task1)


async def test_runner_guard_swallows_unexpected_exception() -> None:
    """任务壳是最后一道防线：意外异常不能把任务静默搞死（否则状态机停在 generating）。"""
    runner = TurnRunner()

    async def boom(token: CancelToken) -> None:
        raise RuntimeError("谁也没想到")

    task = await runner.start(boom)
    await runner.wait(task)  # 不抛即可
    assert not runner.busy


async def test_runner_interrupt_without_in_flight_is_false() -> None:
    """ready 期连点 PTT 会发来空打断——可容忍的协议噪声，不是错误。"""
    runner = TurnRunner()
    assert await runner.interrupt() is False


async def test_runner_interrupt_reports_true_only_for_live_turn() -> None:
    runner = TurnRunner()

    async def idle(token: CancelToken) -> None:
        await token.waiter()

    task = await runner.start(idle)
    await asyncio.sleep(0)
    assert await runner.interrupt() is True
    await runner.wait(task)
    assert await runner.interrupt() is False  # 已收尾 → 不再算打断


async def test_runner_wait_is_noop_when_idle() -> None:
    await TurnRunner().wait()


# ------------------------------ 编排层端到端 ------------------------------


async def test_cancel_before_start_yields_cancelled_close() -> None:
    """一开始就被打断：不产文本、不进 speaking，仍有一条 CANCELLED 收尾。"""
    transport = RecordingTransport()
    graph = make_graph(transport, llm=FixedLLM(["你好"]))
    session = make_session()
    token = _cancelled_token()

    outcome = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "在吗"}, token=token
    )

    assert outcome.status == "CANCELLED"
    assert transport.of_type("assistant_text") == []
    assert transport.states() == ["generating", "ready"]
    assert transport.only_turn_complete()["status"] == "CANCELLED"
    assert transport.of_type("error") == []


async def test_cancel_during_generation_jumps_pending_pull() -> None:
    """片间等待 30s 也必须被取消抢掉（sidecar ≤150ms 的关键一环）。"""
    transport = RecordingTransport()
    graph = make_graph(transport, llm=SlowLLM(delay=30.0))
    session = make_session()
    token = CancelToken()

    started = time.perf_counter()
    task = asyncio.create_task(
        graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "在吗"}, token=token)
    )
    await _wait_until(lambda: len(transport.of_type("assistant_text")) >= 1)
    token.cancel()

    outcome = await asyncio.wait_for(task, 1.0)
    assert outcome.status == "CANCELLED"
    assert time.perf_counter() - started < 1.0
    assert transport.only_turn_complete()["status"] == "CANCELLED"


async def test_cancel_during_speaking_stops_audio_and_returns_ready() -> None:
    """speaking 期被打断：断流（不再产音）+ 一条 CANCELLED + 回 ready，且不报错。"""
    transport = RecordingTransport()
    egress = RecordingEgress()
    graph = make_graph(
        transport, llm=FixedLLM(["你好"]), tts=EndlessTTS(), egress=egress
    )
    session = make_session()
    token = CancelToken()

    task = asyncio.create_task(
        graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "在吗"}, token=token)
    )
    await _wait_until(lambda: len(egress.chunks) >= 3)
    token.cancel()

    outcome = await asyncio.wait_for(task, 1.0)
    produced = len(egress.chunks)
    await asyncio.sleep(0.05)

    assert outcome.status == "CANCELLED"
    assert len(egress.chunks) == produced, "取消后仍在产音（断流未生效）"
    assert transport.only_turn_complete()["status"] == "CANCELLED"
    assert transport.of_type("error") == []
    assert transport.states()[-1] == "ready"
    assert graph.machine.state.value == "ready"


async def test_cancelled_turn_still_advances_turn_seq() -> None:
    """轮次编号照常递增：被打断也是一轮（否则壳侧 seq 会错位）。"""
    graph = make_graph(RecordingTransport())
    session = make_session()

    first = await graph.run_turn(
        session, TriggerSource.USER_INPUT, {"text": "一"}, token=_cancelled_token()
    )
    second = await graph.run_turn(session, TriggerSource.USER_INPUT, {"text": "二"})

    assert (first.turn_seq, second.turn_seq) == (1, 2)
    assert (first.status, second.status) == ("CANCELLED", "SUCCESS")


# ------------------------------ 小工具 ------------------------------


def _cancelled_token() -> CancelToken:
    token = CancelToken()
    token.cancel()
    return token


async def _wait_until(predicate: Callable[[], bool], *, timeout: float = 1.0) -> None:
    """轮询等待某个可观测状态（turn 跑在后台任务里，没有同步返回点）。"""

    async def _until() -> None:
        while not predicate():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_until(), timeout)
