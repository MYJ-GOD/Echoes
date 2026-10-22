"""ipc/：3.4 消息 pydantic 模型（单一来源，13.2-1）。

例外层：全工程唯一允许依赖 pydantic 的层（15.2 v1.4）。
TS 侧 src/lib/ipc_types.ts 由 datamodel-code-generator 生成本模块（13.2-1，生成物禁止手改）。
"""
from __future__ import annotations

from echoes_sidecar.ipc.schema import (
    AsrFinalMsg,
    AsrPartialMsg,
    CloneCancelMsg,
    CloneProgressMsg,
    CloneStartMsg,
    ControlMsg,
    EngineState,
    ErrorMsg,
    HelloMsg,
    Message,
    StateMsg,
    Timings,
    TurnCompleteMsg,
    UserTextMsg,
    parse_line,
    parse_obj,
)

__all__ = [
    "AsrFinalMsg",
    "AsrPartialMsg",
    "CloneCancelMsg",
    "CloneProgressMsg",
    "CloneStartMsg",
    "ControlMsg",
    "EngineState",
    "ErrorMsg",
    "HelloMsg",
    "Message",
    "StateMsg",
    "Timings",
    "TurnCompleteMsg",
    "UserTextMsg",
    "parse_line",
    "parse_obj",
]
