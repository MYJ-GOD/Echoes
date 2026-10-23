"""编排层（4.3/10）：三节点收敛点——compose → generate → speak。

**为什么要有这一层**：`main.py` 是组合根（3.2「具体引擎只在这里实例化」），职责是
装配与协议面；"一次 turn 的业务顺序"（状态迁移 → 提示组装 → 流式生成 → 逐句出声 →
收尾落库）属于编排。把它写回 main.py 会让装配与流程重新缠在一起——阶段 1 接记忆
检索时必然长出第二套 turn 逻辑（这正是 2026-10-23 审计给的头号技术债）。

**冻结面**（4.3）：`run_turn(session, trigger, payload)` 的三个位置参数与
`TriggerSource` 枚举冻结，防止将来加主动开口（ADR-007）时改签名；`token` 是关键字
扩展（三跳打断 3.4 需要），不进冻结面。

**上下文预算**（5.2）：预算与裁剪归本层，provider 不感知（4.4「provider 收到的
messages 永远已合预算」）。阶段 0 只有单轮，`_compose_messages` 是唯一的消息组装点，
阶段 1 的历史/记忆注入接在这里即可。
"""
from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from echoes_sidecar.core.cancel import CancelToken, StreamOutcome, TurnCancelled, aclose, pull
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.db import Storage
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.ipc import AssistantTextMsg, ErrorMsg, StateMsg, Timings, TurnCompleteMsg
from echoes_sidecar.orchestration.text_clean import clean_for_tts
from echoes_sidecar.session.manager import SessionManager
from echoes_sidecar.session.session import Session
from echoes_sidecar.transport.base import AudioEgress, Transport

# 未克隆绑定时的内置音色（2.5 none 态的解析目标；编排层解析，引擎不做状态判断）
BUILTIN_VOICE_ID = "builtin:default"
# 5.2 上下文预算（字符口径的近似）：阶段 0 只有「人设 + 本轮输入」两张，远未触顶；
# 阶段 1 注入记忆与历史后，本常量是裁剪的判据（先丢最旧的历史，永不裁本轮输入）。
MAX_CONTEXT_CHARS = 12_000

TurnStatus = Literal["SUCCESS", "CANCELLED", "FAILED"]


class TriggerSource(Enum):
    """turn 触发源（4.3 冻结枚举）：远程大脑预留（8.1）。"""

    USER_INPUT = "user_input"
    TIMER = "timer"  # 阶段 0 不实现（4.3 原文）
    IDLE_DETECTED = "idle_detected"  # 阶段 0 不实现
    EXTERNAL_EVENT = "external_event"  # 阶段 0 不实现


@dataclass(frozen=True)
class TurnDeps:
    """一次 turn 需要的外部件（组合根构造；编排层只认 ABC/Protocol —— 3.2）。"""

    transport: Transport
    llm: LLMProvider
    tts: TTSEngine
    t0: float  # sidecar 单调时钟原点（3.4 观测字段 t）
    egress: AudioEgress | None = None  # 无壳连接（--ws off）时为 None，音频丢弃
    storage: Storage | None = None  # 会话落库；单测直调可省


@dataclass(frozen=True)
class TurnOutcome:
    """turn 收尾快照（13.4 自动测量与验收断言的取值面）。"""

    status: TurnStatus
    turn_seq: int
    timings: Timings

    @property
    def cancelled(self) -> bool:
        return self.status == "CANCELLED"


@dataclass
class _Progress:
    """turn 内部观测累加器（timings 的三个字段都是"首次发生"语义）。"""

    llm_first_token_ms: int | None = None
    tts_first_audio_ms: int | None = None
    pieces: list[str] = field(default_factory=list)


