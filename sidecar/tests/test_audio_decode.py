"""音频格式适配（R2a 2.14）：MP3 / OGG-Opus → PCM16 24k。"""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf

from echoes_sidecar.audio.decode import decode_to_pcm16
from echoes_sidecar.core.errors import EchoesError, ErrorCode


def _tone(sample_rate: int, seconds: float = 0.2, channels: int = 1) -> np.ndarray:
    t = np.arange(int(sample_rate * seconds)) / sample_rate
    mono = (0.3 * np.sin(2 * np.pi * 440 * t)).astype("float32")
    return np.column_stack([mono] * channels) if channels > 1 else mono


def _encode(samples: np.ndarray, sample_rate: int, fmt: str, subtype: str | None = None) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format=fmt, subtype=subtype)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("fmt", "subtype", "rate", "channels"),
    [
        ("WAV", None, 44_100, 2),  # 立体声 + 重采样
        ("MP3", None, 24_000, 1),  # 云端 TTS 常见回退格式
        ("OGG", "OPUS", 48_000, 1),  # Opus 只支持 8/12/16/24/48k
    ],
)
def test_decodes_to_24k_mono_pcm16(
    fmt: str, subtype: str | None, rate: int, channels: int
) -> None:
    raw = _encode(_tone(rate, channels=channels), rate, fmt, subtype)
    pcm = decode_to_pcm16(raw, sample_rate=24_000)
    assert len(pcm) % 2 == 0
    samples = np.frombuffer(pcm, dtype="<i2")
    assert len(samples) > 0
    # MP3 / Opus 有编码延迟与填充，允许 ±15% 长度误差；WAV 精确
    expected = 24_000 * 0.2
    tolerance = 0.02 if fmt == "WAV" else 0.15
    assert abs(len(samples) - expected) <= expected * tolerance
    assert np.abs(samples).max() > 1000


def test_empty_and_garbage() -> None:
    assert decode_to_pcm16(b"", sample_rate=24_000) == b""
    with pytest.raises(EchoesError) as err:
        decode_to_pcm16(b"not audio at all", sample_rate=24_000)
    assert err.value.code is ErrorCode.TTS_ENGINE_ERROR
    assert "解码" in err.value.message
