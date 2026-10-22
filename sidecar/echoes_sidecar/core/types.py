"""零依赖数据类型（3.3 core/）：AudioChunk 的权威定义（4.2/15.2），audio/ 只做再导出。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass
class AudioChunk:
    """音频帧（4.2）：PCM16；输入 16kHz mono / 输出 24kHz mono（WS 帧格式见 3.4）。"""

    data: bytes
    seq: int
    is_final: bool = False


class VoiceStatus(StrEnum):
    """音色三态（2.5/5.1）：录音中是 UI 态，不落库。"""

    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"
