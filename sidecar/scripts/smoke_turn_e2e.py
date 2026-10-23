"""端到端 L3 冒烟（本机验收工具，不进 CI）：spawn sidecar → 真合成 → WS 0x02 帧 → turn SUCCESS。

链路口径（R20）：
    spawn `python -m echoes_sidecar.main --tts cosyvoice2 --ws auto`
    → stdout 文件 JSON 面（hello 分级就绪 / assistant_text / turn_complete）
    → 第二发 hello tts:true 后写 user_text（PTT 等价）
    → WS 收 0x02 音频帧（1B 方向 + 4B seq LE + 1B flags(bit0=IS_FINAL) + PCM16）
    → 断言：seq 单调、末帧 IS_FINAL、载荷非静音、turn SUCCESS

为什么 stdout/stderr 落文件而不是 PIPE：stdin=PIPE + 文件输出正是 Tauri 壳的
spawn 形态，也是 R20 Windows loader-lock 死锁的复现形态；PIPE 读会引入宿主
缓冲变量。stderr 是 GBK 编码（Windows），WS 端口按 `ws://127.0.0.1:(\d+)` 提取。

用法（cwd=sidecar，前置：uv sync + 权重 ~/.cache/echoes/models/CosyVoice2-0.5B）：
    python scripts/smoke_turn_e2e.py
    python scripts/smoke_turn_e2e.py --text "换一句" --timeout 420
    python scripts/smoke_turn_e2e.py --tts mock --ws off   # 仅消息面自检

日志落 scripts/_smoke_out/（gitignored）。成功以单独一行 `OK:` 收尾。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from contextlib import suppress
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
_OUT_DIR = _SIDECAR_ROOT / "scripts" / "_smoke_out"
OUT_FILE = _OUT_DIR / "smoke_e2e_stdout.jsonl"
ERR_FILE = _OUT_DIR / "smoke_e2e_stderr.log"
SESSION = "default"
DEFAULT_TEXT = "你好！很高兴见到你，今天想聊点什么？"


def _read_lines(path: Path, encoding: str) -> list[str]:
    try:
        return path.read_text(encoding=encoding, errors="replace").splitlines()
    except OSError:
        return []


def _stdout_msgs() -> list[dict[str, object]]:
    msgs: list[dict[str, object]] = []
    for line in _read_lines(OUT_FILE, "utf-8"):
        if line.startswith("{"):
            with suppress(ValueError):
                msgs.append(json.loads(line))
    return msgs


async def _ws_collector(frames: list[tuple[int, bool, bytes]], wait_s: float = 60.0) -> None:
    import websockets

    port: int | None = None
    t0 = time.perf_counter()
    while port is None and time.perf_counter() - t0 < wait_s:
        for line in _read_lines(ERR_FILE, "gbk")[-8:]:
            m = re.search(r"ws://127\.0\.0\.1:(\d+)", line)
            if m:
                port = int(m.group(1))
                break
        if port is None:
            await asyncio.sleep(0.5)
    if port is None:
        print(f"[smoke] WS 端口未取得（{wait_s:.0f}s 内），跳过音频面")
        return

    print(f"[smoke] WS 连接 ws://127.0.0.1:{port}")
    async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
        async for raw in ws:
            if isinstance(raw, bytes):
                direction = raw[0]
                seq = int.from_bytes(raw[1:5], "little")
                flags = raw[5]
                frames.append((seq, bool(flags & 1), raw[6:]))
                assert direction == 0x02, f"方向非 0x02: {direction}"


async def main() -> None:
    parser = argparse.ArgumentParser(prog="smoke_turn_e2e")
    parser.add_argument("--tts", choices=["cosyvoice2", "mock"], default="cosyvoice2")
    parser.add_argument("--ws", choices=["auto", "off"], default="auto")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--timeout", type=float, default=360.0)
    args = parser.parse_args()

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_bytes(b"")
    ERR_FILE.write_bytes(b"")

    py = _SIDECAR_ROOT / ".venv" / "Scripts" / "python.exe"
    env = dict(os.environ, PYTHONUNBUFFERED="1")  # stderr 实时可见（定位 gate 卡点）
    out_fh = OUT_FILE.open("wb", buffering=0)
    err_fh = ERR_FILE.open("wb", buffering=0)
    proc = await asyncio.create_subprocess_exec(
        str(py if py.exists() else sys.executable),
        "-m",
        "echoes_sidecar.main",
        "--tts",
        args.tts,
        "--ws",
        args.ws,
        cwd=str(_SIDECAR_ROOT),
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=out_fh,
        stderr=err_fh,
    )
    print(f"[smoke] spawned pid={proc.pid} tts={args.tts} ws={args.ws}")

    frames: list[tuple[int, bool, bytes]] = []
    ws_task = asyncio.create_task(_ws_collector(frames))
    sent = False
    turn_complete: dict[str, object] | None = None
    t0 = time.perf_counter()
    try:
        while time.perf_counter() - t0 < args.timeout:
            await asyncio.sleep(1.0)
            msgs = _stdout_msgs()
            hellos = [m for m in msgs if m.get("type") == "hello"]
            engines: dict[str, bool] = {}
            if hellos:
                raw_engines = hellos[-1].get("engines", [])
                if isinstance(raw_engines, list):
                    engines = {str(e["name"]): bool(e["ready"]) for e in raw_engines}
            completes = [m for m in msgs if m.get("type") == "turn_complete"]
            if completes:
                turn_complete = completes[0]
            texts = [m for m in msgs if m.get("type") == "assistant_text"]
            print(
                f"[smoke] t={time.perf_counter() - t0:6.1f}s eng={engines} "
                f"frames={len(frames)} texts={len(texts)} turn={turn_complete is not None}",
                flush=True,
            )

            if engines.get("tts") and engines.get("asr") and engines.get("llm") and not sent:
                sent = True
                assert proc.stdin is not None
                proc.stdin.write(
                    json.dumps(
                        {"type": "user_text", "session_id": SESSION, "text": args.text},
                        ensure_ascii=False,
                    ).encode("utf-8")
                    + b"\n"
                )
                await proc.stdin.drain()
                print(f"[smoke] sent user_text (t={time.perf_counter() - t0:.1f}s)", flush=True)

            if turn_complete is not None:
                break
        else:
            raise SystemExit(f"整体超时 {args.timeout:.0f}s（turn_complete 未达）")

        await asyncio.sleep(2.0)  # 帧面收尾宽限（末帧可能晚于 turn_complete 落盘）
    finally:
        ws_task.cancel()
        with suppress(asyncio.CancelledError):
            await ws_task
        with suppress(ProcessLookupError):
            proc.kill()
        with suppress(Exception):
            await proc.wait()
        out_fh.close()
        err_fh.close()

    seqs = [seq for seq, _final, _payload in frames]
    finals = [final for _seq, final, _payload in frames]
    non_silent = any(any(byte != 0 for byte in payload) for _s, _f, payload in frames)
    print(f"[smoke] ws frames={len(frames)} seqs={seqs[:12]} final_tail={finals[-3:]}")

    assert frames, "未收到任何音频帧（WS 未连/端口未起）"
    assert all(seqs[i] <= seqs[i + 1] for i in range(len(seqs) - 1)), "seq 非单调"
    assert finals and finals[-1], "未见 IS_FINAL 收尾帧"
    assert turn_complete is not None and turn_complete.get("status") == "SUCCESS"
    if args.tts == "cosyvoice2":
        assert non_silent, "音频载荷全零（mock 味道）"
    print("OK: 端到端真链路全通（user_text → LLM → 真合成 → WS 0x02 帧 → turn SUCCESS）")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit as exc:  # 冒烟失败退出码非零（CI 不跑本脚本，人工验收用）
        print(f"FAIL: {exc}")
        raise
