"""克隆闭环（4.5/4.6/2.5）：样本校验 → 资产落盘 → engine.clone → voice 落库 → 会话绑定。

为何在编排层：clone 要同时向 transport 发进度/错误、驱动引擎、写存储、改 Session，
这是编排职责；session 层与 transport 层是同层兄弟（15.2 分层），放在 session 里
会破坏「同层不互 import」。

契约要点：
- **报错而非降级**（2.5/4.5）：任何失败都发 `error` 事件 + 音色置 `failed`，绝不回退内置音色；
- **无进度即假死**（4.5）：`clone_progress` 覆盖 recording → training → checking 三段；
- **开工即落 training 行**（14.1）：kill/断电后由 `VoiceRepo.fail_orphans` 收敛为 failed；
- **临时文件 temp+rename**（14.2）：样本不允许写一半就对外可见。

取消语义（当前实现诚实地只做到协作取消）：`cancel()` 在阶段间与引擎返回后检查；
引擎内部推理是同步阻塞调用，真正的实时中断要等三跳协议与引擎级取消（阶段 2）。
"""
from __future__ import annotations

import asyncio
import math
import os
import sys
import time
import wave
from array import array
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path
from typing import Literal
from uuid import uuid4

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.cancel import aclose
from echoes_sidecar.core.errors import CloneError, EchoesError, ErrorCode
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.db import Storage
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.ipc import CloneProgressMsg, ErrorMsg
from echoes_sidecar.session.session import Session
from echoes_sidecar.transport.base import Transport

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2  # PCM16
# 2.4/6：录 3–6 秒；下限卡 3s（不足则引擎无足够音素，宁可不克隆也不产出劣质音色）
MIN_SAMPLE_SECONDS = 3.0
# 电平校验：近乎静音或大量削波的样本对克隆毫无价值（阶段 2 的相似度质检是另一层）
MIN_RMS_DBFS = -45.0
MAX_CLIPPING_RATIO = 0.05
# 阶段 2 相似度质检（campplus 余弦）；阈值先保守取 0.6，真机校准后走 ADR 修订。
MIN_SPEAKER_SIMILARITY = 0.6
QUALITY_REFERENCE_TEXT = "你好，这是音色质检。"

ClonePhase = Literal["recording", "training", "checking"]


class _BytesAudioStream(AudioInputStream):
    """整段 PCM16 → 4.2 输入流（克隆契约只要 AudioInputStream，不关心分片）。"""

    def __init__(self, pcm: bytes) -> None:
        self._pcm = pcm

    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        async def _gen() -> AsyncIterator[AudioChunk]:
            yield AudioChunk(data=self._pcm, seq=0, is_final=True)

        return _gen()


def sample_seconds(pcm: bytes) -> float:
    """PCM16 16k mono 的时长（秒）。"""
    return len(pcm) / (SAMPLE_RATE * SAMPLE_WIDTH)


def check_sample(pcm: bytes, *, min_seconds: float = MIN_SAMPLE_SECONDS) -> None:
    """引擎级样本校验（2.5/阶段 0）：时长不足、近乎静音、严重削波 → CloneError。

    绝不静默放行：劣质样本克隆出来的音色会伴随用户很久，这是「错误记忆比没有记忆更毒」
    在音色上的同构问题。
    """
    seconds = sample_seconds(pcm)
    if seconds < min_seconds:
        raise CloneError(
            ErrorCode.SAMPLE_TOO_SHORT,
            f"样本过短：{seconds:.2f}s < {min_seconds:.1f}s（请录 3–6 秒连续说话）",
        )

    samples = array("h")
    usable = len(pcm) - (len(pcm) % SAMPLE_WIDTH)
    samples.frombytes(pcm[:usable])  # 小端主机（x64/arm64）直读；PCM16 LE 是协议口径
    if not samples:
        raise CloneError(ErrorCode.SAMPLE_TOO_NOISY, "样本不含有效音频帧")

    peak = 0
    square_sum = 0
    clipped = 0
    for value in samples:
        magnitude = value if value >= 0 else -value
        if magnitude > peak:
            peak = magnitude
        if magnitude >= 32_767:
            clipped += 1
        square_sum += value * value

    count = len(samples)
    clipping_ratio = clipped / count
    if peak == 0:
        raise CloneError(ErrorCode.SAMPLE_TOO_NOISY, "样本近乎静音（峰值 0）")

    rms = (square_sum / count) ** 0.5
    rms_dbfs = 20.0 * _log10(rms / 32_768.0)
    if rms_dbfs < MIN_RMS_DBFS:
        raise CloneError(
            ErrorCode.SAMPLE_TOO_NOISY,
            f"样本电平过低：RMS {rms_dbfs:.1f} dBFS < {MIN_RMS_DBFS:.0f} dBFS"
            "（离麦太远或环境太吵）",
        )
    if clipping_ratio > MAX_CLIPPING_RATIO:
        raise CloneError(
            ErrorCode.SAMPLE_TOO_NOISY,
            f"样本严重削波：{clipping_ratio * 100:.1f}% 采样点触顶（离麦太近或增益过高）",
        )


