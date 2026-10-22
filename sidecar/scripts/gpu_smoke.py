"""GPU 冒烟脚本（7.2/13.4：L4 层本机工具，不进 CI）。

子命令：
  tts     CosyVoice2 冒烟：实例化 → 流式合成 → 首包延迟(TTFA)/RTF/显存峰值 → wav 落盘
          （后续子命令：--latency 档位矩阵 P50/P95 报告、克隆冒烟——随阶段对齐补）

用法示例（本机，cwd=sidecar）：
  python scripts/gpu_smoke.py tts --text "你好，我是 Echoes。"
  python scripts/gpu_smoke.py tts --mode zero-shot --prompt-text "…" --prompt-wav path/to/x.wav

前置：uv sync 完成（sidecar/.venv）；权重在 ~/.cache/echoes/models/CosyVoice2-0.5B
（7.3 运行时下载边界，modelscope `iic/CosyVoice2-0.5B`）。
结果以一行 JSON 打印（直接供 docs/benchmarks/tier_matrix 回填复制）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

# vendored 引导（ADR-014：等价上游 example.py 的 sys.path 惯例，脚本独立可用）
_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
_VENDOR_ROOT = _SIDECAR_ROOT / "vendor" / "cosyvoice2"
for _p in (str(_SIDECAR_ROOT), str(_VENDOR_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import torch  # noqa: E402

# ORT CUDA EP 的 cudnn/cublas/cufft DLL：torch wheel 自带全套（torch/lib），
# 注入 dll 搜索路径供 onnxruntime-gpu 加载（不污染系统 PATH）
_TORCH_LIB = Path(torch.__file__).parent / "lib"
if torch.cuda.is_available() and _TORCH_LIB.exists():
    import os

    os.add_dll_directory(str(_TORCH_LIB))
    os.environ["PATH"] = f"{_TORCH_LIB}{os.pathsep}{os.environ.get('PATH', '')}"

DEFAULT_MODEL_DIR = Path.home() / ".cache" / "echoes" / "models" / "CosyVoice2-0.5B"
DEFAULT_TEXT = "你好，我是 Echoes。很高兴见到你，今天想聊点什么？"
OUT_DIR = _SIDECAR_ROOT / "scripts" / "_smoke_out"


def _load_engine(model_dir: Path, load_time_seeds: list[float], fp16: bool = False) -> object:
    """实例化 CosyVoice2（低噪声：压 tqdm 进度与上游 logging 的 INFO 轰炸）。"""
    import logging

    logging.getLogger().setLevel(logging.WARNING)
    warnings.filterwarnings("ignore")
    t0 = time.perf_counter()
    from cosyvoice.cli.cosyvoice import CosyVoice2

    engine = CosyVoice2(
        str(model_dir), load_jit=False, load_trt=False, load_vllm=False,
        fp16=fp16, trt_concurrent=1,
    )
    load_time_seeds.append(time.perf_counter() - t0)
    return engine


def _run_synth(engine: object, *, mode: str, text: str, spk: str,
               prompt_text: str, prompt_wav: str | None) -> dict[str, object]:
    """流式合成一次：采 TTFA（生成器首 yield）、总耗时、语音秒数。"""
    if mode == "sft":
        chains = engine.inference_sft(text, spk, stream=True)
    elif mode == "zero-shot":
        if not (prompt_text and prompt_wav):
            raise SystemExit("zero-shot 需要 --prompt-text 与 --prompt-wav")
        chains = engine.inference_zero_shot(text, prompt_text, prompt_wav, stream=True)
    else:
        raise SystemExit(f"未知 mode: {mode}")

    chunks: list[torch.Tensor] = []
    t0 = time.perf_counter()
    ttfa: float | None = None
    for model_output in chains:
        if ttfa is None:
            ttfa = time.perf_counter() - t0
        chunks.append(model_output["tts_speech"].detach().cpu())
    total_s = time.perf_counter() - t0
    audio = torch.concat(chunks, dim=1)
    audio_s = audio.shape[1] / engine.sample_rate
    rtf = total_s / audio_s

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = OUT_DIR / f"cosyvoice2_{mode}_{int(time.time())}.wav"
    import torchaudio

    torchaudio.save(str(wav_path), audio, engine.sample_rate)
    return {
        "mode": mode,
        "speaker": spk if mode == "sft" else f"prompt:{prompt_wav}",
        "ttfa_s": round(ttfa, 3) if ttfa is not None else None,
        "total_s": round(total_s, 3),
        "audio_s": round(audio_s, 3),
        "rtf": round(rtf, 3),
        "sample_rate": engine.sample_rate,
        "wav": str(wav_path),
    }


def cmd_tts(args: argparse.Namespace) -> None:
    if not args.model_dir.exists():
        raise SystemExit(
            f"权重不存在: {args.model_dir}（7.3：modelscope 下载 iic/CosyVoice2-0.5B）"
        )
    cuda = torch.cuda.is_available()
    if cuda:
        torch.cuda.reset_peak_memory_stats()

    _load_times: list[float] = []
    engine = _load_engine(args.model_dir, _load_times, fp16=args.fp16)

    spks = engine.list_available_spks()
    mode = args.mode
    if mode == "sft" and not spks:
        raise SystemExit("权重无内置音色（spk2info 为空），请用 --mode zero-shot")

    spk = args.spk or (spks[0] if spks else "")
    result = _run_synth(engine, mode=mode, text=args.text, spk=spk,
                        prompt_text=args.prompt_text, prompt_wav=args.prompt_wav)
    vram = (
        round(torch.cuda.max_memory_allocated() / 2**20, 1) if cuda else 0.0
    )
    result.update(
        load_s=round(sum(_load_times), 3),
        device="cuda" if cuda else "cpu",
        gpu=(torch.cuda.get_device_name(0) if cuda else None),
        vram_peak_mib=vram,
    )
    print(json.dumps({"gpu_smoke": "tts-cosyvoice2", **result}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(prog="gpu_smoke", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tts = sub.add_parser("tts", help="CosyVoice2 合成冒烟（L4）")
    p_tts.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    p_tts.add_argument("--text", default=DEFAULT_TEXT)
    p_tts.add_argument("--mode", choices=["sft", "zero-shot"], default="sft")
    p_tts.add_argument("--spk", default="", help="内置音色（默认取 list 首个）")
    p_tts.add_argument("--fp16", action="store_true", help="LLM fp16 装载（上游原生构造参数）")
    p_tts.add_argument("--prompt-text", default="", help="zero-shot 提示文本")
    p_tts.add_argument("--prompt-wav", default=None, help="zero-shot 提示音频（16k wav）")
    p_tts.set_defaults(func=cmd_tts)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
