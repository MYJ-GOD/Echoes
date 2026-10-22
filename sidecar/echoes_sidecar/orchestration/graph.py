"""最简编排节点与冻结签名（文档 4.3 / 10）。

run_turn 签名冻结（4.3）：阶段 0 只调度 USER_INPUT；其余枚举触发路径返回
NotImplementedError——防止未来加主动开口（ADR-007）时改签名。
LangGraph 只留三节点；上下文预算/裁剪全在本层（5.2），provider 不感知。
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from echoes_sidecar.session.session import Session


class TriggerSource(Enum):
    """turn 触发源（4.3 冻结枚举）：远程大脑预留（8.1）。"""

    USER_INPUT = "user_input"
    TIMER = "timer"  # 阶段 0 不实现（4.3 原文）
    IDLE_DETECTED = "idle_detected"  # 阶段 0 不实现
    EXTERNAL_EVENT = "external_event"  # 阶段 0 不实现


async def run_turn(session: Session, trigger: TriggerSource, payload: dict[str, Any]) -> None:
    """编排入口（4.3 冻结签名；payload 结构见 3.4 对应消息）。

    骨架空实现：阶段 0 第一周接「文本→LLM→文本」（文档 §12 步骤 3）；
    状态机迁移由 core.state_machine 承担（3.5），非 USER_INPUT 一律拒绝。
    """
    if trigger is not TriggerSource.USER_INPUT:
        raise NotImplementedError(f"{trigger.value} 为非阶段 0 触发源（4.3：防主动开口改签名）")
    _ = (session, payload)
    raise NotImplementedError("阶段 0 第一周接线（文档 §12 步骤 3；graph.py 三节点收敛）")
