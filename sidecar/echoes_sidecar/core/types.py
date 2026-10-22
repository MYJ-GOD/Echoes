"""零依赖数据类型（3.3 core/）：AudioChunk 的权威定义（4.2/15.2），audio/ 只做再导出。

Persona 也归 core（4.6 v1.4：与 Session 聚合解耦的零依赖类型，core 级测试可锁）。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


@dataclass
class AudioChunk:
    """音频帧（4.2）：PCM16；输入 16kHz mono / 输出 24kHz mono（WS 帧格式见 3.4）。"""

    data: bytes
    seq: int
    is_final: bool = False


@dataclass
class Persona:
    """人设卡（4.6；与 5.1 persona 表字段一一映射；core 级零依赖类型）。"""

    id: str
    name: str
    system_prompt: str
    created_at: float
    updated_at: float


class VoiceStatus(StrEnum):
    """音色三态（2.5/5.1）：录音中是 UI 态，不落库。"""

    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"


class WSFrameFlags(IntEnum):
    """3.4 WS 二进制帧 flags（偏移 5 的 1B）：三位语义独立、可叠加。"""

    IS_FINAL = 0x01  # bit0：前部输入结束（视作最后一块）
    INTERRUPT_HINT = 0x02  # bit1：播放打断（输出三跳语义）
    CLONE_SAMPLE = 0x04  # bit2：克隆样本分片
