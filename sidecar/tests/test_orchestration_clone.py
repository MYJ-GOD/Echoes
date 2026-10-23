"""克隆闭环（4.5/4.6/2.5/14.1）：样本校验、进度三段、成功绑定、失败落 failed、取消。

层级：L2（mock 引擎，零模型依赖，13.1）；真引擎行为归 L4 本机脚本。
"""

from __future__ import annotations

import time
import wave
from array import array
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.errors import CloneError, EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk, VoiceStatus, WSFrameFlags
from echoes_sidecar.db import Storage
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.engines.tts.mock import MockTTSEngine
from echoes_sidecar.orchestration.clone import CloneService, check_sample, sample_seconds
from echoes_sidecar.session.session import Session
from echoes_sidecar.transport.base import Transport
from echoes_sidecar.transport.local_ws import (
    DIR_INPUT,
    LocalWebSocketTransport,
    encode_audio_frame,
)

SAMPLE_RATE = 16_000


def _tone(seconds: float, amplitude: int = 8000) -> bytes:
    """交变方波 PCM16：RMS ≈ amplitude（-12 dBFS 左右，远高于静音阈值）。"""
    count = int(SAMPLE_RATE * seconds)
    samples = array("h", [amplitude if index % 2 == 0 else -amplitude for index in range(count)])
    return samples.tobytes()


class _RecordingTransport(Transport):
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def recv(self) -> dict[str, Any] | None:
        return None

    async def send(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)

    async def close(self) -> None:
        return None


class _FixedTTS(TTSEngine):
    """返回固定 voice_id 的引擎（测 ID 冲突与绑定）。"""

    def __init__(self, voice_id: str) -> None:
        self.voice_id = voice_id

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        yield AudioChunk(data=b"\x00\x00", seq=0, is_final=True)

    async def clone(self, sample: AudioInputStream) -> str:
        _ = sample
        return self.voice_id


class _FailingTTS(TTSEngine):
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        yield AudioChunk(data=b"\x00\x00", seq=0, is_final=True)

    async def clone(self, sample: AudioInputStream) -> str:
        _ = sample
        raise self.exc


class _CancellingTTS(TTSEngine):
    """引擎返回前触发取消：模拟「用户在推理途中点了取消」。"""

    def __init__(self) -> None:
        self.on_clone: Callable[[], None] | None = None

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        yield AudioChunk(data=b"\x00\x00", seq=0, is_final=True)

    async def clone(self, sample: AudioInputStream) -> str:
        _ = sample
        if self.on_clone is not None:
            self.on_clone()
        return "voice:cancelled"


