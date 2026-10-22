"""4.2 AudioChunkStream：AudioChunk 权威定义归 core/（15.2 依赖图），本模块只做契约抽象与再导出。

sidecar 内不存在任何直接打开麦克风的代码（3.2）：输入输出都是帧流抽象。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from echoes_sidecar.core.types import AudioChunk

__all__ = ["AudioChunk", "AudioInputStream", "AudioOutputStream"]


class AudioInputStream(ABC):
    """输入源抽象（4.2）：壳侧采集（经 WS）、文件、网络 WS 都是它的实现。"""

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        """异步产出 AudioChunk。"""


class AudioOutputStream(ABC):
    """输出目标抽象（4.2）：真正的播放设备与缓冲在 Tauri 壳（rodio，ADR-010）。

    stop() 语义：打断——清空内部缓冲、立即停止（三跳协议见 3.4）。
    """

    @abstractmethod
    async def write(self, chunk: AudioChunk) -> None:
        """送出一个 chunk。"""

    @abstractmethod
    async def stop(self) -> None:
        """打断：清空内部缓冲，立即停止。"""
