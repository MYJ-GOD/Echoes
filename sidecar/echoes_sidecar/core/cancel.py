"""三跳打断（3.4）的协作式取消原语：取消令牌 + 可被令牌抢先的流式取项。

**为什么不用 `Task.cancel()`**：LLM/TTS 的异步生成器被强杀时，`finally` 里的
`await` 会收到 `CancelledError` 复投，`turn_complete`/`state` 就再也写不出去——
而三跳的一致性收尾正是协议要求（被打断的 turn 必须以
`turn_complete(status=CANCELLED)` 结束，3.4 三跳分摊表末行）。所以取消是
协作式的：令牌置位，编排层在下一个安全检查点停下并正常收尾。

**为什么还要抢跑**：只在下一次取项之后检查令牌，最坏要等引擎吐完当前片
（真实 TTS 单 chunk 可达百毫秒），会撑爆 sidecar ≤150ms 的预算。
`pull()` 让令牌与 `__anext__` 竞速，取消能插队到 pending 取项之前。

本模块只依赖 asyncio：属 core 层，任何层都可 import（15.2）。
"""
from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from enum import StrEnum
from typing import TypeVar

T = TypeVar("T")


class TurnCancelled(Exception):
    """turn 被三跳打断的内部信号（不映射 error 事件，只映射 CANCELLED 收尾）。"""


class StreamOutcome(StrEnum):
    """`pull()` 的三种归属：取到元素 / 流已终结 / 被取消抢先。"""

    ITEM = "item"
    END = "end"
    CANCELLED = "cancelled"


class CancelToken:
    """协作式取消令牌（3.4 三跳）：`cancel()` 幂等，`waiter()` 供竞速复用。"""

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._waiter: asyncio.Task[bool] | None = None

    def cancel(self) -> None:
        """置位（幂等）：可在任意线程/协程内调用，只置标志不打断在途 await。"""
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def waiter(self) -> asyncio.Task[bool]:
        """惰性创建、整轮复用的等待句柄（逐片新建任务会让一次回复多出上千个对象）。

        `close()` 之后若同一令牌又被复用，这里会自动补一个新的句柄。
        """
        if self._waiter is None or self._waiter.cancelled():
            self._waiter = asyncio.ensure_future(self._event.wait())
        return self._waiter

    async def close(self) -> None:
        """turn 收束时释放句柄：未置位的 waiter 会永久 pending，事件循环关闭时报垃圾告警。"""
        waiter, self._waiter = self._waiter, None
        if waiter is not None and not waiter.done():
            waiter.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await waiter


async def pull(stream: AsyncIterator[T], token: CancelToken) -> tuple[StreamOutcome, T | None]:
    """从流里取下一项，但取消令牌可抢先（三跳 ≤150ms 的关键一环）。

    - 令牌已置位 → 立刻 `CANCELLED`，不再向引擎要数据；
    - 两者同时就绪 → 让元素赢，下一轮再判定取消（少丢一片好过丢错片）；
    - 被抢先的 `__anext__` 必须 cancel：异步生成器会在那个 await 点收到
      `CancelledError` 退出，从而释放底层资源（不是"挂在那里等 GC"）。
    """
    if token.cancelled:
        return StreamOutcome.CANCELLED, None
    pending = asyncio.ensure_future(stream.__anext__())
    try:
        await asyncio.wait({pending, token.waiter()}, return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
        pending.cancel()
        raise
    if pending.done():
        try:
            return StreamOutcome.ITEM, pending.result()
        except StopAsyncIteration:
            return StreamOutcome.END, None
    pending.cancel()
    with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
        await pending
    return StreamOutcome.CANCELLED, None


async def aclose(stream: object) -> None:
    """尽力关闭流（`AsyncIterator` 不保证有 `aclose`，异常不外泄到 turn 收尾）。"""
    close = getattr(stream, "aclose", None)
    if close is None:
        return
    with contextlib.suppress(Exception):
        await close()


__all__ = ["CancelToken", "StreamOutcome", "TurnCancelled", "aclose", "pull"]
