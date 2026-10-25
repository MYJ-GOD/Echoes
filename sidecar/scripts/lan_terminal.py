"""局域网玩具终端模拟器（8.2；验证协议而非硬件）。

用法（cwd=sidecar）：

    python scripts/lan_terminal.py --url "ws://<ip>:<port>/?token=..." --text "你好"
    python scripts/lan_terminal.py --host 192.168.1.5 --port 51234 --token "<token>" \
        --wav sample16k.wav --out reply24k.pcm

文本模式走 `user_text`；音频模式把 16k mono PCM16 WAV 按 0x01 帧上送，并把
0x02 下行音频写入 `--out`（裸 PCM16 24k）。`turn_complete.turn_seq` 用于去重：
重连后把已见序号传给 `--last-turn-seq`，旧收尾不会重复打印。

范围（8.3）：单活动端点，不做多终端并发/公网/加密。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
import wave
from pathlib import Path
from urllib.parse import quote

import websockets.asyncio.client

_DIR_INPUT = 0x01
_DIR_OUTPUT = 0x02
_FLAG_FINAL = 0x01
_CHUNK = 3200  # 100ms @16k mono PCM16


def _url(args: argparse.Namespace) -> str:
    if args.url:
        return str(args.url)
    if not args.token:
        raise SystemExit("未给 --url 时必须提供 --token")
    return f"ws://{args.host}:{args.port}/?token={quote(args.token, safe='')}"


async def _run_text(ws: object, text: str, timeout: float, last_turn: int) -> int:
    await ws.send(json.dumps({"type": "user_text", "session_id": "default", "text": text}))  # type: ignore[attr-defined]
    latest = ""
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)  # type: ignore[attr-defined]
        if isinstance(raw, bytes):
            continue
        msg = json.loads(raw)
        kind = msg.get("type")
        if kind == "hello":
            engines = ", ".join(f"{e['name']}:{e['ready']}" for e in msg["engines"])
            print(f"HELLO {engines}")
        elif kind == "asr_final":
            print(f"ASR {msg['text']}")
        elif kind == "assistant_text":
            latest = str(msg["text"])
        elif kind == "error":
            print(f"ERROR {msg['code']}: {msg['message']}")
            return 1
        elif kind == "turn_complete":
            seq = int(msg["turn_seq"])
            if seq <= last_turn:
                print(f"SKIP stale turn {seq}（去重）")
                continue
            print(f"REPLY {latest}")
            print(f"TURN {seq} {msg['status']} {msg['timings']}")
            return 0 if msg["status"] == "SUCCESS" else 1


async def _run_audio(
    ws: object, wav_path: Path, out_path: Path, timeout: float, last_turn: int
) -> int:
    with wave.open(str(wav_path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000:
            raise SystemExit("WAV 必须是 16k mono PCM16（3.4 输入口径）")
        pcm = wav.readframes(wav.getnframes())

    seq = 0
    for offset in range(0, len(pcm), _CHUNK):
        payload = pcm[offset : offset + _CHUNK]
        await ws.send(bytes([_DIR_INPUT]) + struct.pack("<I", seq) + b"\x00" + payload)  # type: ignore[attr-defined]
        seq += 1
    await ws.send(bytes([_DIR_INPUT]) + struct.pack("<I", seq) + bytes([_FLAG_FINAL]))  # type: ignore[attr-defined]
    print(f"SENT {len(pcm)}B / {seq + 1} frames")

    out = out_path.open("wb")
    try:
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)  # type: ignore[attr-defined]
            if isinstance(raw, bytes) and len(raw) >= 6 and raw[0] == _DIR_OUTPUT:
                out.write(raw[6:])
                continue
            if not isinstance(raw, bytes):
                msg = json.loads(raw)
                kind = msg.get("type")
                if kind == "asr_final":
                    print(f"ASR {msg['text']}")
                elif kind == "error":
                    print(f"ERROR {msg['code']}: {msg['message']}")
                    return 1
                elif kind == "turn_complete":
                    turn = int(msg["turn_seq"])
                    if turn <= last_turn:
                        print(f"SKIP stale turn {turn}")
                        continue
                    print(f"TURN {turn} {msg['status']}")
                    return 0 if msg["status"] == "SUCCESS" else 1
    finally:
        out.close()


async def _main(args: argparse.Namespace) -> int:
    url = _url(args)
    print(f"CONNECT {url.split('?')[0]}（token 已隐藏）")
    async with websockets.asyncio.client.connect(url) as ws:
        if args.wav:
            return await _run_audio(
                ws, Path(args.wav), Path(args.out or "reply.pcm"), args.timeout, args.last_turn_seq
            )
        return await _run_text(ws, args.text, args.timeout, args.last_turn_seq)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Echoes LAN 玩具终端模拟器（8.2）")
    parser.add_argument("--url", help="完整 ws:// URL（含 ?token=）；优先于 host/port/token")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token", default="")
    parser.add_argument("--text", default="你好，终端接入测试。")
    parser.add_argument("--wav", help="16k mono PCM16 WAV；给定时走音频模式")
    parser.add_argument("--out", help="音频模式下行裸 PCM 输出（24k PCM16）")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--last-turn-seq", type=int, default=0, help="重连去重：已见 turn_seq")
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_main(args))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
