"""LocalWebSocketTransport（文档 4.1）：本机 ws://127.0.0.1:PORT；音频二进制帧走 WS。

空实现占位（接口已冻结）：阶段 0 第二周接线（文档 §12 步骤 4），期间禁止临时伪装实现。
实现后必须加入 tests/test_transport_conformance.py 的 FACTORIES（13.2-3）。
"""
from __future__ import annotations

from echoes_sidecar.transport.base import Transport

__all__ = ["LocalWebSocketTransport"]


class LocalWebSocketTransport(Transport):
    """未实现：抽象类保持抽象（实例化由组合根控制），阶段 0 接线。"""