class _AssetWritingTTS(TTSEngine):
    """ADR-009 真路的形态：引擎自己落 prompt 资产（`clone_<hex>.wav`）再返回 voice_id。"""

    def __init__(self, voices_dir: Path, voice_id: str = "clone:abc123") -> None:
        self.voices_dir = voices_dir
        self.voice_id = voice_id

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        yield AudioChunk(data=b"\x00\x00", seq=0, is_final=True)

    async def clone(self, sample: AudioInputStream) -> str:
        _ = sample
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        target = self.voices_dir / f"{self.voice_id.replace(':', '_')}.wav"
        with wave.open(str(target), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(SAMPLE_RATE)
            handle.writeframes(b"\x00\x00" * 1600)
        return self.voice_id


def _setup(tmp_path: Path) -> tuple[Storage, Session, Path]:
    storage = Storage.open(tmp_path / "db" / "echoes.db")
    now = time.time()
    persona = storage.personas.sync(
        persona_id="default", name="默认人设", system_prompt="s", now=now
    )
    row = storage.sessions.create(session_id="default", persona_id=persona.id, now=now)
    session = Session(
        session_id=row.id,
        profile_id=row.profile_id,
        persona=persona,
        voice_id=row.voice_id,
        created_at=row.started_at,
    )
    return storage, session, tmp_path / "assets"


def _service(
    storage: Storage,
    session: Session,
    assets_root: Path,
    transport: Transport,
    tts: TTSEngine,
) -> CloneService:
    return CloneService(
        transport=transport,
        storage=storage,
        tts=tts,
        session=session,
        assets_root=assets_root,
        t0=time.perf_counter(),
    )


def _progress(sent: list[dict[str, Any]]) -> list[tuple[str, int]]:
    return [
        (str(msg["phase"]), int(msg["pct"])) for msg in sent if msg.get("type") == "clone_progress"
    ]


def _errors(sent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [msg for msg in sent if msg.get("type") == "error"]


# ------------------------------- 样本校验 -------------------------------


def test_sample_seconds_matches_pcm16_16k_mono() -> None:
    assert sample_seconds(_tone(2.0)) == pytest.approx(2.0, abs=1e-3)


def test_short_sample_is_rejected() -> None:
    with pytest.raises(CloneError) as excinfo:
        check_sample(_tone(2.0))
    assert excinfo.value.code is ErrorCode.SAMPLE_TOO_SHORT


def test_silent_sample_is_rejected() -> None:
    with pytest.raises(CloneError) as excinfo:
        check_sample(b"\x00" * (SAMPLE_RATE * 2 * 4))
    assert excinfo.value.code is ErrorCode.SAMPLE_TOO_NOISY


def test_clipped_sample_is_rejected() -> None:
    loud = array("h", [32767] * (SAMPLE_RATE * 4)).tobytes()
    with pytest.raises(CloneError) as excinfo:
        check_sample(loud)
    assert excinfo.value.code is ErrorCode.SAMPLE_TOO_NOISY


def test_normal_sample_passes() -> None:
    check_sample(_tone(3.5))  # 不抛即通过


# ------------------------------- 成功路径 -------------------------------


async def test_clone_success_writes_asset_binds_voice_and_reports_progress(
    tmp_path: Path,
) -> None:
    storage, session, assets_root = _setup(tmp_path)
    transport = _RecordingTransport()
    tts = MockTTSEngine()
    service = _service(storage, session, assets_root, transport, tts)
    pcm = _tone(3.5)
    try:
        assert await service.run(pcm, ["sample-0"]) is True

        # 三段进度齐全（4.5：无进度即假死）
        assert _progress(transport.sent) == [
            ("recording", 100),
            ("training", 10),
            ("training", 100),
            ("checking", 100),
        ]
        assert _errors(transport.sent) == []

        # 音色落库 ready，且 id 采用引擎返回值（4.5 资产身份归引擎）
        voices = storage.voices.list_all()
        assert len(voices) == 1
        voice = voices[0]
        assert voice.status is VoiceStatus.READY
        assert voice.id == session.voice_id
        assert voice.id.startswith("voice:mock-")
        assert voice.display_name == "音色 1"
        assert voice.sample_path.startswith("voices/") and voice.sample_path.endswith(".wav")

        # 会话绑定（2.5/§12 步骤 5）：后续回复用该音色
        bound = storage.sessions.get(session.session_id)
        assert bound is not None and bound.voice_id == voice.id

        # 样本按 14.2 temp+rename 落成合法 16k 单声道 WAV，且没有残留 .tmp
        wav_files = list((assets_root / "voices").glob("*.wav"))
        assert len(wav_files) == 1
        with wave.open(str(wav_files[0]), "rb") as handle:
            assert handle.getnchannels() == 1
            assert handle.getframerate() == SAMPLE_RATE
            assert handle.getnframes() == len(pcm) // 2
        assert not list((assets_root / "voices").glob("*.tmp"))
    finally:
        storage.close()


async def test_engine_written_prompt_asset_is_recorded_as_model_path(
    tmp_path: Path,
) -> None:
    """ADR-009 真路：引擎落的 `clone_<hex>.wav` 被认成 model_path（不猜路径，只认实存文件）。"""
    storage, session, assets_root = _setup(tmp_path)
    transport = _RecordingTransport()
    tts = _AssetWritingTTS(assets_root / "voices")
    service = _service(storage, session, assets_root, transport, tts)
    try:
        assert await service.run(_tone(3.5)) is True

        voice = storage.voices.list_all()[0]
        assert voice.model_path == "voices/clone_abc123.wav"
        assert voice.sample_path != voice.model_path  # 样本与 prompt 是两笔资产
        assert session.voice_id == "clone:abc123"
    finally:
        storage.close()


async def test_display_name_increments_per_voice(tmp_path: Path) -> None:
    storage, session, assets_root = _setup(tmp_path)
    transport = _RecordingTransport()
    try:
        first = _service(storage, session, assets_root, transport, _FixedTTS("voice:one"))
        assert await first.run(_tone(3.5)) is True
        second = _service(storage, session, assets_root, transport, _FixedTTS("voice:two"))
        assert await second.run(_tone(3.5)) is True

        names = sorted(voice.display_name for voice in storage.voices.list_all())
        assert names == ["音色 1", "音色 2"]
        assert session.voice_id == "voice:two"  # 后克隆的覆盖会话绑定
    finally:
        storage.close()


# ------------------------------- 失败路径 -------------------------------


async def test_engine_clone_error_marks_voice_failed_and_cleans_sample(
    tmp_path: Path,
) -> None:
    storage, session, assets_root = _setup(tmp_path)
    transport = _RecordingTransport()
    tts = _FailingTTS(CloneError(ErrorCode.SAMPLE_TOO_NOISY, "引擎判定噪声过大"))
    service = _service(storage, session, assets_root, transport, tts)
    try:
        assert await service.run(_tone(3.5)) is False

        errors = _errors(transport.sent)
        assert len(errors) == 1
        assert errors[0]["code"] == ErrorCode.SAMPLE_TOO_NOISY
        assert errors[0]["fatal"] is False

        voices = storage.voices.list_all()
        assert len(voices) == 1
        assert voices[0].status is VoiceStatus.FAILED
        assert session.voice_id is None  # 禁止回退/误绑（2.5）
        bound = storage.sessions.get(session.session_id)
        assert bound is not None and bound.voice_id is None
        assert list((assets_root / "voices").glob("*.wav")) == []  # 14.1 清理临时文件
    finally:
        storage.close()


async def test_unexpected_engine_crash_maps_to_clone_engine_failed(
    tmp_path: Path,
) -> None:
    storage, session, assets_root = _setup(tmp_path)
    transport = _RecordingTransport()
    service = _service(
        storage, session, assets_root, transport, _FailingTTS(RuntimeError("cuda boom"))
    )
    try:
        assert await service.run(_tone(3.5)) is False
        errors = _errors(transport.sent)
        assert errors[0]["code"] == ErrorCode.CLONE_ENGINE_FAILED
        assert "cuda boom" in str(errors[0]["message"])
    finally:
        storage.close()


async def test_echoes_error_from_engine_is_wrapped_not_leaked(tmp_path: Path) -> None:
    storage, session, assets_root = _setup(tmp_path)
    transport = _RecordingTransport()
    service = _service(
        storage,
        session,
        assets_root,
        transport,
        _FailingTTS(EchoesError(ErrorCode.MODEL_NOT_LOADED, "权重缺失")),
    )
    try:
        assert await service.run(_tone(3.5)) is False
        assert _errors(transport.sent)[0]["code"] == ErrorCode.CLONE_ENGINE_FAILED
    finally:
        storage.close()


async def test_invalid_sample_never_creates_voice_row(tmp_path: Path) -> None:
    """校验在落库前：坏样本不该在库里留下任何音色（含 failed 的噪声行）。"""
    storage, session, assets_root = _setup(tmp_path)
    transport = _RecordingTransport()
    service = _service(storage, session, assets_root, transport, MockTTSEngine())
    try:
        assert await service.run(_tone(1.0)) is False
        assert storage.voices.list_all() == []
        assert _errors(transport.sent)[0]["code"] == ErrorCode.SAMPLE_TOO_SHORT
    finally:
        storage.close()


async def test_cancel_during_clone_discards_result(tmp_path: Path) -> None:
    """clone_cancel 在引擎返回后生效：结果丢弃 + CLONE_CANCELLED + 音色 failed。"""
    storage, session, assets_root = _setup(tmp_path)
    transport = _RecordingTransport()
    tts = _CancellingTTS()
    service = _service(storage, session, assets_root, transport, tts)
    tts.on_clone = service.cancel
    try:
        assert await service.run(_tone(3.5)) is False
        errors = _errors(transport.sent)
        assert errors[0]["code"] == ErrorCode.CLONE_CANCELLED
        assert storage.voices.list_all()[0].status is VoiceStatus.FAILED
        assert session.voice_id is None
    finally:
        storage.close()


async def test_engine_voice_id_collision_is_reported(tmp_path: Path) -> None:
    """引擎返回已存在的 voice_id：读的是别人的资产，必须报错（4.5 身份冲突）。"""
    storage, session, assets_root = _setup(tmp_path)
    transport = _RecordingTransport()
    try:
        first = _service(storage, session, assets_root, transport, _FixedTTS("voice:dup"))
        assert await first.run(_tone(3.5)) is True

        second = _service(storage, session, assets_root, transport, _FixedTTS("voice:dup"))
        assert await second.run(_tone(3.5)) is False
        errors = _errors(transport.sent)
        assert errors[-1]["code"] == ErrorCode.CLONE_ENGINE_FAILED

        # 冲突不产生重复 ready 行；本次尝试的占位行保留为 failed（失败可追溯，2.5）
        voices = storage.voices.list_all()
        ready = [voice for voice in voices if voice.status is VoiceStatus.READY]
        failed = [voice for voice in voices if voice.status is VoiceStatus.FAILED]
        assert [voice.id for voice in ready] == ["voice:dup"]
        assert len(failed) == 1 and failed[0].id != "voice:dup"
        assert session.voice_id == "voice:dup"  # 首次成功绑定未被二次失败污染
    finally:
        storage.close()


# ------------------------------ WS 帧分流 ------------------------------


async def test_clone_frames_do_not_pollute_ptt_stream() -> None:
    """bit2 克隆帧进独立队列：克隆音绝不能进 ASR（3.4 帧语义）。"""
    ws = LocalWebSocketTransport()
    clone_flag = int(WSFrameFlags.CLONE_SAMPLE)
    ws._feed_audio(encode_audio_frame(DIR_INPUT, 0, clone_flag, b"\x01\x00"))
    ws._feed_audio(
        encode_audio_frame(DIR_INPUT, 1, clone_flag | int(WSFrameFlags.IS_FINAL), b"\x02\x00")
    )
    assert await ws.collect_clone_sample() == b"\x01\x00\x02\x00"

    ws._feed_audio(
        encode_audio_frame(DIR_INPUT, 0, int(WSFrameFlags.IS_FINAL), b"\x03\x00")
    )
    assert await ws.next_utterance() == b"\x03\x00"


async def test_clone_sample_collection_returns_none_on_eof() -> None:
    ws = LocalWebSocketTransport()
    ws._feed_audio(
        encode_audio_frame(DIR_INPUT, 0, int(WSFrameFlags.CLONE_SAMPLE), b"\x01\x00")
    )
    ws._mark_eof()
    assert await ws.collect_clone_sample() is None
