"""Session 聚合（文档 4.6 冻结）。不持有 Transport / AudioStream，由 Manager 注入。

重启后的重建语义（14.1 v1.4）：依 DB 最近 session 记录（profile_id/persona_id/voice_id）
重建并沿用原 session_id；丢失的仅为未落库 turn 与滚动上下文。

Persona 权威定义归 core/types（4.6 v1.4 修复轮：core 级零依赖类型）；本模块 re-export
以维持「session 层持有聚合」的导入习惯不变。
"""
from __future__ import annotations

from dataclasses import dataclass

from echoes_sidecar.core.types import Persona

__all__ = ["Persona", "Session"]


@dataclass
class Session:
    """会话聚合（4.6）：上下文、记忆、当前音色挂这里，不散落全局（3.2）。

    voice_id=None = 2.5 none 态（未克隆），由编排层解析为 builtin:default；
    字段顺序按非默认优先调整，字段集与 4.6 完全一致。
    """

    session_id: str
    profile_id: str  # 记忆归属（阶段 0 固定 "default"；远程预留见 8.1）
    persona: Persona
    voice_id: str | None = None
    turn_seq: int = 0  # turn 单调序号（3.4；IPC 天然有序，无幂等键——3.2）
    created_at: float = 0.0
