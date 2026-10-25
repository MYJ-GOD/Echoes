"""阶段 2 克隆质检：campplus 相似度门禁（高/低/无能力/合成失败）。"""

from __future__ import annotations

import time
from array import array
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk, VoiceStatus
from echoes_sidecar.db import Storage
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.orchestration.clone import CloneService
from echoes_sidecar.session.session import Session
from echoes_sidecar.transport.base import Transport

SAMPLE_RATE = 16_000


def _tone(seconds: float, amplitude: int = 8000) -> bytes:
    count = int(SAMPLE_RATE * seconds)
    samples = array("h", [amplitude if i % 2 == 0 else -amplitude for i in range(count)])
    return samples.tobytes()


class _Transport(Transport):
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def recv(self) -> dict[str, Any] | None:
        return None

    async def send(self, msg: dict[str, Any]) -> None:
        self.sent.append(msg)

    async def close(self) -> None:
        return None


class QualityTTS(TTSEngine):
    """克隆成功 + 质检分数可控；synthesize 供参考音频收集。"""

    def __init__(self, score: float, *, voice_id: str = "clone:quality") -> None:
        self.score = score
        self.voice_id = voice_id
        self.synth_calls = 0
        self.sample_len = 0
        self.synth_len = 0

    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        self.synth_calls += 1
        yield AudioChunk(data=b"\x00\x00" * 2400, seq=0, is_final=True)

    async def clone(self, sample: Any) -> str:
        _ = sample
        return self.voice_id

    async def speaker_similarity(self, sample_pcm: bytes, synth_pcm: bytes) -> float:
        self.sample_len = len(sample_pcm)
        self.synth_len = len(synth_pcm)
        return self.score


class NoQualityTTS(QualityTTS):
    """没有 speaker_similarity 的引擎（mock 形态）：跳过质检。"""

    speaker_similarity = None  # type: ignore[assignment]


class ExplodingSynthTTS(QualityTTS):
    async def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        _ = (text, voice_id)
        raise EchoesError(ErrorCode.TTS_ENGINE_ERROR, "synth boom")
        yield AudioChunk(data=b"", seq=0)  # pragma: no cover


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
        min_similarity=0.6,
    )


def _progress(sent: list[dict[str, Any]]) -> list[tuple[str, int]]:
    return [
        (str(msg["phase"]), int(msg["pct"]))
        for msg in sent
        if msg.get("type") == "clone_progress"
    ]


def _errors(sent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [msg for msg in sent if msg.get("type") == "error"]


async def test_high_similarity_marks_ready_and_binds(tmp_path: Path) -> None:
    storage, session, assets = _setup(tmp_path)
    tts = QualityTTS(0.91)
    transport = _Transport()
    try:
        ok = await _service(storage, session, assets, transport, tts).run(_tone(3.5))
        assert ok is True
        assert session.voice_id == "clone:quality"
        row = storage.voices.get("clone:quality")
        assert row is not None
        assert row.status is VoiceStatus.READY
        assert row.quality_score == 0.91
        assert _progress(transport.sent) == [
            ("recording", 100),
            ("training", 10),
            ("training", 100),
            ("checking", 10),
            ("checking", 100),
        ]
        assert _errors(transport.sent) == []
        assert tts.synth_calls == 1
        assert tts.sample_len > 0 and tts.synth_len > 0
    finally:
        storage.close()


async def test_low_similarity_marks_failed_and_does_not_bind(tmp_path: Path) -> None:
    storage, session, assets = _setup(tmp_path)
    transport = _Transport()
    try:
        ok = await _service(storage, session, assets, transport, QualityTTS(0.21)).run(
            _tone(3.5)
        )
        assert ok is False
        assert session.voice_id is None
        row = storage.voices.get("clone:quality")
        assert row is not None
        assert row.status is VoiceStatus.FAILED
        assert row.quality_score == 0.21
        errors = _errors(transport.sent)
        assert [msg["code"] for msg in errors] == ["CLONE_QUALITY_LOW"]
        # 样本已清理（14.1 不留孤儿资产）
        assert not list((assets / "voices").glob("*.wav"))
    finally:
        storage.close()


async def test_engine_without_scorer_skips_quality(tmp_path: Path) -> None:
    storage, session, assets = _setup(tmp_path)
    transport = _Transport()
    tts = NoQualityTTS(0.0, voice_id="clone:plain")
    try:
        ok = await _service(storage, session, assets, transport, tts).run(_tone(3.5))
        assert ok is True
        assert session.voice_id == "clone:plain"
        row = storage.voices.get("clone:plain")
        assert row is not None
        assert row.status is VoiceStatus.READY
        assert row.quality_score is None
        assert ("checking", 10) not in _progress(transport.sent)
        assert ("checking", 100) in _progress(transport.sent)
        assert tts.synth_calls == 0
    finally:
        storage.close()


async def test_reference_synthesis_failure_marks_failed(tmp_path: Path) -> None:
    storage, session, assets = _setup(tmp_path)
    transport = _Transport()
    try:
        ok = await _service(
            storage, session, assets, transport, ExplodingSynthTTS(0.9)
        ).run(_tone(3.5))
        assert ok is False
        assert session.voice_id is None
        row = storage.voices.get("clone:quality")
        assert row is not None
        assert row.status is VoiceStatus.FAILED
        assert [msg["code"] for msg in _errors(transport.sent)] == [
            "CLONE_ENGINE_FAILED"
        ]
    finally:
        storage.close()


async def test_non_finite_score_marks_failed(tmp_path: Path) -> None:
    storage, session, assets = _setup(tmp_path)
    transport = _Transport()
    try:
        ok = await _service(
            storage, session, assets, transport, QualityTTS(float("nan"))
        ).run(_tone(3.5))
        assert ok is False
        assert [msg["code"] for msg in _errors(transport.sent)] == [
            "CLONE_ENGINE_FAILED"
        ]
    finally:
        storage.close()
