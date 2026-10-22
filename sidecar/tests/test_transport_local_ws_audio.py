"""LocalWebSocketTransport 音频面（3.4 WS 二进制帧；阶段 0 第二周-4）。

帧口径（3.4 冻结）：偏移 0 = 1B 方向（0x01 壳→sidecar / 0x02 sidecar→壳）；
偏移 1 = 4B seq LE；偏移 5 = 1B flags（bit0 is_final / bit1 interrupt_hint /
bit2 clone_sample）；偏移 6 起 = PCM16 payload（入 16k mono / 出 24k mono）。
控制面（JSON text 帧）一致性由 test_transport_conformance 背书；本文件锁音频面。
"""

from __future__ import annotations

import pytest

from echoes_sidecar.core.types import AudioChunk, WSFrameFlags
from echoes_sidecar.transport.local_ws import (
    DIR_INPUT,
    DIR_OUTPUT,
    decode_audio_frame,
    encode_audio_frame,
)


@pytest.mark.parametrize(
    "direction,seq,flags,payload",
    [
        (DIR_INPUT, 0, 0, b"\x01\x02"),
        (DIR_OUTPUT, 1, 0, b""),
        (DIR_INPUT, 4096, int(WSFrameFlags.IS_FINAL), b"\x00" * 16),
        (DIR_INPUT, 2, int(WSFrameFlags.CLONE_SAMPLE), b"\x10\x20\x30"),
        (DIR_OUTPUT, 7, int(WSFrameFlags.INTERRUPT_HINT), b"\x01"),
    ],
)
def test_frame_roundtrip(direction: int, seq: int, flags: int, payload: bytes) -> None:
    raw = encode_audio_frame(direction, seq, flags, payload)
    assert len(raw) == 6 + len(payload)
    frame = decode_audio_frame(raw)
    assert frame.direction == direction
    assert frame.seq == seq
    assert frame.flags == flags
    assert frame.payload == payload


def test_decode_rejects_short_frame() -> None:
    with pytest.raises(ValueError):
        decode_audio_frame(b"\x01\x02\x03")  # <6B：报错而非降级（3.4.1 姿态）


def test_seq_is_little_endian_u32() -> None:
    """seq 编码口径锁定：LE u32（壳侧同款实现对拍依据）。"""
    raw = encode_audio_frame(DIR_INPUT, 0x0000ABCD, 0, b"")
    assert raw[1:5] == bytes([0xCD, 0xAB, 0x00, 0x00])
    assert decode_audio_frame(raw).seq == 0x0000ABCD


async def test_server_routes_audio_frames_to_stream(test_server_pair) -> None:
    """壳→sidecar：三个 audio 帧（末帧 is_final）→ audio_stream() 三 chunk 是 final 终止。"""
    t_sidecar, peer_conn = test_server_pair
    stream = t_sidecar.audio_stream()

    for seq in range(3):
        flags = int(WSFrameFlags.IS_FINAL) if seq == 2 else 0
        await peer_conn.send(encode_audio_frame(DIR_INPUT, seq, flags, bytes([seq] * 8)))

    chunks = [chunk async for chunk in stream]
    assert chunks == [
        AudioChunk(data=bytes([0] * 8), seq=0, is_final=False),
        AudioChunk(data=bytes([1] * 8), seq=1, is_final=False),
        AudioChunk(data=bytes([2] * 8), seq=2, is_final=True),
    ]


async def test_server_send_audio_to_peer(test_server_pair) -> None:
    """sidecar→壳：send_audio 组 0x02 帧（24k PCM payload 透传未改写）。"""
    t_sidecar, peer_conn = test_server_pair
    await t_sidecar.send_audio(AudioChunk(data=b"\x11\x22", seq=9, is_final=True))
    raw = await peer_conn.recv()
    frame = decode_audio_frame(raw)
    assert frame.direction == DIR_OUTPUT
    assert frame.seq == 9
    assert frame.flags == int(WSFrameFlags.IS_FINAL)
    assert frame.payload == b"\x11\x22"


async def test_peer_disconnect_ends_audio_stream(test_server_pair) -> None:
    """壳侧断线 → 音频流终结哨兵（消费端不挂死；3.4.1 恢复语义前置条件）。"""
    import asyncio

    t_sidecar, peer_conn = test_server_pair
    await peer_conn.send(encode_audio_frame(DIR_INPUT, 0, 0, b"\x01\x02"))
    await asyncio.sleep(0.2)  # 保障 handler 吃到帧（close 之后到达的尾帧可丢=断线语义）
    await t_sidecar.close()
    stream = t_sidecar.audio_stream()
    try:
        chunks = await asyncio.wait_for(_collect(stream), timeout=2.0)
    except TimeoutError:
        pytest.fail("音频流未在断线后终结")
    assert any(c.data == b"\x01\x02" for c in chunks)


async def _collect(stream) -> list[AudioChunk]:
    return [chunk async for chunk in stream]
