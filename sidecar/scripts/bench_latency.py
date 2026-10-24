"""延迟基线（ADR-012 / 验收 6.2）：跑 N 轮 turn，把四段耗时算成 P50/P95 报告。

**为什么需要它**：验收第 1、2、5 条都要「本机实测数字」，肉眼掐表既不可复现也不
可回归。`gpu_smoke.py --latency` 量的是引擎单点（模块内），本脚本量的是**整链**：
壳侧一行 `user_text` 进去 → `turn_complete.timings` 出来，中间包含编排、IPC 与
引擎调度——验收判的就是这个数。

**timings 的口径**（易踩坑）：`t` / `timings.*` 都是 sidecar 单调时钟的**绝对刻度**
（自进程启动起算，3.4），不是「本段耗时」。所以分段要减：
    生成首 token   = llm_first_token_ms - state(generating).t
    首 token→首音频 = tts_first_audio_ms - llm_first_token_ms
    turn 总耗时     = total_ms - state(generating).t
减法的被减数 `state(generating).t` 每轮都会发出，所以任意客户端都能算，无需新字段。

用法（cwd = sidecar）：
    python scripts/bench_latency.py --turns 5                      # mock 全链自检
    python scripts/bench_latency.py --turns 10 --llm ollama --tts cosyvoice2 --asr whisper
    python scripts/bench_latency.py --turns 10 --real              # 真机四段，写报告
真机档要求权重就位（~/.cache/echoes/models/）且 ollama 在跑；缺件会明确报错。

产出：scripts/_bench_out/latency_<stamp>.md（表格，可直接贴 ADR-012）与同名 .json。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path

_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
_OUT_DIR = _SIDECAR_ROOT / "scripts" / "_bench_out"

# 验收预算（6.2 表；ADR-012 允许阶段 0 按实测一次性校准 ±20%）
BUDGETS: dict[str, tuple[float, float]] = {
    # 段名: (P50 预算 ms, P95 预算 ms)；0 表示该段不设 P95
    "first_token": (700.0, 0.0),
    "first_audio": (500.0, 0.0),
    "turn_total": (2500.0, 4000.0),
}


def _read_msgs(path: Path) -> list[dict[str, object]]:
    msgs: list[dict[str, object]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return msgs
    for line in text.splitlines():
        if line.startswith("{"):
            with suppress(ValueError):
                msgs.append(json.loads(line))
    return msgs


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def turns_from_msgs(msgs: list[dict[str, object]]) -> list[dict[str, int | None]]:
    """按出现顺序把消息流还原成「每轮四段」（减法口径见模块 docstring）。"""
    turns: list[dict[str, int | None]] = []
    start: int | None = None
    for msg in msgs:
        kind = msg.get("type")
        if kind == "state" and msg.get("state") == "generating":
            start = _as_int(msg.get("t"))
        elif kind == "turn_complete":
            timings = msg.get("timings")
            if not isinstance(timings, dict):  # 畸形帧：跳过而不是算错
                start = None
                continue
            first_token = _as_int(timings.get("llm_first_token_ms"))
            first_audio = _as_int(timings.get("tts_first_audio_ms"))
            total = _as_int(timings.get("total_ms"))
            turns.append(
                {
                    "status": msg.get("status") if isinstance(msg.get("status"), str) else None,
                    "turn_start_t": start,
                    "first_token": _seg(first_token, start),
                    "first_audio": _seg(first_audio, first_token),
                    "turn_total": _seg(total, start),
                }
            )
            start = None
    return turns


def _seg(mark: int | None, base: int | None) -> int | None:
    """绝对刻度差 → 本段耗时（任一缺失即 None：FAILED/CANCELLED 没有首音频）。"""
    if mark is None or base is None:
        return None
    return max(0, mark - base)


def percentile(values: list[float], pct: float) -> float:
    """线性插值分位数（样本少时也不至于只报最大/最小）。"""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def summarize(turns: list[dict[str, int | None]]) -> dict[str, dict[str, float | int]]:
    report: dict[str, dict[str, float | int]] = {}
    for key in ("first_token", "first_audio", "turn_total"):
        values = [float(v) for turn in turns if (v := turn.get(key)) is not None]
        report[key] = {
            "n": len(values),
            "p50": round(percentile(values, 0.50), 1),
            "p95": round(percentile(values, 0.95), 1),
            "min": round(min(values), 1) if values else 0.0,
            "max": round(max(values), 1) if values else 0.0,
        }
    return report


def _verdict(key: str, p50: float, p95: float) -> str:
    budget_p50, budget_p95 = BUDGETS[key]
    if p50 > budget_p50:
        return "❌ 超预算"
    if budget_p95 and p95 > budget_p95:
        return "❌ P95 超预算"
    return "✅" if p50 > 0 else "—"


def render_markdown(
    report: dict[str, dict[str, float | int]],
    *,
    engines: dict[str, str],
    turns: int,
    wall_ms: float,
    stamp: str,
) -> str:
    labels = {
        "first_token": "asr_final/输入 → 首 token",
        "first_audio": "首 token → 首音频块",
        "turn_total": "turn 总耗时（起点 → turn_complete）",
    }
    # mock 全链的毫秒数没有意义（引擎是 `yield` 常量）：判读列一律标 —，
    # 否则一次自检会看起来像"验收通过"，比没有基准更糟。
    mock = all(value == "mock" for value in engines.values())
    lines = [
        f"# 延迟基线 {stamp}",
        "",
        f"引擎：llm={engines['llm']} tts={engines['tts']} asr={engines['asr']}｜"
        f"轮数={turns}｜客户端观测总时长={wall_ms:.0f}ms",
        "",
    ]
    if mock:
        lines.extend(
            [
                "> ⚠️ **mock 自检**：本次只验证脚手架（消息流 → 统计 → 报告）通，" 
                "数字不代表真实延迟，不得作为 ADR-012 的校准依据。",
                "",
            ]
        )
    lines.extend(
        [
            "| 段 | 预算 P50 | P50 | P95 | min | max | n | 判定 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for key, label in labels.items():
        row = report[key]
        b50, b95 = BUDGETS[key]
        budget = f"≤{b50:.0f}ms" + (f" / P95 ≤{b95:.0f}ms" if b95 else "")
        verdict = "—（mock）" if mock else _verdict(key, float(row["p50"]), float(row["p95"]))
        lines.append(
            f"| {label} | {budget} | {row['p50']} | {row['p95']} | "
            f"{row['min']} | {row['max']} | {row['n']} | {verdict} |"
        )
    lines.extend(
        [
            "",
            "口径：`timings.*` 是 sidecar 单调时钟的绝对刻度（3.4），上表已按",
            "`state(generating).t` 与 `llm_first_token_ms` 做差得到分段耗时。",
            "PTT→asr_final（≤600ms）与打断三跳（≤300ms）需真麦克风/真播放，",
            "不在本脚本内——见 ADR-012 的「待上机」两段。",
            "",
        ]
    )
    return "\n".join(lines)


async def run_bench(args: argparse.Namespace) -> int:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = _OUT_DIR / f"latency_{stamp}.stdout.jsonl"
    err_file = _OUT_DIR / f"latency_{stamp}.stderr.log"
    out_file.write_bytes(b"")
    err_file.write_bytes(b"")

    py = _SIDECAR_ROOT / ".venv" / "Scripts" / "python.exe"
    if not py.exists():
        py = _SIDECAR_ROOT / ".venv" / "bin" / "python"
    command = [
        str(py if py.exists() else sys.executable),
        "-m",
        "echoes_sidecar.main",
        "--llm",
        args.llm,
        "--tts",
        args.tts,
        "--asr",
        args.asr,
        "--ws",
        "off",  # 消息面基准：不开 WS（音频面耗时归 gpu_smoke / 打断实测）
    ]
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    out_fh = out_file.open("wb", buffering=0)
    err_fh = err_file.open("wb", buffering=0)
    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(_SIDECAR_ROOT),
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=out_fh,
        stderr=err_fh,
    )
    print(f"[bench] spawned pid={proc.pid} {args.llm}/{args.tts}/{args.asr}")

    started = time.perf_counter()
    deadline = started + args.timeout
    sent = 0
    finished = 0
    ready_logged = False
    try:
        while finished < args.turns and time.perf_counter() < deadline:
            await asyncio.sleep(0.2)
            msgs = _read_msgs(out_file)
            hellos = [m for m in msgs if m.get("type") == "hello"]
            ready: dict[str, bool] = {}
            if hellos:
                raw = hellos[-1].get("engines")
                if isinstance(raw, list):
                    ready = {str(e["name"]): bool(e["ready"]) for e in raw}
            completes = len([m for m in msgs if m.get("type") == "turn_complete"])
            finished = completes
            # 分级就绪（3.4 v1.4）：真引擎要等 warmup 完成才压——否则首轮撞上
            # 「权重还没物化」，量到的是一条失败路径，而不是基线。
            required = [
                name
                for name, chosen in (
                    ("asr", args.asr != "mock"),
                    ("llm", args.llm != "mock"),
                    ("tts", args.tts != "mock"),
                )
                if chosen
            ]
            engines_ready = all(ready.get(name) for name in required)
            if engines_ready and not ready_logged:
                print(
                    f"[bench] 引擎就绪（{'+'.join(required) or 'mock'}），"
                    f"等待 {(time.perf_counter() - started) * 1000:.0f}ms"
                )
                ready_logged = True
            if engines_ready and sent < args.turns and sent == completes:
                assert proc.stdin is not None
                text = args.text if sent == 0 else f"{args.text}（第 {sent + 1} 轮）"
                proc.stdin.write(
                    json.dumps(
                        {"type": "user_text", "session_id": "default", "text": text},
                        ensure_ascii=False,
                    ).encode("utf-8")
                    + b"\n"
                )
                await proc.stdin.drain()
                sent += 1
                print(f"[bench] sent turn {sent}/{args.turns}")
        wall_ms = (time.perf_counter() - started) * 1000
    finally:
        with suppress(ProcessLookupError):
            proc.kill()
        with suppress(Exception):
            await proc.wait()
        out_fh.close()
        err_fh.close()

    if finished < args.turns:
        print(
            f"[bench] 只完成 {finished}/{args.turns} 轮（超时 {args.timeout:.0f}s）："
            f"看 {err_file}",
            file=sys.stderr,
        )

    turns = turns_from_msgs(_read_msgs(out_file))
    failed = [t for t in turns if t["status"] != "SUCCESS"]
    if failed:
        print(f"[bench] 有 {len(failed)} 轮非 SUCCESS：{failed}", file=sys.stderr)
    if not turns:
        print("[bench] 没有可统计的 turn（看 stderr 日志）", file=sys.stderr)
        return 1

    report = summarize(turns)
    markdown = render_markdown(
        report,
        engines={"llm": args.llm, "tts": args.tts, "asr": args.asr},
        turns=len(turns),
        wall_ms=wall_ms,
        stamp=stamp,
    )
    md_path = _OUT_DIR / f"latency_{stamp}.md"
    md_path.write_text(markdown, encoding="utf-8", newline="\n")
    (_OUT_DIR / f"latency_{stamp}.json").write_text(
        json.dumps({"report": report, "turns": turns}, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(markdown)
    print(f"[bench] 报告：{md_path}")
    return 0 if not failed else 2


def main() -> int:
    parser = argparse.ArgumentParser(prog="bench_latency")
    parser.add_argument("--turns", type=int, default=5)
    parser.add_argument("--llm", choices=["mock", "ollama"], default="mock")
    parser.add_argument("--tts", choices=["mock", "cosyvoice2"], default="mock")
    parser.add_argument("--asr", choices=["mock", "whisper"], default="mock")
    parser.add_argument("--text", default="你好，今天有点累，陪我聊聊。")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument(
        "--real",
        action="store_true",
        help="等价于 --llm ollama --tts cosyvoice2 --asr whisper（真机基线）",
    )
    args = parser.parse_args()
    if args.real:
        args.llm, args.tts, args.asr = "ollama", "cosyvoice2", "whisper"
    return asyncio.run(run_bench(args))


if __name__ == "__main__":
    raise SystemExit(main())
