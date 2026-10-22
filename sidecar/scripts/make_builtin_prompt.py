"""生成 builtin:default 音色的零样本 prompt wav（一次性资产；全程离线不联网）。

Windows SAPI「Microsoft Huihui Desktop」（zh-CN）合成 → 16kHz mono PCM16。
产物落 engines/tts/assets/builtin_default_prompt.wav 并入库；PROMPT_TEXT 单一
来源 = engines/tts/cosyvoice2.py 的 BUILTIN_DEFAULT_PROMPT_TEXT（这里 import）。
zero-shot 声音克隆的前提是 wav 与文本严格配对——改文本必须重跑本脚本重生成。

用法（cwd=sidecar）：.venv/Scripts/python.exe scripts/make_builtin_prompt.py
"""

from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

# vendored 引导同款惯例：脚本独立可用（engines 常量配对来源）
_SIDECAR_ROOT = Path(__file__).resolve().parents[1]
if str(_SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(_SIDECAR_ROOT))

from echoes_sidecar.engines.tts.cosyvoice2 import BUILTIN_DEFAULT_PROMPT_TEXT  # noqa: E402


def main() -> None:
    out = (
        _SIDECAR_ROOT
        / "echoes_sidecar"
        / "engines"
        / "tts"
        / "assets"
        / "builtin_default_prompt.wav"
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.SelectVoice('Microsoft Huihui Desktop'); "
        f"$s.SetOutputToWaveFile('{out}', "
        "(New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, "
        "[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, "
        "[System.Speech.AudioFormat.AudioChannel]::Mono))); "
        f"$s.Speak('{BUILTIN_DEFAULT_PROMPT_TEXT}'); $s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)

    with wave.open(str(out), "rb") as w:
        rate = w.getframerate()
        n_channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        n_frames = w.getnframes()
    if (rate, n_channels, sampwidth) != (16000, 1, 2):
        raise SystemExit(
            f"口径不符（须 16kHz mono PCM16）: {rate}Hz {n_channels}ch {sampwidth * 8}bit"
        )
    print(
        f"OK {out} rate={rate} ch={n_channels} bits={sampwidth * 8} "
        f"dur={n_frames / rate:.2f}s"
    )


if __name__ == "__main__":
    main()
