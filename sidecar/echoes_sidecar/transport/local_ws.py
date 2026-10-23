"""LocalWebSocketTransport（4.1 冻结契约实现；阶段 0 第二周-4）。

口径（3.4 冻结）：
- JSON 控制消息走 text 帧（Transport 契约：send/recv/close，保序，EOF→None）；
  一致性由 tests/test_transport_conformance.py 背书（stdio 同套用例）。
- 音频走 binary 帧：偏移 0 = 1B 方向（0x01 壳→sidecar / 0x02 sidecar→壳）、
  偏移 1 = 4B seq LE、偏移 5 = 1B flags（bit0 is_final / bit1 interrupt_hint /
  bit2 clone_sample）、偏移 6 起 = PCM16 payload。
- 壳→sidecar 方向的帧经 audio_stream() 以 AudioChunk 流暴露（4.2 契约口，
  ASREngine.transcribe 直接消费）；sidecar→壳经 send_audio()。

阶段 0 简化注记：单客户端假设（配对壳）；多连接时新连接替换旧连接（旧连接的
EOF 哨兵被抑制，不误标全局结束）。

背压（3.4 三跳前提的 600/300ms 缓冲上限）在这一层是**结构性满足**而非再设一道队列：
`send_audio` 由编排层的拉取式循环逐帧 await——TTS 与 WS 之间没有中间缓冲，
"超上限"这个状态不存在，写满 TCP 窗口时 await 本身就是节流。壳侧那 600ms 是
硬上限（`src-tauri/src/audio.rs::MAX_BUFFERED_SAMPLES`）。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import struct
import sys
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.types import AudioChunk, WSFrameFlags
from echoes_sidecar.transport.base import Transport

DIR_INPUT = 0x01
DIR_OUTPUT = 0x02
_HEADER_LEN = 6  # 1B 方向 + 4B seq + 1B flags


@dataclass
class AudioFrame:
    """解码后的 WS 二进制帧（3.4 偏移表字面映射）。"""

    direction: int
    seq: int
    flags: int
    payload: bytes


def encode_audio_frame(direction: int, seq: int, flags: int, payload: bytes) -> bytes:
    """组帧（壳侧同款实现对拍依据；seq LE u32）。"""
    return bytes([direction]) + struct.pack("<I", seq) + bytes([flags & 0xFF]) + payload


def decode_audio_frame(raw: bytes) -> AudioFrame:
    """解帧；长度不足 6B 抛 ValueError（报错而非降级，3.4.1 姿态）。"""
    if len(raw) < _HEADER_LEN:
        raise ValueError(f"WS 二进制帧不足 {_HEADER_LEN}B: {len(raw)}B")
    seq = struct.unpack("<I", raw[1:5])[0]
    return AudioFrame(direction=raw[0], seq=seq, flags=raw[5], payload=raw[_HEADER_LEN:])


class _WsAudioInputStream(AudioInputStream):
    """壳→sidecar 音频帧流（is_final chunk 落地即流尾；conn 断开由哨兵终结）。"""

    def __init__(self, queue: asyncio.Queue[AudioChunk | None]) -> None:
        self._q = queue

    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        async def _gen() -> AsyncIterator[AudioChunk]:
            while True:
                item = await self._q.get()
                if item is None:
                    return
                yield item
                if item.is_final:
                    return

        return _gen()


class LocalWebSocketTransport(Transport):
    """本机 WS server（127.0.0.1 动态端口）：JSON text 帧 = 控制面，binary = 音频面。"""

    def __init__(self) -> None:
        self._server: Any | None = None
        self._conn: Any | None = None
        self._inbound: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._audio_in: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        # 克隆样本独立队列：bit2 帧不能进 PTT 流，否则克隆音会被 ASR 当成用户说话
        self._clone_in: asyncio.Queue[AudioChunk | None] = asyncio.Queue()
        self._closing = False
        self._eof = False

    async def start(self) -> int:
        """监听 127.0.0.1（port=0 内核分配），返回实际端口；可重复调用覆盖旧 server。"""
        from websockets.asyncio.server import serve

        self._server = await serve(self._handler, "127.0.0.1", 0)
        socks = getattr(self._server, "sockets", None)
        assert socks is not None, "websockets server 建立后应有监听 socket"
        return int(next(iter(socks)).getsockname()[1])

    async def _handler(self, conn: Any) -> None:
        self._conn = conn
        try:
            async for raw in conn:
                if isinstance(raw, bytes):
                    self._feed_audio(raw)
                    continue
                try:
                    self._inbound.put_nowait(json.loads(raw))
                except ValueError:
                    print("[sidecar] WS 收到坏 JSON 帧，已丢弃", file=sys.stderr)
        except Exception:  # ConnectionClosed 等 —— 连接级终止，全局不崩
            pass
        finally:
            if self._conn is conn:  # 仅当仍是活跃连接才标 EOF（新连接已接替时不误标）
                self._conn = None
                self._mark_eof()

    def _mark_eof(self) -> None:
        self._eof = True
        self._inbound.put_nowait(None)
        self._audio_in.put_nowait(None)
        self._clone_in.put_nowait(None)

    def _feed_audio(self, raw: bytes) -> None:
        try:
            frame = decode_audio_frame(raw)
        except ValueError as exc:
            print(f"[sidecar] WS 音频帧解码失败，已丢弃: {exc}", file=sys.stderr)
            return
        if frame.direction != DIR_INPUT:
            return
        chunk = AudioChunk(
            data=frame.payload,
            seq=frame.seq,
            is_final=bool(frame.flags & WSFrameFlags.IS_FINAL),
        )
        # bit2 = 克隆样本分片（3.4）：与 PTT 帧分流，克隆音绝不进 ASR
        if frame.flags & WSFrameFlags.CLONE_SAMPLE:
            self._clone_in.put_nowait(chunk)
            return
        self._audio_in.put_nowait(chunk)

    def audio_stream(self) -> AudioInputStream:
        """壳→sidecar 音频流（每个 turn 由编排层消费一次，PTT 整段形态）。"""
        return _WsAudioInputStream(self._audio_in)

    async def next_utterance(self) -> bytes | None:
        """收集一整段 PTT 输入（至 is_final 帧）的 PCM16；连接中断返回 None。

        与 audio_stream() 同源队列，每次调用消费一段。EOF（壳断开/重连）时
        未收 final 的半段不构成有效输入 → None（由调用方丢弃，防半句进 ASR）。
        """
        parts: list[bytes] = []
        async for chunk in self.audio_stream():
            parts.append(chunk.data)
            if chunk.is_final:
                return b"".join(parts)
        return None

    def clone_stream(self) -> AudioInputStream:
        """壳→sidecar 克隆样本流（bit2 帧；4.5 clone 契约的 AudioInputStream 口）。"""
        return _WsAudioInputStream(self._clone_in)

    async def collect_clone_sample(self) -> bytes | None:
        """收集一段完整克隆样本（至 is_final）的 PCM16；连接中断返回 None。

        与 next_utterance 同构：样本分段上送、收尾由 final 帧界定（3.4 bit2）。
        """
        parts: list[bytes] = []
        async for chunk in self.clone_stream():
            parts.append(chunk.data)
            if chunk.is_final:
                return b"".join(parts)
        return None

    async def send_audio(self, chunk: AudioChunk) -> None:
        """sidecar→壳音频帧（3.4：tts_chunk 24k PCM 口径由上层保证）。"""
        if self._conn is None:
            return  # 阶段 0：无客户端连接时丢弃输出音频（不排队积压）
        flags = int(WSFrameFlags.IS_FINAL) if chunk.is_final else 0
        await self._conn.send(encode_audio_frame(DIR_OUTPUT, chunk.seq, flags, chunk.data))

    async def recv(self) -> dict[str, Any] | None:
        item = await self._inbound.get()
        if item is None and self._eof:
            self._inbound.put_nowait(None)  # EOF 幂等可见：后续 recv 持续 None（4.1 契约）
            return None
        return item

    async def send(self, msg: dict[str, Any]) -> None:
        if self._conn is None:
            return
        await self._conn.send(json.dumps(msg, ensure_ascii=False))

    async def close(self) -> None:
        """幂等关闭：先关活跃连接（走 handler 的 EOF 路径），再 shutdown server。"""
        if self._closing:
            return
        self._closing = True
        if self._conn is not None:
            with contextlib.suppress(Exception):
                await self._conn.close()
        if self._server is not None:
            with contextlib.suppress(Exception):
                self._server.close()
                await self._server.wait_closed()
        if not self._eof:  # 兜底：无连接史（未 start 或从未 connect）时也要满足 EOF 契约
            self._mark_eof()


__all__ = ["LocalWebSocketTransport", "encode_audio_frame", "decode_audio_frame", "AudioFrame"]
