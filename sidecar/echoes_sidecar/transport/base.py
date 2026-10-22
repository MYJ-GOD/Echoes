"""Transport 契约（文档 4.1 冻结）。

「所有 Transport 实现必须通过同一套一致性测试（13.2 第 3 条）」——
远程大脑只需换 Transport（文档 8.1）的证明义务挂在 tests/test_transport_conformance.py。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


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
