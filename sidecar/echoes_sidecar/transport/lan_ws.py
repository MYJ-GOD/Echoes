"""LanWebSocketTransport（4.1/8.2）：局域网 WS + token 配对，单活动端点。

**范围**：同一时间只接受一个终端（多终端并发调度明确不做，8.3）。连接携带
`?token=<配对令牌>`；token 由 sidecar 启动时生成或通过 `--lan-token` 指定。
JSON 控制/事件与音频二进制帧走同一条 WS（3.4 帧格式），因此终端既可以是
文本面也可以是音频端点。

**重连去重**：服务端不做事件重放缓存（单端点 + `turn_seq` 客户端去重，8.2）；
终端按 `turn_complete.turn_seq` 忽略重复/过期收尾。
"""
from __future__ import annotations

import socket

from echoes_sidecar.transport.local_ws import LocalWebSocketTransport


class LanWebSocketTransport(LocalWebSocketTransport):
    """0.0.0.0 监听 + token 鉴权；其余行为与本地 WS 一致。"""

    def __init__(self, token: str, *, host: str = "0.0.0.0") -> None:
        text = token.strip()
        if len(text) < 16:
            raise ValueError("LAN token 至少 16 字符（8.2 配对令牌）")
        super().__init__(host=host, token=text, keep_alive=True)
        self._port = 0

    async def start(self, port: int = 0) -> int:
        self._port = await super().start(port)
        return self._port

    @property
    def port(self) -> int:
        return self._port

    def url(self) -> str:
        """可直接交给终端模拟器的配对 URL（IP + token）。"""
        return f"ws://{_lan_ip()}:{self._port}/?token={self._token}"


def _lan_ip() -> str:
    """取本机对外 IPv4（UDP connect 不实际发包）；失败回 127.0.0.1。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return str(sock.getsockname()[0])
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


__all__ = ["LanWebSocketTransport"]
