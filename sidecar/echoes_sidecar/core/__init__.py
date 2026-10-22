"""core/：零依赖类型层（文档 3.3/15.2）——错误码、状态机、AudioChunk/Persona 等。

依赖方向：core 不 import 任何上层；全工程唯一 pydantic 例外在 ipc/（15.2 v1.4）。
4.2 的推荐姿势 `from echoes_sidecar.core import AudioChunk` 即由此出口承载。
"""
from __future__ import annotations

from echoes_sidecar.core.errors import (
    CloneError,
    EchoesError,
    ErrorCode,
    ErrorDomain,
)
from echoes_sidecar.core.state_machine import (
    LEGAL_TRANSITIONS,
    REQUIRED_ENGINES_FOR_READY,
    AppState,
    IllegalTransitionError,
    StateMachine,
    is_legal,
    required_engines_ready,
)
from echoes_sidecar.core.types import (
    AudioChunk,
    Persona,
    VoiceStatus,
    WSFrameFlags,
)

__all__ = [
    "REQUIRED_ENGINES_FOR_READY",
    "LEGAL_TRANSITIONS",
    "AppState",
    "AudioChunk",
    "CloneError",
    "EchoesError",
    "ErrorDomain",
    "ErrorCode",
    "IllegalTransitionError",
    "Persona",
    "StateMachine",
    "VoiceStatus",
    "WSFrameFlags",
    "is_legal",
    "required_engines_ready",
]
