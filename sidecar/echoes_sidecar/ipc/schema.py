"""3.4 stdio JSON 消息（v1.4 控制面补全）——冻结契约：改动走文档变更记录（12.2）。

约束（3.4）：未知字段必须忽略（extra="ignore"，只追加兼容规则的 schema 侧执行点）。
方向：事件/状态 = sidecar→壳；控制四类 = 壳→sidecar。
本文件是 TS 类型生成（13.2-1）与 golden 对拍（13.2-2）的单一来源。
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from echoes_sidecar.core.errors import ErrorCode

PROTOCOL_VERSION = "1.0"  # 3.4 握手：大版本不匹配 = PROTOCOL_MISMATCH


class _Msg(BaseModel):
    """消息基类：未知字段必须忽略（3.4 兼容规则）。"""

    model_config = ConfigDict(extra="ignore")


# ------------------------- sidecar→壳：事件/状态 -------------------------


class EngineState(_Msg):
    """hello.engines 条目；就绪变化时重发 hello（3.4 v1.4 分级就绪载体）。

    `provider` / `model` 是 R2a 2.5 的 active_* 回报：设置页据此显示「实际生效」，
    而不是只显示「目标值」（2.12 路径可见性）。
    """

    name: str
    ready: bool
    provider: str | None = None
    model: str | None = None


class HelloMsg(_Msg):
    """握手（3.4）：sidecar 启动后第一行输出；必需引擎集合定义见 3.5。"""

    type: Literal["hello"] = "hello"
    sidecar_version: str
    protocol_version: Literal["1.0"] = "1.0"
    t: int
    engines: list[EngineState]


class AsrPartialMsg(_Msg):
    type: Literal["asr_partial"] = "asr_partial"
    session_id: str
    text: str
    t: int


class AsrFinalMsg(_Msg):
    type: Literal["asr_final"] = "asr_final"
    session_id: str
    text: str
    is_final: bool
    t: int


class AssistantTextMsg(_Msg):
    """assistant 回复文本（v1.4.1 追加，12.2 变更记录）。

    text = 截至当前的全量回复文本：流式期间逐帧递增（UI 直接替换渲染），
    收尾边界由同 turn 的 turn_complete 界定；不携带 turn_seq（归属当前
    在途 turn，3.5 单会话单在途 turn）。
    """

    type: Literal["assistant_text"] = "assistant_text"
    session_id: str
    text: str
    t: int


class Timings(_Msg):
    """turn_complete.timings（3.4 观测字段；13.4 自动测量的唯一数据来源）。

    FAILED/CANCELLED 可能未产出音频/首 token，故两字段可空。
    """

    total_ms: int
    llm_first_token_ms: int | None = None
    tts_first_audio_ms: int | None = None


class TurnCompleteMsg(_Msg):
    type: Literal["turn_complete"] = "turn_complete"
    session_id: str
    turn_seq: int
    status: Literal["SUCCESS", "CANCELLED", "FAILED"]
    timings: Timings


class CloneProgressMsg(_Msg):
    """recording → training → checking 由 SessionManager 产出（4.5；无进度即假死）。"""

    type: Literal["clone_progress"] = "clone_progress"
    session_id: str
    phase: Literal["recording", "training", "checking"]
    pct: int
    t: int


class ErrorMsg(_Msg):
    """错误事件（3.4）：前端按 code 渲染；fatal=True 时状态机进 error 吸收态（3.5）。"""

    type: Literal["error"] = "error"
    session_id: str | None = None  # boot 期/会话外错误无 session（3.4.1 STORAGE/PROTOCOL 等）
    code: ErrorCode
    message: str
    fatal: bool
    t: int


class StateMsg(_Msg):
    """状态变更（3.5）：state 变更才发，不重复发；非法迁移由 StateMachine 拦截。"""

    type: Literal["state"] = "state"
    session_id: str | None = None  # booting/error 期可能无会话
    state: Literal["booting", "ready", "generating", "speaking", "error"]
    t: int


# ------------------------- 壳→sidecar：控制面（v1.4） -------------------------


class ControlMsg(_Msg):
    """interrupt=打断并回采集；cancel_turn=仅丢弃不采集（3.4 控制动词定案）。

    两者收尾一致：turn_complete(status=CANCELLED)，播放缓冲清理由壳负责。
    """

    type: Literal["control"] = "control"
    action: Literal["interrupt", "cancel_turn", "open_session"]
    session_id: str
    turn_seq: int | None = None


class UserTextMsg(_Msg):
    """文本输入触发 turn：与 asr_final 等价（3.4/3.5；12.3 首周「文本→LLM→文本」用）。"""

    type: Literal["user_text"] = "user_text"
    session_id: str
    text: str


class RetryMsg(_Msg):
    """重说 / 编辑上一条（R4 4.4/4.5）：append-only 重跑一轮。

    `text=None` = 重说（沿用上一轮 user_text）；给了 `text` = 编辑上一条。
    sidecar 新建 turn，旧 turn 由编排层写 `superseded_by`（失败不取代）。
    不复用 `user_text`：语义不同——重说不能把原文再追加一条用户气泡。
    """

    type: Literal["retry"] = "retry"
    session_id: str
    text: str | None = None


class CloneStartMsg(_Msg):
    """样本经 WS 帧上送（bit2=clone_sample）完成后发起克隆（3.4/4.6）。

    sample_keys 与资产目录内样本文件名对应（3.2：资产层解析相对路径）。
    """

    type: Literal["clone_start"] = "clone_start"
    session_id: str
    sample_keys: list[str]


class CloneCancelMsg(_Msg):
    """中途取消克隆 → CloneError(CLONE_CANCELLED) → 音色落 failed（3.4/2.5）。"""

    type: Literal["clone_cancel"] = "clone_cancel"
    session_id: str


Message = Annotated[
    HelloMsg
    | AsrPartialMsg
    | AsrFinalMsg
    | AssistantTextMsg
    | TurnCompleteMsg
    | CloneProgressMsg
    | ErrorMsg
    | StateMsg
    | ControlMsg
    | UserTextMsg
    | RetryMsg
    | CloneStartMsg
    | CloneCancelMsg,
    Field(discriminator="type"),
]

_MESSAGE_ADAPTER: TypeAdapter[Message] = TypeAdapter(Message)


def parse_line(line: str) -> Message:
    """单行 JSON → 具体消息模型（13.2 golden 对拍唯一入口）。"""
    return _MESSAGE_ADAPTER.validate_json(line)


def parse_obj(obj: dict[str, object]) -> Message:
    """已反序列化的 dict → 具体消息模型（Transport.recv() 之后用）。"""
    return _MESSAGE_ADAPTER.validate_python(obj)
