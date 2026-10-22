"""CosyVoice2TtsEngine：4.5 契约实现测试（阶段 0 第二周尾部接线）。

口径：
- 分级就绪（同 whisper）：warmup() 由组合根调用；单测桩注入 _engine，不触
  vendored/权重（真链路冒烟 = scripts/gpu_smoke.py，L4 手动档不进 CI）。
- 权重缺失 / 未 warmup → EchoesError(MODEL_NOT_LOADED)；未知音色 / prompt 资产
  缺失 → VOICE_NOT_AVAILABLE（3.4.1 报错不降级）。
- 产出锁三点：逐段 chunk（seq 0..n）、末段 payload + is_final=True、PCM16 LE
  幅度对拍（np_to_pcm16 纯函数；24kHz mono 输出口径 3.4）。
"""

from __future__ import annotations

import struct
import sys
import types
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import echoes_sidecar.engines.tts.cosyvoice2 as cosyvoice2_module
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.engines.tts.cosyvoice2 import (
    BUILTIN_DEFAULT_PROMPT_TEXT,
    BUILTIN_DEFAULT_PROMPT_WAV,
    BUILTIN_DEFAULT_VOICE,
    CosyVoice2TtsEngine,
    np_to_pcm16,
)


class _FakeVendored:
    """vendored CosyVoice2 替身：预置产出序列 + zero-shot 调参记录对拍。"""

    def __init__(self, outs: list[Any], exc: Exception | None = None) -> None:
        self._outs = outs
        self._exc = exc
        self.calls: list[dict[str, Any]] = []

    def inference_zero_shot(
        self,
        tts_text: str,
        prompt_text: str,
        prompt_wav: str,
        stream: bool = False,
        speed: float = 1.0,
        text_frontend: bool = True,
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append(
            {
                "tts_text": tts_text,
                "prompt_text": prompt_text,
                "prompt_wav": prompt_wav,
                "stream": stream,
            }
        )
        yield from ({"tts_speech": o} for o in self._outs)
        if self._exc is not None:
            raise self._exc


def _stub_engine(outs: list[Any], exc: Exception | None = None) -> CosyVoice2TtsEngine:
    """轻构造引擎 + 直塞替身 vendored 实例（绕过真加载，不触 torch/vendor）。"""
    engine = CosyVoice2TtsEngine(model_dir=Path("Z:/missing/weights"))
    engine._engine = _FakeVendored(outs, exc)
    return engine


async def _collect(engine: CosyVoice2TtsEngine, text: str, voice_id: str) -> list[AudioChunk]:
    return [chunk async for chunk in engine.synthesize(text, voice_id)]


def test_builtin_default_prompt_asset_paired() -> None:
    """入库资产自检：wav 与 prompt_text 常量配对存在（重生成时双源同步锁定）。"""
    assert BUILTIN_DEFAULT_PROMPT_WAV.is_file(), "先跑 scripts/make_builtin_prompt.py 生成资产"


def test_engine_is_tts_contract() -> None:
    engine = CosyVoice2TtsEngine()
    assert isinstance(engine, TTSEngine)
    # 7.3 约定权重路径（模型缓存不入库，~/.cache/echoes/models/）
    assert engine._model_dir == (
        Path.home() / ".cache" / "echoes" / "models" / "CosyVoice2-0.5B"
    )


def test_np_to_pcm16_clamps_and_scales() -> None:
    """幅度钳制 [-1,1]、float32 → <i2 量化（朝零截断）、LE 编序（3.4 输出口径）。"""
    data = np_to_pcm16(np.array([0.5, -0.5, 1.5, -1.5], dtype=np.float32))
    assert data == struct.pack("<hhhh", 16383, -16383, 32767, -32767)


def test_np_to_pcm16_flattens_2d() -> None:
    """vendored 产出 shape [1,N]——先 flatten 再量化，不逐行打包。"""
    data = np_to_pcm16(np.array([[0.5, -0.5]], dtype=np.float32))
    assert data == struct.pack("<hh", 16383, -16383)


def test_np_to_pcm16_empty() -> None:
    assert np_to_pcm16(np.zeros((0,), dtype=np.float32)) == b""


async def test_synthesize_without_warmup_raises() -> None:
    """未 warmup 即调用 = MODEL_NOT_LOADED（3.4.1 引擎错误不静默）。"""
    engine = CosyVoice2TtsEngine(model_dir=Path("Z:/missing/weights"))
    with pytest.raises(EchoesError) as exc_info:
        await _collect(engine, "你好", BUILTIN_DEFAULT_VOICE)
    assert exc_info.value.code == ErrorCode.MODEL_NOT_LOADED


async def test_warmup_missing_weights_raises_model_not_loaded(tmp_path: Path) -> None:
    """权重目录缺失 = 报错不降级，绝不触发 vendored 的联网 snapshot_download 回退。"""
    engine = CosyVoice2TtsEngine(model_dir=tmp_path / "CosyVoice2-0.5B")
    with pytest.raises(EchoesError) as exc_info:
        await engine.warmup()
    assert exc_info.value.code == ErrorCode.MODEL_NOT_LOADED


async def test_synthesize_streams_chunks_with_final() -> None:
    """两段产出：seq 0（非终结）→ seq 1（带真实 payload、is_final=True）。"""
    engine = _stub_engine(
        [np.full((1, 4), 0.5, dtype=np.float32), np.full((1, 2), -0.5, dtype=np.float32)]
    )
    chunks = await _collect(engine, "你好", BUILTIN_DEFAULT_VOICE)

    assert [c.seq for c in chunks] == [0, 1]
    assert [c.is_final for c in chunks] == [False, True]
    assert chunks[0].data == struct.pack("<hhhh", 16383, 16383, 16383, 16383)
    assert chunks[1].data == struct.pack("<hh", -16383, -16383)

    vendored = engine._engine
    assert isinstance(vendored, _FakeVendored)
    call = vendored.calls[0]
    assert call["tts_text"] == "你好"
    assert call["prompt_text"] == BUILTIN_DEFAULT_PROMPT_TEXT  # builtin:default 强配对
    assert call["prompt_wav"] == str(BUILTIN_DEFAULT_PROMPT_WAV)
    assert call["stream"] is True


async def test_synthesize_empty_output_yields_eof_frame() -> None:
    """零段产出（清洗后空文本等）→ 单帧 b"" is_final=True 流尾兜底。"""
    engine = _stub_engine([])
    chunks = await _collect(engine, "x", BUILTIN_DEFAULT_VOICE)
    assert chunks == [AudioChunk(data=b"", seq=0, is_final=True)]


async def test_synthesize_unknown_voice_raises() -> None:
    """未知 voice_id → VOICE_NOT_AVAILABLE（阶段 0 仅内置音色面）。"""
    engine = _stub_engine([])
    with pytest.raises(EchoesError) as exc_info:
        await _collect(engine, "你好", "voice:future-clone")
    assert exc_info.value.code == ErrorCode.VOICE_NOT_AVAILABLE


async def test_builtin_prompt_asset_missing_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """prompt wav 资产缺失 → VOICE_NOT_AVAILABLE（不回退其它音源，2.5/3.4.1）。"""
    monkeypatch.setattr(
        cosyvoice2_module, "BUILTIN_DEFAULT_PROMPT_WAV", tmp_path / "nope.wav"
    )
    engine = _stub_engine([])
    with pytest.raises(EchoesError) as exc_info:
        await _collect(engine, "你好", BUILTIN_DEFAULT_VOICE)
    assert exc_info.value.code == ErrorCode.VOICE_NOT_AVAILABLE


async def test_worker_thread_error_bridges_tts_engine_error() -> None:
    """线程内异常经队列桥回主协程 → EchoesError(TTS_ENGINE_ERROR)，不静默不降级。"""
    engine = _stub_engine([np.zeros((1, 2), dtype=np.float32)], exc=RuntimeError("boom"))
    with pytest.raises(EchoesError) as exc_info:
        await _collect(engine, "你好", BUILTIN_DEFAULT_VOICE)
    assert exc_info.value.code == ErrorCode.TTS_ENGINE_ERROR


def _seed_wetext_cache(monkeypatch: pytest.MonkeyPatch, base: Path) -> None:
    """临时 MODELSCOPE_CACHE 下按需建 4 个 fst（或假装缺失）供缓存校验用。"""
    monkeypatch.setenv("MODELSCOPE_CACHE", str(base))
    for rel in cosyvoice2_module._WETEXT_SNAPSHOT_FILES:
        (base / "hub" / "pengzhendong" / "wetext" / rel).parent.mkdir(
            parents=True, exist_ok=True
        )


def test_wetext_cache_missing_raises_model_not_loaded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """wetext fst 缓存缺件 → MODEL_NOT_LOADED（boot 报错不降级，绝不联网补拉）。"""
    _seed_wetext_cache(monkeypatch, tmp_path)  # 目录在但 fst 一个都没有
    with pytest.raises(EchoesError) as exc_info:
        cosyvoice2_module._install_wetext_offline_snapshot()
    assert exc_info.value.code == ErrorCode.MODEL_NOT_LOADED


def test_wetext_offline_patch_forces_local_files_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """缓存齐备时补丁生效：wetext 的 snapshot_download 调用强制 local_files_only。"""
    _seed_wetext_cache(monkeypatch, tmp_path)
    for rel in cosyvoice2_module._WETEXT_SNAPSHOT_FILES:
        (tmp_path / "hub" / "pengzhendong" / "wetext" / rel).touch()

    calls: list[dict[str, Any]] = []

    def _spy(model_id: str, **kwargs: Any) -> str:
        calls.append({"model_id": model_id, **kwargs})
        return "Z:/stub/root"

    inner = types.SimpleNamespace(snapshot_download=_spy)
    monkeypatch.setitem(sys.modules, "wetext", types.SimpleNamespace(wetext=inner))

    cosyvoice2_module._install_wetext_offline_snapshot()

    assert inner.snapshot_download is not _spy  # 已被离线包装替换
    inner.snapshot_download("pengzhendong/wetext")
    assert calls == [{"model_id": "pengzhendong/wetext", "local_files_only": True}]


def test_load_engine_weights_gate_precedes_wetext_patch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """权重缺失时在 wetext 安装面之前截断（离线红线①先于②，宁缺毋联网）。"""
    calls: list[bool] = []
    monkeypatch.setattr(
        cosyvoice2_module,
        "_install_wetext_offline_snapshot",
        lambda: calls.append(True),
    )
    engine = CosyVoice2TtsEngine(model_dir=tmp_path / "absent-weights")
    with pytest.raises(EchoesError):
        engine._load_engine()
    assert not calls
