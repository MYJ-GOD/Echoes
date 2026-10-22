"""StdioTransport（文档 4.1/3.4）：stdin/stdout 行分隔 JSON，阶段 0 默认主链路。

reader/writer 可注入（13.2-3 一致性套件用）；真实跨进程管道由组合根（main.py）装配。
"""
from __future__ import annotations

import json
from typing import Any, Protocol

from echoes_sidecar.transport.base import Transport


class _AsyncReader(Protocol):
    """readline() 语义的最小协议（StreamReader 结构满足）。"""

    async def readline(self) -> bytes: ...


class _AsyncWriter(Protocol):
    """write/drain/close/wait_closed 语义的最小协议（StreamWriter 结构满足）。"""

    def write(self, data: bytes) -> None: ...

    async def drain(self) -> None: ...

    def close(self) -> None: ...

    async def wait_closed(self) -> None: ...


class StdioTransport(Transport):
    """行分隔 JSON 收发：接收端按行反序列化，EOF 反回 None；close 幂等。"""

    def __init__(self, reader: _AsyncReader, writer: _AsyncWriter) -> None:
        self._reader = reader
        self._writer = writer
        self._closed = False

    async def recv(self) -> dict[str, Any] | None:
        line = await self._reader.readline()
        if not line:  # EOF：流关闭且无后续消息（4.1）
            return None
        decoded: object = json.loads(line.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("stdio 行必须是 JSON 对象（3.4）")
        return decoded

    async def send(self, msg: dict[str, Any]) -> None:
        if self._closed:
            raise RuntimeError("transport 已关闭")
        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        self._writer.write(data)
        await self._writer.drain()

    async def close(self) -> None:
        """幂等关闭：第二次调用无事发生（13.2-3 套件断言点）。"""
        if not self._closed:
            self._closed = True
            self._writer.close()
            await self._writer.wait_closed()
