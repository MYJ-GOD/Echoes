"""共享测试设施（母文档 13.2）。

内存双工通道：不依赖真实子进程/WS，把 StdioTransport 推入「一致性套件」（13.2-3）。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import pytest

from echoes_sidecar.transport.base import Transport
from echoes_sidecar.transport.local_ws import LocalWebSocketTransport
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


class _WsPeerTransport(Transport):
    """LocalWS 一致性套件的客户端 peer：真实 ws client 的 Transport 鸭子实现。"""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def recv(self) -> dict[str, Any] | None:
        try:
            raw = await self._conn.recv()
        except Exception:  # ConnectionClosed → EOF 语义（4.1）
            return None
        return json.loads(raw)

    async def send(self, msg: dict[str, Any]) -> None:
        await self._conn.send(json.dumps(msg, ensure_ascii=False))

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self._conn.close()


async def make_local_ws_pair() -> tuple[LocalWebSocketTransport, Transport]:
    """LocalWS pair：sidecar 侧真实 server + 客户端 peer（127.0.0.1 动态端口）。"""
    import websockets.asyncio.client

    t_sidecar = LocalWebSocketTransport()
    port = await t_sidecar.start()
    conn = await websockets.asyncio.client.connect(f"ws://127.0.0.1:{port}")
    return t_sidecar, _WsPeerTransport(conn)


@pytest.fixture
async def test_server_pair() -> tuple[LocalWebSocketTransport, Any]:
    """音频面测试用：server + 原始 client 帧连接（不受 Transport 映射限制）。"""
    import websockets.asyncio.client

    t_sidecar = LocalWebSocketTransport()
    port = await t_sidecar.start()
    conn = await websockets.asyncio.client.connect(f"ws://127.0.0.1:{port}")
    try:
        yield t_sidecar, conn
    finally:
        with contextlib.suppress(Exception):
            await conn.close()
        await t_sidecar.close()


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
