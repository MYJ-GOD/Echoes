"""权威错误码总表（文档 3.4.1 冻结契约）：只追加、不重命名、不复用。

3.4.1 与 13.2 以本文件为唯一来源；CloneError 语义见 4.5（调用方必须向 UI 报错并置
音色 failed，禁止回退——2.5）。
"""
from __future__ import annotations

from enum import StrEnum


class ErrorDomain(StrEnum):
    """错误域（文档 3.4.1「域」列）。"""

    CLONE = "clone"
    ENGINE = "engine"
    VOICE = "voice"
    CAPTURE = "capture"
    LLM = "llm"
    ASR = "asr"
    TTS = "tts"
    STORAGE = "storage"
    IPC = "ipc"
    MISC = "misc"


class ErrorCode(StrEnum):
    """错误码（3.4：code 采用 DOMAIN_REASON 命名，前端按 code 渲染，不解析 message）。"""

    SAMPLE_TOO_SHORT = "SAMPLE_TOO_SHORT"
    SAMPLE_TOO_NOISY = "SAMPLE_TOO_NOISY"
    CLONE_QUALITY_LOW = "CLONE_QUALITY_LOW"
    CLONE_ENGINE_FAILED = "CLONE_ENGINE_FAILED"
    CLONE_CANCELLED = "CLONE_CANCELLED"
    MODEL_NOT_LOADED = "MODEL_NOT_LOADED"
    VOICE_NOT_AVAILABLE = "VOICE_NOT_AVAILABLE"
    MIC_NOT_AVAILABLE = "MIC_NOT_AVAILABLE"
    LLM_PROVIDER_UNAVAILABLE = "LLM_PROVIDER_UNAVAILABLE"
    LLM_KEY_MISSING = "LLM_KEY_MISSING"
    ASR_ENGINE_ERROR = "ASR_ENGINE_ERROR"
    TTS_ENGINE_ERROR = "TTS_ENGINE_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"
    HISTORY_WRITE_FAILED = "HISTORY_WRITE_FAILED"
    PROTOCOL_MISMATCH = "PROTOCOL_MISMATCH"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class EchoesError(Exception):
    """统一错误载体：fatal=True 时进入 3.5 的 error 吸收态（14.1 处置）。"""

    def __init__(self, code: ErrorCode, message: str, *, fatal: bool = False) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message
        self.fatal = fatal


class CloneError(EchoesError):
    """克隆失败（4.5 契约）：含 CLONE_CANCELLED（3.4 clone_cancel 触发）。"""
