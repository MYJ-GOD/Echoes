"""单在途 turn 的任务槽（3.5「单会话单在途 turn」/ 3.4 三跳打断）。

**为什么 turn 必须跑在后台任务里**：`stdio` 主循环与 `control` 消息共用同一条
输入流。turn 一旦在循环内同步跑完，`control(action=interrupt)` 就只能排在这轮
之后——打断根本无从谈起。所以 turn 一律 `create_task`，主循环保持可读。

**为什么取消要"先置令牌再等"**：见 `core.cancel` 模块 docstring（不强杀异步
生成器，保证 `turn_complete(status=CANCELLED)` 一定写得出去）。

`start()` 自带"先打断旧 turn 再开新 turn"：这正是 3.5 用户动作矩阵里
`generating`/`speaking` 收到新输入的语义（重入 `generating`）。
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
from collections.abc import Awaitable, Callable

from echoes_sidecar.core.cancel import CancelToken

TurnFactory = Callable[[CancelToken], Awaitable[None]]

# 取消宽限：置令牌后等在途 turn 自己收尾的上限。超时说明引擎没在安全检查点
# 停下（真实 TTS 卡在模型里），此时宁可让旧 turn 继续跑完也不能挂住新 turn。
DEFAULT_CANCEL_GRACE_SECONDS = 2.0


class TurnRunner:
    """turn 任务槽：串行化 + 协作式打断（3.4 三跳 / 3.5 单在途）。"""

    def __init__(self, *, cancel_grace_seconds: float = DEFAULT_CANCEL_GRACE_SECONDS) -> None:
        self._lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._token: CancelToken | None = None
        self._grace = cancel_grace_seconds

    @property
    def busy(self) -> bool:
        """是否有在途 turn（壳侧 busy 对侧；状态机之外的第二视角，仅用于日志/守卫）。"""
        return self._task is not None and not self._task.done()

    async def interrupt(self) -> bool:
        """打断在途 turn 并等它收尾；返回是否真有 turn 被打断。

        无在途 turn 时返回 False —— 壳侧在 `ready` 期发来的 `control` 属可容忍的
        协议噪声（用户连点两次 PTT 就会发生），记日志即可，不算错误。
        """
        async with self._lock:
            return await self._cancel_locked()

    async def start(self, factory: TurnFactory) -> asyncio.Task[None]:
        """打断旧 turn（若有）→ 起新 turn 任务并返回句柄。

        返回句柄而不是 None：调用方需要 `wait()` 自己起的那个（`user_text` 会把它
        顶掉，若拿"当前任务"就会等错对象）。
        """
        async with self._lock:
            await self._cancel_locked()
            token = CancelToken()
            self._token = token
            task = asyncio.create_task(self._guard(factory, token), name="echoes-turn")
            self._task = task
            return task

    async def wait(self, task: asyncio.Task[None] | None = None) -> None:
        """等在途 turn 收尾（默认当前）；`shield` 保证等待方被取消时不牵连 turn。"""
        target = self._task if task is None else task
        if target is None:
            return
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.shield(target)

    async def _cancel_locked(self) -> bool:
        token, task = self._token, self._task
        if token is None or task is None or task.done():
            return False
        token.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), self._grace)
        except TimeoutError:
            print(
                f"[sidecar] 打断超时（>{self._grace:.1f}s）：引擎未在安全检查点停下，"
                "旧 turn 继续跑完后由收尾逻辑复位状态",
                file=sys.stderr,
            )
        return True

    async def _guard(self, factory: TurnFactory, token: CancelToken) -> None:
        """任务壳：兜住意外异常（否则任务静默死掉，状态机永远停在 generating）。"""
        try:
            await factory(token)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001  turn 任务的最后一道防线
            print(f"[sidecar] turn 任务异常退出: {exc}", file=sys.stderr)
        finally:
            await token.close()


__all__ = ["DEFAULT_CANCEL_GRACE_SECONDS", "TurnFactory", "TurnRunner"]