def _log10(value: float) -> float:
    """避免 math.log10(0) 的 ValueError（峰值已在调用前判零，这里只做防御）。"""
    from math import log10

    return log10(value) if value > 0 else float("-inf")


class CloneService:
    """会话级克隆编排（4.6：clone_start/clone_cancel 的响应方）。"""

    def __init__(
        self,
        *,
        transport: Transport,
        storage: Storage,
        tts: TTSEngine,
        session: Session,
        assets_root: Path,
        t0: float,
        clock: Callable[[], float] = time.time,
        min_similarity: float = MIN_SPEAKER_SIMILARITY,
    ) -> None:
        self._transport = transport
        self._storage = storage
        self._tts = tts
        self._session = session
        self._assets_root = assets_root
        self._t0 = t0
        self._clock = clock
        self._min_similarity = min_similarity
        self._cancel = asyncio.Event()

    def set_session(self, session: Session) -> None:
        """R1c 切换活跃会话：后续克隆/绑定写到新会话。"""
        self._session = session

    # ------------------------------ 对外接口 ------------------------------

    def cancel(self) -> None:
        """请求取消（3.4 clone_cancel）：在阶段边界生效，不假装能打断引擎内部推理。"""
        self._cancel.set()

    async def run(self, pcm: bytes, sample_keys: Sequence[str] = ()) -> bool:
        """执行一次克隆；返回是否成功（失败已向 UI 报错，不抛给主循环）。"""
        self._cancel.clear()
        _ = sample_keys  # 3.4：样本内容以 WS 帧为准；keys 仅供壳侧对账，sidecar 不依赖
        voice_id = uuid4().hex
        current_id = voice_id
        sample_file: Path | None = None

        try:
            check_sample(pcm)
            await self._emit_progress("recording", 100)

            sample_file = await asyncio.to_thread(self._write_sample, voice_id, pcm)
            self._storage.voices.insert_training(
                voice_id=voice_id,
                display_name=self._next_display_name(),
                sample_path=self._rel(sample_file),
                now=self._now(),
            )
            await self._emit_progress("training", 10)
            self._raise_if_cancelled("克隆开始前取消")

            engine_voice_id = await self._tts.clone(_BytesAudioStream(pcm))
            if self._cancel.is_set():
                # 引擎已跑完但用户不要了：结果丢弃（样本文件随失败路径清理）
                raise CloneError(ErrorCode.CLONE_CANCELLED, "克隆已取消（引擎返回后丢弃结果）")

            await self._emit_progress("training", 100)
            self._storage.voices.adopt_id(voice_id, engine_voice_id)
            current_id = engine_voice_id
            self._raise_if_cancelled("质检前取消")

            # 阶段 2 质检：引擎声明支持相似度质检时（CosyVoice2 campplus），
            # 用克隆音色合成一句参考文本，与原样本算余弦；mock 引擎能力位为假则跳过。
            # 能力位来自 4.5 的 TTS 契约（v1.4.4 追加），不再是 getattr 鸭子探测。
            if self._tts.supports_similarity_check:
                await self._emit_progress("checking", 10)
                reference = await self._collect_reference(engine_voice_id)
                raw_score = await self._tts.speaker_similarity(pcm, reference)
                score = float(raw_score)
                if not math.isfinite(score):
                    raise CloneError(
                        ErrorCode.CLONE_ENGINE_FAILED, "音色质检返回非法分数"
                    )
                score = max(0.0, min(1.0, score))
                self._storage.voices.set_quality(engine_voice_id, score)
                if score < self._min_similarity:
                    raise CloneError(
                        ErrorCode.CLONE_QUALITY_LOW,
                        f"音色相似度 {score:.2f} < {self._min_similarity:.2f}，请重新录制",
                    )
                self._raise_if_cancelled("质检后取消")

            self._storage.voices.mark_ready(
                engine_voice_id, model_path=self._existing_model_rel(engine_voice_id)
            )

            # 2.5/§12 步骤 5：绑定当前会话，后续回复全用该音色
            self._session.voice_id = engine_voice_id
            self._storage.sessions.bind_voice(self._session.session_id, engine_voice_id)
            await self._emit_progress("checking", 100)
            return True
        except CloneError as exc:
            await self._fail(current_id, exc, sample_file)
            return False
        except EchoesError as exc:
            await self._fail(
                current_id,
                CloneError(ErrorCode.CLONE_ENGINE_FAILED, f"克隆引擎失败：{exc.message}"),
                sample_file,
            )
            return False
        except Exception as exc:  # noqa: BLE001  克隆面不允许异常逃逸到主循环
            await self._fail(
                current_id,
                CloneError(ErrorCode.CLONE_ENGINE_FAILED, f"克隆异常：{exc}"),
                sample_file,
            )
            return False

    # ------------------------------ 内部实现 ------------------------------

    def _now(self) -> float:
        return float(self._clock())

    def _now_ms(self) -> int:
        return int((self._now() - self._t0) * 1000)

    def _raise_if_cancelled(self, reason: str) -> None:
        if self._cancel.is_set():
            raise CloneError(ErrorCode.CLONE_CANCELLED, reason)

    async def _emit_progress(self, phase: ClonePhase, pct: int) -> None:
        await self._transport.send(
            CloneProgressMsg(
                session_id=self._session.session_id,
                phase=phase,
                pct=max(0, min(100, pct)),
                t=self._now_ms(),
            ).model_dump(mode="json")
        )

    async def _collect_reference(self, voice_id: str) -> bytes:
        """用克隆音色合成质检参考音频（24k PCM16），供说话人相似度比较。"""
        parts: list[bytes] = []
        stream = self._tts.synthesize(QUALITY_REFERENCE_TEXT, voice_id)
        try:
            async for chunk in stream:
                if chunk.data:
                    parts.append(chunk.data)
        finally:
            await aclose(stream)
        pcm = b"".join(parts)
        if not pcm:
            raise CloneError(ErrorCode.CLONE_ENGINE_FAILED, "音色质检参考音频为空")
        return pcm

    def _voices_dir(self) -> Path:
        return self._assets_root / "voices"

    def _rel(self, path: Path) -> str:
        """5.1/3.2：库里只存相对资产目录的路径。"""
        return path.relative_to(self._assets_root).as_posix()

    def _write_sample(self, voice_id: str, pcm: bytes) -> Path:
        """样本落盘（temp+rename，14.2）：文件名用无歧义的 hex id，避免 ID 里的 ':'。"""
        target = self._voices_dir() / f"{voice_id}.wav"
        return self._atomic_write_wav(target, pcm)

    def _atomic_write_wav(self, target: Path, pcm: bytes) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.tmp")
        try:
            with wave.open(str(tmp), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(SAMPLE_WIDTH)
                handle.setframerate(SAMPLE_RATE)
                handle.writeframes(pcm[: len(pcm) - (len(pcm) % SAMPLE_WIDTH)])
            os.replace(tmp, target)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise CloneError(
                ErrorCode.CLONE_ENGINE_FAILED, f"样本写盘失败：{target}（{exc}）"
            ) from exc
        return target

    def _existing_model_rel(self, voice_id: str) -> str | None:
        """引擎产出的资产文件（若有）：不猜路径，只认资产目录里真实存在的文件。

        glob 已按引擎返回的 voice_id 收窄（`clone:<hex>` → `clone_<hex>.*`），
        不会误认样本（样本名是克隆前生成的裸 hex）。ADR-009 的 zero-shot 路把
        prompt wav 本身当资产，所以这里**不再跳过 .wav**。
        """
        safe = voice_id.replace(":", "_")
        for candidate in sorted(self._voices_dir().glob(f"{safe}.*")):
            return self._rel(candidate)
        return None

    def _next_display_name(self) -> str:
        """5.1：自动生成「音色 N」——取已用编号的最大值 +1，不引入对象元数据（2.4）。

        不能用「行数 +1」：删过/失败过的行会让编号回落，出现两个「音色 3」，
        用户在列表里就分不清哪个是哪个（名字是唯一的辨识手段）。
        """
        highest = 0
        for row in self._storage.voices.list_all():
            suffix = row.display_name.removeprefix("音色 ")
            if suffix == row.display_name:  # 不是自动生成的样式，跳过
                continue
            try:
                highest = max(highest, int(suffix))
            except ValueError:  # 「音色 A」这类手写名不影响编号
                continue
        return f"音色 {highest + 1}"

    async def _fail(self, voice_id: str, exc: CloneError, sample_file: Path | None) -> None:
        """失败收束（4.5）：音色置 failed + error 事件 + 清理样本（14.1）。"""
        try:
            self._storage.voices.mark_failed(voice_id)
        except EchoesError as store_exc:
            # 行可能压根没建（校验就失败）；不掩盖原始错误
            print(f"[sidecar] 克隆失败但音色置 failed 未生效: {store_exc}", file=sys.stderr)
        if sample_file is not None:
            try:
                await asyncio.to_thread(sample_file.unlink, True)
            except OSError as os_exc:
                # 不遮蔽参数 exc：except 块退出时该名字会被删除，后面还要用 exc.code
                print(f"[sidecar] 失败样本清理未完成: {os_exc}", file=sys.stderr)
        await self._transport.send(
            ErrorMsg(
                session_id=self._session.session_id,
                code=exc.code,
                message=exc.message,
                fatal=False,
                t=self._now_ms(),
            ).model_dump(mode="json")
        )


__all__ = ["CloneService", "check_sample", "sample_seconds"]
