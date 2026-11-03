"""云端 TTS 的音频格式适配（R2a 2.14；§11 决策 8：sidecar Python 解码）。

**为什么不在 Rust 播放端解码**：`AudioChunk` 是冻结协议里唯一的音频形态（PCM16）。
在播放端解码要么改协议（新增格式字段 + 采样率协商），要么让壳侧缓存非 PCM 再
转码——两者都会把 provider 差异泄漏进壳。Python 侧已有 libsndfile
（soundfile 0.12 / libsndfile 1.2：MP3、OGG-Vorbis、OGG-Opus），解码 + 重采样后
统一成 16k/24k PCM16，播放层完全无感。

**只按需加载**：纯 PCM 端点不会 import soundfile/scipy；云端档不因此多背一份
解码库的启动成本。重采样用 `resample_poly`（抗混叠），scipy 缺失时退回线性插值
并记日志——只影响非 PCM 端点的音质，不影响协议与隐私语义。
"""

from __future__ import annotations

import io
import sys
from math import gcd

import numpy as np

from echoes_sidecar.core.errors import EchoesError, ErrorCode


def decode_to_pcm16(data: bytes, *, sample_rate: int) -> bytes:
    """任意受支持容器（WAV/MP3/OGG/Opus/FLAC…）→ PCM16 mono @ `sample_rate`。"""
    if not data:
        return b""
    try:
        import soundfile as sf  # type: ignore[import-untyped]  # 上游不带 stubs

        samples, rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except Exception as exc:  # noqa: BLE001  解码库/格式问题统一折成引擎错误
        raise EchoesError(
            ErrorCode.TTS_ENGINE_ERROR,
            f"云端音频无法解码（支持 PCM / MP3 / OGG / Opus）：{exc}",
        ) from exc
    if samples.size == 0:
        return b""
    samples = np.asarray(samples, dtype=np.float32)
    mono = samples.mean(axis=1) if samples.shape[1] > 1 else samples[:, 0]
    if int(rate) != sample_rate:
        mono = _resample(mono, int(rate), sample_rate)
    clipped = np.clip(mono, -1.0, 1.0)
    pcm: np.ndarray = (clipped * 32767.0).astype("<i2")
    return pcm.tobytes()


def _resample(samples: np.ndarray, src: int, dst: int) -> np.ndarray:
    up = dst // gcd(src, dst)
    down = src // gcd(src, dst)
    try:
        from scipy.signal import resample_poly
    except ImportError:
        print(
            "[sidecar] scipy 不可用：云端音频改用线性插值重采样（音质略降）",
            file=sys.stderr,
        )
        return _linear_resample(samples, src, dst)
    return np.asarray(resample_poly(samples, up, down), dtype=np.float32)


def _linear_resample(samples: np.ndarray, src: int, dst: int) -> np.ndarray:
    target = int(round(len(samples) * dst / src))
    if target <= 0:
        return samples[:0]
    x_old = np.arange(len(samples), dtype=np.float64) / src
    x_new = np.arange(target, dtype=np.float64) / dst
    return np.asarray(np.interp(x_new, x_old, samples), dtype=np.float32)


__all__ = ["decode_to_pcm16"]
