"""13.2-3：Transport 一致性套件。

参数化在同一套用例上跑全部实现；阶段 0 第二周加入 LocalWebSocketTransport 时
只需在 FACTORIES 再登记一项（13.2-3：「远程只需换 Transport」由本套件背书）。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest

from echoes_sidecar.transport.base import Transport
from tests.conftest import assert_transport_suite, make_local_ws_pair, make_stdio_pair

TransportFactory = Callable[[], Awaitable[tuple[Transport, Transport]]]


async def _stdio_pair() -> tuple[Transport, Transport]:
    return make_stdio_pair()


async def _local_ws_pair() -> tuple[Transport, Transport]:
    return await make_local_ws_pair()


FACTORIES: dict[str, TransportFactory] = {
    # 13.2-3：Stdio 与 LocalWS 必须过同一套用例；WS 实现随阶段 0 第二周接入（§12 步骤 4）
    "stdio": _stdio_pair,
    "local_ws": _local_ws_pair,
}


@pytest.mark.parametrize("pair_factory", FACTORIES.values(), ids=FACTORIES.keys())
async def test_transport_conformance(pair_factory: TransportFactory) -> None:
    t_sidecar, t_peer = await pair_factory()
    await assert_transport_suite(t_sidecar, t_peer)
