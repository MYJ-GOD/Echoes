"""Transport 契约（文档 4.1 冻结）。

「所有 Transport 实现必须通过同一套一致性测试（13.2 第 3 条）」——
远程大脑只需换 Transport（文档 8.1）的证明义务挂在 tests/test_transport_conformance.py。

义务注记（评审修复轮）：背压（写端阻塞/读端慢时的流控）未在本骨架实现——
随 LocalWebSocketTransport 于阶段 0 第二周接入（§12 步骤 4）；13.2-5 的三维
（schema 双向 / transport 一致性 / 状态机对拍）未齐前不得宣称「契约全绿」。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol

from echoes_sidecar.core.types import AudioChunk


class Transport(ABC):
    """消息 dict（3.4）的收发抽象。实现必须保证单行序列化（stdio）与序列保序。"""

    @abstractmethod
    async def recv(self) -> dict[str, Any] | None:
        """拉取下一条消息（3.4）；流关闭且无后续消息时返回 None。"""

    @abstractmethod
    async def send(self, msg: dict[str, Any]) -> None:
        """发送一条消息 dict。"""

    @abstractmethod
    async def close(self) -> None:
        """关闭底层流；幂等（重复调用安全）。"""


class AudioEgress(Protocol):
    """输出音频的发送面（3.4 WS 0x02 帧）。

    为什么不直接标 `LocalWebSocketTransport`：3.2 要求编排层只依赖契约（ABC/Protocol），
    具体传输实现归组合根装配；远程大脑（8.1）将来换 LanWebSocketTransport 时，
    编排层这一行不需要改。
    """

    async def send_audio(self, chunk: AudioChunk) -> None:
        """送出一帧 TTS 音频（24k mono PCM16）；无壳连接时实现可静默丢弃。"""
        ...
