"""共享测试设施（母文档 13.2）。

内存双工通道：不依赖真实子进程/WS，把 StdioTransport 推入「一致性套件」（13.2-3）。
"""
from __future__ import annotations

import asyncio

from echoes_sidecar.transport.base import Transport
from echoes_sidecar.transport.stdio import StdioTransport


class _MemWriter:
    """最小 StreamWriter 鸭子实现：write 直接注入对端 reader；close 语义 = 对端 EOF。"""

    def __init__(self, peer_reader: asyncio.StreamReader) -> None:
        self._peer = peer_reader
        self._closed = False

    def write(self, data: bytes) -> None:
        if not self._closed:
            self._peer.feed_data(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._peer.feed_eof()

    async def wait_closed(self) -> None:
        return None


def make_stdio_pair() -> tuple[StdioTransport, StdioTransport]:
    """两条互为对端的 StdioTransport：A.send → B.recv；B.send → A.recv。"""
    reader_a = asyncio.StreamReader()
    reader_b = asyncio.StreamReader()
    writer_a = _MemWriter(reader_b)  # A 的发送端 → B 的接收端
    writer_b = _MemWriter(reader_a)  # B 的发送端 → A 的接收端
    return StdioTransport(reader_a, writer_a), StdioTransport(reader_b, writer_b)


async def assert_transport_suite(t_sidecar: Transport, t_peer: Transport) -> None:
    """一致性套件（13.2-3）：序列、EOF→None、close 幂等、双向对等。

    「远程大脑只需换 Transport」（八.1）由该套件背书：新实现入套件，同用例全绿。
    """
    m1 = {"type": "user_text", "session_id": "s1", "text": "在吗？"}
    m2 = {"type": "state", "session_id": None, "state": "ready", "t": 5}

    # 方向一：A→B，保序
    await t_sidecar.send(m1)
    await t_sidecar.send(m2)
    assert await t_peer.recv() == m1
    assert await t_peer.recv() == m2

    # 方向二：B→A（双向对等）
    await t_peer.send(m1)
    assert await t_sidecar.recv() == m1

    # close 幂等
    await t_sidecar.close()
    await t_sidecar.close()

    # 对端收到 EOF → recv None（4.1 契约）
    assert await t_peer.recv() is None

    await t_peer.close()
    assert await t_sidecar.recv() is None