class TurnGraph:
    """三节点编排：本层是 turn 顺序的唯一实现（main.py 不再持有流程）。"""

    def __init__(
        self,
        deps: TurnDeps,
        machine: StateMachine,
        *,
        manager: SessionManager | None = None,
    ) -> None:
        self._deps = deps
        self._machine = machine
        self._manager = manager

    @property
    def machine(self) -> StateMachine:
        """状态机归 sidecar 所有（3.5）；组合根持有同一个实例以便其他入口共用。"""
        return self._machine

    async def run_turn(
        self,
        session: Session,
        trigger: TriggerSource,
        payload: dict[str, Any],
        *,
        token: CancelToken | None = None,
    ) -> TurnOutcome:
        """跑一次 turn（4.3 冻结签名 + 关键字 token）。

        收尾的不变式（三跳 3.4 与 3.5 共同要求）：一次 turn 恒有且只有一条
        `turn_complete`，状态机恒回 `ready`——异常路径也不允许把 UI 锁在 generating。
        """
        if trigger is not TriggerSource.USER_INPUT:
            raise NotImplementedError(f"{trigger.value} 为非阶段 0 触发源（4.3：防主动开口改签名）")
        text = _require_text(payload)
        if self._manager is None:
            return await self._execute(session, text, token)
        # 4.6 串行化守卫：正常路径下 TurnRunner 已保证单在途，这里是不变式断言
        with self._manager.serialize_turn(session.session_id):
            return await self._execute(session, text, token)

    async def _execute(
        self, session: Session, text: str, token: CancelToken | None
    ) -> TurnOutcome:
        token = token if token is not None else CancelToken()
        status: TurnStatus = "SUCCESS"
        progress = _Progress()
        timings = Timings(total_ms=0)

        self._machine.transition(AppState.GENERATING)
        await self._emit_state(session)

        try:
            messages = self._compose_messages(session, text)
            reply = await self._generate(session, messages, progress, token)
            self._machine.transition(AppState.SPEAKING)
            await self._emit_state(session)
            await self._speak(session, reply, progress, token)
        except TurnCancelled:
            # 三跳收尾：不再产出音频（在途 chunk 丢弃），壳侧播放在首跳已清空
            status = "CANCELLED"
            print("[sidecar] turn 被三跳打断，按 CANCELLED 收尾", file=sys.stderr)
        except EchoesError as exc:
            # 引擎错误不静默不降级（3.4.1）：turn FAILED 收束，状态机照常回 ready
            status = "FAILED"
            print(
                f"[sidecar] turn 失败（{exc.code}），按 FAILED 收尾: {exc.message}",
                file=sys.stderr,
            )
            await self._emit_error(session, exc)
        finally:
            await token.close()
            if status == "SUCCESS" and token.cancelled:
                status = "CANCELLED"  # 收尾瞬间才置位：最后一个检查点没赶上，语义仍算打断
            session.turn_seq += 1
            timings = Timings(
                total_ms=self._now_ms(),
                llm_first_token_ms=progress.llm_first_token_ms,
                tts_first_audio_ms=progress.tts_first_audio_ms,
            )
            await self._deps.transport.send(
                TurnCompleteMsg(
                    session_id=session.session_id,
                    turn_seq=session.turn_seq,
                    status=status,
                    timings=timings,
                ).model_dump(mode="json")
            )
            if self._machine.state is not AppState.READY:
                self._machine.transition(AppState.READY)
                await self._emit_state(session)
            await self._persist_session(session)

        return TurnOutcome(status=status, turn_seq=session.turn_seq, timings=timings)

    # ------------------------------ 三节点 ------------------------------

    def _compose_messages(self, session: Session, user_text: str) -> list[dict[str, str]]:
        """节点 1：提示组装（5.2 预算/裁剪的唯一执行点）。

        阶段 0 只有「人设 + 本轮输入」；阶段 1 的 retrieve 结果（记忆/摘要）插在
        system 与 user 之间，裁剪按 `MAX_CONTEXT_CHARS` 先丢最旧的历史——
        **永不裁本轮输入**（用户刚说的话是不可替换的）。
        """
        messages = [
            {"role": "system", "content": session.persona.system_prompt},
            {"role": "user", "content": user_text},
        ]
        self._fit_budget(messages)
        return messages

    def _fit_budget(self, messages: list[dict[str, str]]) -> None:
        """预算守卫（5.2）：超限时从"最旧的可丢消息"开始裁，至少保留首尾两条。"""
        total = sum(len(m["content"]) for m in messages)
        while total > MAX_CONTEXT_CHARS and len(messages) > 2:
            dropped = messages.pop(1)
            total -= len(dropped["content"])
            print(
                f"[sidecar] 上下文超预算 {MAX_CONTEXT_CHARS} 字，已丢弃一条历史（5.2）",
                file=sys.stderr,
            )

    async def _generate(
        self,
        session: Session,
        messages: list[dict[str, str]],
        progress: _Progress,
        token: CancelToken,
    ) -> str:
        """节点 2：流式生成（回复文本逐片回传，v1.4.1 全量语义）。"""
        stream: AsyncIterator[str] = self._deps.llm.generate(messages)
        try:
            while True:
                outcome, piece = await pull(stream, token)
                if outcome is StreamOutcome.END:
                    break
                if outcome is StreamOutcome.CANCELLED:
                    raise TurnCancelled
                if progress.llm_first_token_ms is None:
                    progress.llm_first_token_ms = self._now_ms()
                progress.pieces.append(piece or "")
                await self._deps.transport.send(
                    AssistantTextMsg(
                        session_id=session.session_id,
                        text="".join(progress.pieces),
                        t=self._now_ms(),
                    ).model_dump(mode="json")
                )
        finally:
            await aclose(stream)
        return "".join(progress.pieces)

    async def _speak(
        self,
        session: Session,
        reply: str,
        progress: _Progress,
        token: CancelToken,
    ) -> None:
        """节点 3：逐句出声（分句归引擎，编排层只消费 chunk 流 —— 4.5）。"""
        voice_id = session.voice_id or BUILTIN_VOICE_ID
        speakable = clean_for_tts(reply)  # 5.2：音频吃清洗后文本；assistant_text 帧保持原样
        stream = self._deps.tts.synthesize(speakable, voice_id)
        try:
            while True:
                outcome, chunk = await pull(stream, token)
                if outcome is StreamOutcome.END:
                    break
                if outcome is StreamOutcome.CANCELLED:
                    raise TurnCancelled
                if chunk is None:
                    continue
                if progress.tts_first_audio_ms is None:
                    progress.tts_first_audio_ms = self._now_ms()
                await self._send_audio(chunk)
        finally:
            await aclose(stream)

    # ------------------------------ 观测与收尾 ------------------------------

    def _now_ms(self) -> int:
        """3.4 观测字段 t：sidecar 单调时钟 ms（自组合根的 t0 起算）。"""
        return int((time.perf_counter() - self._deps.t0) * 1000)

    async def _send_audio(self, chunk: AudioChunk) -> None:
        """音频出壳（3.4 WS 0x02 帧）；无连接时静默丢弃（send_audio 既有语义）。"""
        egress = self._deps.egress
        if egress is not None:
            await egress.send_audio(chunk)

    async def _emit_state(self, session: Session) -> None:
        await self._deps.transport.send(
            StateMsg(
                state=self._machine.state.value,
                session_id=session.session_id,
                t=self._now_ms(),
            ).model_dump(mode="json")
        )

    async def _emit_error(self, session: Session, exc: EchoesError) -> None:
        await self._deps.transport.send(
            ErrorMsg(
                session_id=session.session_id,
                code=exc.code,
                message=exc.message,
                fatal=exc.fatal,
                t=self._now_ms(),
            ).model_dump(mode="json")
        )

    async def _persist_session(self, session: Session) -> None:
        """turn 收尾落库（5.1：轮次明细不落库，只更新活跃时间与音色绑定）。

        写盘进线程（3.2 事件循环只做调度）；失败记 stderr 但不打断 turn——
        14.1「磁盘满：停止写入、保常态」，同时保留可观测性。
        """
        storage = self._deps.storage
        if storage is None:
            return

        def _write() -> None:
            storage.sessions.touch(session.session_id, now=time.time())
            if session.voice_id is not None:
                storage.sessions.bind_voice(session.session_id, session.voice_id)

        try:
            await asyncio.to_thread(_write)
        except EchoesError as exc:
            print(f"[sidecar] 会话落库失败（turn 不受影响）: {exc}", file=sys.stderr)


def _require_text(payload: dict[str, Any]) -> str:
    """payload 取本轮输入文本（3.4：user_text / asr_final 同构，只带 text）。"""
    raw = payload.get("text")
    if not isinstance(raw, str) or not raw.strip():
        raise EchoesError(ErrorCode.INTERNAL_ERROR, f"turn payload 缺有效 text：{raw!r}")
    return raw


__all__ = [
    "BUILTIN_VOICE_ID",
    "MAX_CONTEXT_CHARS",
    "TriggerSource",
    "TurnDeps",
    "TurnGraph",
    "TurnOutcome",
    "TurnStatus",
]
