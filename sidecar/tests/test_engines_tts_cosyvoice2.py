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

import asyncio
import struct
import sys
import threading
import types
import wave
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import echoes_sidecar.engines.tts.cosyvoice2 as cosyvoice2_module
from echoes_sidecar.audio.stream import AudioInputStream
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
    """vendored CosyVoice2 替身：预置产出序列 + 推理/spk 注册参数对拍。"""

    def __init__(
        self,
        outs: list[Any],
        exc: Exception | None = None,
        *,
        spk_exc: Exception | None = None,
        spk_fail_prefix: str = "",
    ) -> None:
        self._outs = outs
        self._exc = exc
        self._spk_exc = spk_exc
        self._spk_fail_prefix = spk_fail_prefix
        self.calls: list[dict[str, Any]] = []
        self.spk_calls: list[dict[str, Any]] = []

    def add_zero_shot_spk(self, prompt_text: str, prompt_wav: str, spk_id: str) -> bool:
        self.spk_calls.append(
            {"prompt_text": prompt_text, "prompt_wav": prompt_wav, "spk_id": spk_id}
        )
        if self._spk_exc is not None and spk_id.startswith(self._spk_fail_prefix):
            raise self._spk_exc
        return True

    def inference_zero_shot(
        self,
        tts_text: str,
        prompt_text: str,
        prompt_wav: str,
        zero_shot_spk_id: str = "",
        stream: bool = False,
        speed: float = 1.0,
        text_frontend: bool = True,
    ) -> Iterator[dict[str, Any]]:
        self.calls.append(
            {
                "mode": "zero_shot",
                "tts_text": tts_text,
                "prompt_text": prompt_text,
                "prompt_wav": prompt_wav,
                "zero_shot_spk_id": zero_shot_spk_id,
                "stream": stream,
            }
        )
        yield from ({"tts_speech": o} for o in self._outs)
        if self._exc is not None:
            raise self._exc

    def inference_cross_lingual(
        self,
        tts_text: str,
        prompt_wav: str,
        zero_shot_spk_id: str = "",
        stream: bool = False,
        speed: float = 1.0,
        text_frontend: bool = True,
    ) -> Iterator[dict[str, Any]]:
        self.calls.append(
            {
                "mode": "cross_lingual",
                "tts_text": tts_text,
                "prompt_wav": prompt_wav,
                "zero_shot_spk_id": zero_shot_spk_id,
                "stream": stream,
            }
        )
        yield from ({"tts_speech": o} for o in self._outs)


def _stub_engine(
    outs: list[Any],
    exc: Exception | None = None,
    *,
    spk_exc: Exception | None = None,
    spk_fail_prefix: str = "",
    voices_dir: Path | None = None,
) -> CosyVoice2TtsEngine:
    """轻构造引擎 + 直塞替身 vendored 实例（绕过真加载，不触 torch/vendor）。"""
    kwargs: dict[str, Any] = {"model_dir": Path("Z:/missing/weights")}
    if voices_dir is not None:
        kwargs["voices_dir"] = voices_dir
    engine = CosyVoice2TtsEngine(**kwargs)
    engine._engine = _FakeVendored(
        outs, exc, spk_exc=spk_exc, spk_fail_prefix=spk_fail_prefix
    )
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


