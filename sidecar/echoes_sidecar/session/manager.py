"""SessionManager（文档 4.6）：创建/获取/销毁 Session、注入 Transport 与 AudioStream、
串行化同一 Session 内 turn、响应 3.4 clone_start 并产出 clone_progress（无进度即假死）。

阶段 0 只维护一个 Session，但代码路径按「按 session_id 查找」写（4.6）；
sidecar 重启后的重建语义见 14.1。
"""
from __future__ import annotations

from echoes_sidecar.session.session import Session


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, session: Session) -> None:
        """登记会话：同 id 重复创建 = bug 而非覆盖（报错而非降级，3.2）。"""
        if session.session_id in self._sessions:
            raise ValueError(f"session 重复创建: {session.session_id}")
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Session | None:
        """按 session_id 查找（4.6 契约路径；远程阶段 2 复用）。"""
        return self._sessions.get(session_id)

    def serialize_turn(self, session_id: str) -> None:
        """串行化同一 Session 内 turn（4.6）：并发进入回合时抛错。

        空实现：阶段 0 第一周随 run_turn 接线（§12 步骤 3）。
        """
        raise NotImplementedError("阶段 0 第一周接线（文档 §12 步骤 3；4.6 串行化职责）")
