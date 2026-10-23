"""SessionManager（文档 4.6）：创建/获取/销毁 Session、串行化同一 Session 内 turn、
响应 3.4 clone_start 的会话级副作用。

阶段 0 只维护一个 Session，但代码路径按「按 session_id 查找」写（4.6）；
sidecar 重启后的重建语义见 14.1。

**关于"注入 Transport 与 AudioStream"（4.6 原文）**：15.2 的分层契约把 session 与
transport 定为同层兄弟（互不可 import），所以"注入"发生在组合根——Manager 交出
Session，编排层用组合根装配好的 Transport 跑 turn。这不是偏离，而是把 4.6 的意图
落到 15.2 的分层上（否则 session 必须 import transport，契约当场红）。
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from echoes_sidecar.session.session import Session


class TurnInFlightError(RuntimeError):
    """同一 Session 已有在途 turn（4.6 串行化：并发进入回合即报错）。"""


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._busy: set[str] = set()

    def create(self, session: Session) -> None:
        """登记会话：同 id 重复创建 = bug 而非覆盖（报错而非降级，3.2）。"""
        if session.session_id in self._sessions:
            raise ValueError(f"session 重复创建: {session.session_id}")
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Session | None:
        """按 session_id 查找（4.6 契约路径；远程阶段 2 复用）。"""
        return self._sessions.get(session_id)

    def destroy(self, session_id: str) -> None:
        """销毁会话（4.6）：不存在即忽略（幂等，关机路径会重复调）。"""
        self._sessions.pop(session_id, None)
        self._busy.discard(session_id)

    @contextmanager
    def serialize_turn(self, session_id: str) -> Iterator[None]:
        """串行化同一 Session 内 turn（4.6）：并发进入回合时抛 `TurnInFlightError`。

        为什么不是 `async with`：本守卫不 await（临界区由调用方自己包），用同步
        上下文管理器才能在"起任务前后"任意位置安全进出，也不占事件循环。
        正常路径下 `TurnRunner` 已先取消旧 turn 再起新的（3.5 单在途），所以这里
        永不触发——它是**不变式断言**，被触发就意味着有人绕开了编排层。
        """
        if session_id in self._busy:
            raise TurnInFlightError(f"session {session_id} 已有在途 turn（4.6 串行化）")
        self._busy.add(session_id)
        try:
            yield
        finally:
            self._busy.discard(session_id)

    @property
    def in_flight(self) -> frozenset[str]:
        """当前有在途 turn 的 session 集合（观测面：验收脚本与日志用）。"""
        return frozenset(self._busy)


__all__ = ["SessionManager", "TurnInFlightError"]