async def test_synthesize_waits_for_warmup_in_flight(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """warmup 在途 → 合成**等它装完**（冷启动首轮慢，但不报「没就绪」）。

    真机形态：窗口 ~3s 就 ready，CosyVoice2 权重物化要十几秒；用户恰在这段
    窗口点第一句，硬报 MODEL_NOT_LOADED 等于「点了却说没就绪」。
    """
    engine = CosyVoice2TtsEngine(model_dir=tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def _slow_load() -> None:
        entered.set()
        release.wait(5)
        engine._engine = _FakeVendored([np.full((1, 2), 0.5, dtype=np.float32)])
        engine._spk_ids.add(BUILTIN_DEFAULT_VOICE)

    monkeypatch.setattr(engine, "_load_engine", _slow_load)
    warm = asyncio.create_task(engine.warmup())
    assert await asyncio.to_thread(entered.wait, 5) is True  # 确认已进到加载里

    turn = asyncio.create_task(_collect(engine, "你好", BUILTIN_DEFAULT_VOICE))
    await asyncio.sleep(0.05)
    assert not turn.done(), "warmup 未完成时合成应等待，而不是立刻报错"

    release.set()
    chunks = await turn
    await warm
    assert chunks[-1].is_final is True
    assert chunks[0].data == struct.pack("<hh", 16383, 16383)


async def test_synthesize_after_failed_warmup_raises_real_cause(tmp_path: Path) -> None:
    """warmup 失败后合成：抛当时那次失败的真因（权重缺失优于笼统「未就绪」）。"""
    engine = CosyVoice2TtsEngine(model_dir=tmp_path / "CosyVoice2-0.5B")
    with pytest.raises(EchoesError):
        await engine.warmup()

    with pytest.raises(EchoesError) as exc_info:
        await _collect(engine, "你好", BUILTIN_DEFAULT_VOICE)
    assert exc_info.value.code == ErrorCode.MODEL_NOT_LOADED
    assert "权重不存在" in exc_info.value.message


async def test_synthesize_streams_chunks_with_final() -> None:
    """两段产出 → 两帧真 payload 立刻发出 + 一帧零长度 is_final 收尾。

    **不许扣住末帧盖 is_final**：那会把首音频推迟到下一个 chunk 到达
    （ADR-012 §4.1 实测首段 3.2s 就好、TTFA 却记成 7.7s）。
    """
    engine = _stub_engine(
        [np.full((1, 4), 0.5, dtype=np.float32), np.full((1, 2), -0.5, dtype=np.float32)]
    )
    chunks = await _collect(engine, "你好", BUILTIN_DEFAULT_VOICE)

    assert [c.seq for c in chunks] == [0, 1, 2]
    assert [c.is_final for c in chunks] == [False, False, True]
    assert chunks[0].data == struct.pack("<hhhh", 16383, 16383, 16383, 16383)
    assert chunks[1].data == struct.pack("<hh", -16383, -16383)
    assert chunks[2].data == b""  # 流尾锚点：零长度（壳侧 push_pcm16 直接 return）

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


# ------------------------------ 4.5 分句接线 ------------------------------


async def test_synthesize_splits_sentences_into_separate_inference_calls() -> None:
    """4.5：逐句推理（首句先出），chunk 序号跨句连续，流尾由零长度帧收束。"""
    engine = _stub_engine([np.full((1, 2), 0.25, dtype=np.float32)])
    engine._add_spk(
        BUILTIN_DEFAULT_VOICE, BUILTIN_DEFAULT_PROMPT_TEXT, BUILTIN_DEFAULT_PROMPT_WAV
    )

    chunks = await _collect(engine, "第一句。第二句！", BUILTIN_DEFAULT_VOICE)

    vendored = engine._engine
    assert isinstance(vendored, _FakeVendored)
    assert [c["tts_text"] for c in vendored.calls] == ["第一句。", "第二句！"]
    assert [c.seq for c in chunks] == [0, 1, 2]
    assert [c.is_final for c in chunks] == [False, False, True]


async def test_synthesize_long_sentence_is_split_by_secondary_pause() -> None:
    """超过 60 字的长句按次级停顿拆开：不让首块音频等整句念完。"""
    engine = _stub_engine([np.zeros((1, 2), dtype=np.float32)])
    engine._add_spk(
        BUILTIN_DEFAULT_VOICE, BUILTIN_DEFAULT_PROMPT_TEXT, BUILTIN_DEFAULT_PROMPT_WAV
    )
    long_sentence = "、".join(["很长的一段话"] * 20) + "。"

    await _collect(engine, long_sentence, BUILTIN_DEFAULT_VOICE)

    vendored = engine._engine
    assert isinstance(vendored, _FakeVendored)
    assert len(vendored.calls) > 1
    assert all(len(c["tts_text"]) <= 60 for c in vendored.calls)


async def test_synthesize_uses_cached_spk_embedding_when_registered() -> None:
    """注册过音色就走 spk2info 缓存：合成不再传 prompt 文本/wav（省掉每轮特征提取）。"""
    engine = _stub_engine([np.zeros((1, 2), dtype=np.float32)])
    engine._add_spk(
        BUILTIN_DEFAULT_VOICE, BUILTIN_DEFAULT_PROMPT_TEXT, BUILTIN_DEFAULT_PROMPT_WAV
    )

    await _collect(engine, "你好", BUILTIN_DEFAULT_VOICE)

    vendored = engine._engine
    assert isinstance(vendored, _FakeVendored)
    call = vendored.calls[0]
    assert call["zero_shot_spk_id"] == BUILTIN_DEFAULT_VOICE
    assert call["prompt_text"] == ""
    assert call["prompt_wav"] == ""


# ------------------------------ 克隆真路（ADR-009 zero-shot） ------------------------------


def _seed_wav(path: Path, *, seconds: float = 0.05) -> Path:
    """写一段可被 clone 收下的 PCM16 16k 样本 wav。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = b"\x00\x01" * int(16_000 * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16_000)
        handle.writeframes(frames)
    return path


def _pcm_stream(pcm: bytes) -> AudioInputStream:
    class _Stream(AudioInputStream):
        def __aiter__(self) -> AsyncIterator[AudioChunk]:
            async def _gen() -> AsyncIterator[AudioChunk]:
                yield AudioChunk(data=pcm, seq=0, is_final=True)

            return _gen()

    return _Stream()


async def test_clone_writes_prompt_wav_and_registers_embedding(tmp_path: Path) -> None:
    """clone：prompt 落 voices/clone_<hex>.wav（temp+rename）→ 嵌入注册 → 返回 clone:<hex>。"""
    engine = _stub_engine([], voices_dir=tmp_path / "voices")

    voice_id = await engine.clone(_pcm_stream(b"\x01\x00" * 16))

    assert voice_id.startswith("clone:")
    safe = voice_id.replace(":", "_")
    wav = tmp_path / "voices" / f"{safe}.wav"
    assert wav.is_file()
    with wave.open(str(wav), "rb") as handle:
        assert (handle.getframerate(), handle.getnchannels()) == (16_000, 1)
        assert handle.getnframes() == 16
    # 临时文件不留痕（14.2）
    assert list((tmp_path / "voices").glob(".*.tmp")) == []

    vendored = engine._engine
    assert isinstance(vendored, _FakeVendored)
    assert vendored.spk_calls == [
        {"prompt_text": "", "prompt_wav": str(wav), "spk_id": voice_id}
    ]


async def test_clone_empty_sample_raises_without_touching_disk(tmp_path: Path) -> None:
    """空样本 = CLONE_ENGINE_FAILED，且不产生任何音色资产（14.1 不留孤儿）。"""
    engine = _stub_engine([], voices_dir=tmp_path / "voices")
    with pytest.raises(EchoesError) as exc_info:
        await engine.clone(_pcm_stream(b""))
    assert exc_info.value.code == ErrorCode.CLONE_ENGINE_FAILED
    assert not (tmp_path / "voices").exists() or list((tmp_path / "voices").iterdir()) == []


async def test_clone_without_warmup_raises_model_not_loaded(tmp_path: Path) -> None:
    engine = CosyVoice2TtsEngine(model_dir=tmp_path / "w", voices_dir=tmp_path / "voices")
    with pytest.raises(EchoesError) as exc_info:
        await engine.clone(_pcm_stream(b"\x01\x00" * 8))
    assert exc_info.value.code == ErrorCode.MODEL_NOT_LOADED


async def test_clone_embedding_failure_cleans_wav(tmp_path: Path) -> None:
    """嵌入提取失败 → CLONE_ENGINE_FAILED，且 prompt wav 不残留（不留孤儿资产）。"""
    engine = _stub_engine([], spk_exc=RuntimeError("onnx 炸了"), voices_dir=tmp_path / "voices")
    with pytest.raises(EchoesError) as exc_info:
        await engine.clone(_pcm_stream(b"\x01\x00" * 16))
    assert exc_info.value.code == ErrorCode.CLONE_ENGINE_FAILED
    assert list((tmp_path / "voices").glob("clone_*.wav")) == []


async def test_cloned_voice_synthesizes_via_cross_lingual(tmp_path: Path) -> None:
    """克隆音色没有转写文本 → 走 inference_cross_lingual（不硬填 prompt 文本）。"""
    engine = _stub_engine([np.zeros((1, 2), dtype=np.float32)], voices_dir=tmp_path / "voices")
    voice_id = await engine.clone(_pcm_stream(b"\x01\x00" * 16))

    chunks = await _collect(engine, "你好", voice_id)

    vendored = engine._engine
    assert isinstance(vendored, _FakeVendored)
    call = vendored.calls[0]
    assert call["mode"] == "cross_lingual"
    assert call["zero_shot_spk_id"] == voice_id
    assert call["prompt_wav"].endswith(f"{voice_id.replace(':', '_')}.wav")
    assert chunks[-1].is_final is True


async def test_register_voices_rebuilds_embeddings_from_assets(tmp_path: Path) -> None:
    """重启重建：按 voices/*.wav 重建嵌入（不写权重目录，7.3 下载边界保持只读）。"""
    voices = tmp_path / "voices"
    _seed_wav(voices / "clone_abc.wav")
    engine = _stub_engine([], voices_dir=voices)

    engine._register_voices()

    vendored = engine._engine
    assert isinstance(vendored, _FakeVendored)
    registered = {c["spk_id"] for c in vendored.spk_calls}
    assert registered == {BUILTIN_DEFAULT_VOICE, "clone:abc"}


async def test_register_voices_skips_broken_clone(tmp_path: Path) -> None:
    """单个克隆嵌入重建失败只跳过它，不牵连其它音色（3.4.1 局部报错不全局降级）。"""
    voices = tmp_path / "voices"
    _seed_wav(voices / "clone_bad.wav")
    engine = _stub_engine(
        [], spk_exc=RuntimeError("坏样本"), spk_fail_prefix="clone:", voices_dir=voices
    )

    engine._register_voices()  # 不抛

    # 坏的那支没进音色面，内置音色照常可用
    assert engine._spk_ids == {BUILTIN_DEFAULT_VOICE}


async def test_cloned_voice_missing_wav_raises(tmp_path: Path) -> None:
    """克隆音色资产被删 → VOICE_NOT_AVAILABLE（不静默回退内置音色，2.5）。"""
    engine = _stub_engine([], voices_dir=tmp_path / "voices")
    engine._spk_ids.add("clone:gone")
    with pytest.raises(EchoesError) as exc_info:
        await _collect(engine, "你好", "clone:gone")
    assert exc_info.value.code == ErrorCode.VOICE_NOT_AVAILABLE


async def test_cloned_voice_unregistered_raises(tmp_path: Path) -> None:
    """样本在但嵌入没就绪（重建失败）→ VOICE_NOT_AVAILABLE 并指明原因。"""
    voices = tmp_path / "voices"
    _seed_wav(voices / "clone_ready.wav")
    engine = _stub_engine([], voices_dir=voices)
    with pytest.raises(EchoesError) as exc_info:
        await _collect(engine, "你好", "clone:ready")
    assert exc_info.value.code == ErrorCode.VOICE_NOT_AVAILABLE
    assert "嵌入" in exc_info.value.message


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
