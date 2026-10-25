"""LanWebSocketTransport（4.1/8.2）：token 配对、hello 重放、重连保活。"""

from __future__ import annotations

import asyncio
import json

import pytest
import websockets.asyncio.client
from websockets.exceptions import ConnectionClosed

from echoes_sidecar.transport.lan_ws import LanWebSocketTransport
from tests.conftest import _WsPeerTransport, assert_transport_suite

TOKEN = "test-token-0123456789abcdef"


async def _connect(lan: LanWebSocketTransport, token: str = TOKEN) -> object:
    return await websockets.asyncio.client.connect(
        f"ws://127.0.0.1:{lan.port}/?token={token}"
    )


async def test_lan_transport_passes_conformance_suite() -> None:
    lan = LanWebSocketTransport(TOKEN)
    await lan.start()
    conn = await _connect(lan)
    try:
        await assert_transport_suite(lan, _WsPeerTransport(conn))
    finally:
        await lan.close()


async def test_bad_token_is_rejected() -> None:
    lan = LanWebSocketTransport(TOKEN)
    await lan.start()
    conn = await _connect(lan, token="wrong-token")
    try:
        with pytest.raises(ConnectionClosed):
            await asyncio.wait_for(conn.recv(), timeout=2.0)
    finally:
        await conn.close()
        await lan.close()


async def test_hello_is_replayed_for_late_terminal() -> None:
    lan = LanWebSocketTransport(TOKEN)
    await lan.start()
    try:
        await lan.send(
            {
                "type": "hello",
                "sidecar_version": "0.1.0",
                "protocol_version": "1.0",
                "t": 1,
                "engines": [{"name": "llm", "ready": True}],
            }
        )
        conn = await _connect(lan)
        try:
            raw = await asyncio.wait_for(conn.recv(), timeout=2.0)
            assert json.loads(raw)["type"] == "hello"
        finally:
            await conn.close()
    finally:
        await lan.close()


async def test_reconnect_keeps_server_alive() -> None:
    lan = LanWebSocketTransport(TOKEN)
    await lan.start()
    first = await _connect(lan)
    await first.close()
    await asyncio.sleep(0.1)

    second = await _connect(lan)
    try:
        await lan.send({"type": "state", "state": "ready", "session_id": "default", "t": 2})
        raw = await asyncio.wait_for(second.recv(), timeout=2.0)
        assert json.loads(raw)["type"] == "state"
    finally:
        await second.close()
        await lan.close()
