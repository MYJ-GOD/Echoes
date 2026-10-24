"""共享测试设施（母文档 13.2）。

内存双工通道：不依赖真实子进程/WS，把 StdioTransport 推入「一致性套件」（13.2-3）。
turn 编排的构造样板（`make_graph`）也在这里：编排层测试与 ASR 入口测试共用。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import Any

import pytest

from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.core.types import AudioChunk, Persona
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.llm.mock import MockLLMProvider
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.memory.extractor import MemoryExtractor
from echoes_sidecar.memory.store import MemoryStore
from echoes_sidecar.orchestration.graph import TurnDeps, TurnGraph
from echoes_sidecar.session.session import Session
from echoes_sidecar.session.summary import SessionSummarizer
from echoes_sidecar.transport.base import AudioEgress, Transport
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


class RecordingTransport(Transport):
    """4.1 Transport 替身：只记录 send 的 JSON 载荷（turn 面不消费 recv/close）。"""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def recv(self) -> dict[str, Any] | None:
        return None

    async def send(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)

    async def close(self) -> None:
        return None

    def of_type(self, kind: str) -> list[dict[str, Any]]:
        return [msg for msg in self.sent if msg.get("type") == kind]

    def states(self) -> list[str]:
        return [str(msg["state"]) for msg in self.of_type("state")]

    def only_turn_complete(self) -> dict[str, Any]:
        """turn 的不变式：恒有且只有一条 turn_complete（3.4 三跳收尾要求）。"""
        completes = self.of_type("turn_complete")
        assert len(completes) == 1, f"应恒有且只有一条 turn_complete，实得 {completes}"
        return completes[0]


class RecordingEgress(AudioEgress):
    """AudioEgress 替身：记录下行音频帧。"""

    def __init__(self) -> None:
        self.chunks: list[AudioChunk] = []

    async def send_audio(self, chunk: AudioChunk) -> None:
        self.chunks.append(chunk)


def make_session() -> Session:
    now = time.time()
    persona = Persona(
        id="default", name="默认人设", system_prompt="s", created_at=now, updated_at=now
    )
    return Session(session_id="default", profile_id="default", persona=persona)


def ready_machine() -> StateMachine:
    machine = StateMachine()
    machine.transition(AppState.READY)
    return machine


def make_graph(
    transport: Transport | None = None,
    *,
    llm: LLMProvider | None = None,
    tts: TTSEngine | None = None,
    egress: AudioEgress | None = None,
    machine: StateMachine | None = None,
    t0: float | None = None,
    memory: MemoryStore | None = None,
    extractor: MemoryExtractor | None = None,
    summarizer: SessionSummarizer | None = None,
) -> TurnGraph:
    """turn 编排的标准装配（默认 mock 引擎 + 记录型 transport）。"""
    return TurnGraph(
        TurnDeps(
            transport=transport if transport is not None else RecordingTransport(),
            llm=llm if llm is not None else MockLLMProvider(),
            tts=tts if tts is not None else MockTTSEngine(),
            t0=t0 if t0 is not None else time.perf_counter(),
            egress=egress,
            memory=memory,
            extractor=extractor,
            summarizer=summarizer,
        ),
        machine if machine is not None else ready_machine(),
    )
