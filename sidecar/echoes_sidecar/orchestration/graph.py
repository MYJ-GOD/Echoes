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
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Literal

from echoes_sidecar.core.cancel import CancelToken, StreamOutcome, TurnCancelled, aclose, pull
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.db import Storage
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.llm.router import ProviderRouter
from echoes_sidecar.engines.tts.base import TTSEngine
from echoes_sidecar.ipc import AssistantTextMsg, ErrorMsg, StateMsg, Timings, TurnCompleteMsg
from echoes_sidecar.memory.extractor import MemoryExtractor
from echoes_sidecar.memory.store import MemoryStore
from echoes_sidecar.orchestration.text_clean import clean_for_tts
from echoes_sidecar.session.manager import SessionManager
from echoes_sidecar.session.runtime import RuntimeSettings
from echoes_sidecar.session.session import Session
from echoes_sidecar.session.summary import SessionSummarizer, SummaryState, SummaryTurn
from echoes_sidecar.transport.base import AudioEgress, Transport

# 未克隆绑定时的内置音色（2.5 none 态的解析目标；编排层解析，引擎不做状态判断）
BUILTIN_VOICE_ID = "builtin:default"
# 5.2 上下文预算（字符口径的近似）：阶段 0 只有「人设 + 本轮输入」两张，远未触顶；
# 阶段 1 注入记忆与历史后，本常量是裁剪的判据（先丢最旧的历史，永不裁本轮输入）。
MAX_CONTEXT_CHARS = 12_000
# 5.2「会话内最近 N 轮」：12 轮（24 条消息）足够覆盖摘要间隔，再长的历史归摘要。
MAX_HISTORY_TURNS = 12

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
    memory: MemoryStore | None = None  # 5.2：turn 前检索相关事实
    extractor: MemoryExtractor | None = None  # 5.2：turn 后异步抽取
    summarizer: SessionSummarizer | None = None  # 5.2：每 10 轮/30 分钟的滚动摘要
    settings_loader: Callable[[], RuntimeSettings] | None = None  # 3.4：每 turn 拉取


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
        # 5.2 抽取是「turn 结束后」的后台活：任务句柄必须自持，否则可能被 GC。
        self._memory_tasks: set[asyncio.Task[None]] = set()
        # 5.2 滚动摘要：最近 N 轮 + 摘要状态都留在内存，重启只恢复摘要与事实。
        self._summary_tasks: set[asyncio.Task[None]] = set()
        self._history: dict[str, list[SummaryTurn]] = {}
        self._summaries: dict[str, SummaryState | None] = {}

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
        reply = ""

        self._machine.transition(AppState.GENERATING)
        await self._emit_state(session)

        try:
            await self._apply_runtime_settings(session)
            messages = await self._compose_messages(session, text)
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
            # 5.2：抽取/摘要都在 turn 收尾之后异步跑，不占本轮延迟、失败不回噬 turn。
            if status == "SUCCESS" and reply:
                self._append_history(session, text, reply, session.turn_seq)
                self._schedule_summary(session, session.turn_seq)
                self._schedule_memory(session, text, reply, session.turn_seq)

        return TurnOutcome(status=status, turn_seq=session.turn_seq, timings=timings)

    # ------------------------------ 三节点 ------------------------------

    async def _compose_messages(self, session: Session, user_text: str) -> list[dict[str, str]]:
        """节点 1：提示组装（5.2 预算/裁剪的唯一执行点）。

        system = 人设 + 检索到的 fact（5.2：记忆拼进 system，不跟在 user 后面）。
        记忆是增强项：检索失败只记 stderr，本轮照常无记忆回答——错误记忆比没有
        记忆更毒，但「检索坏了就聊不了」同样不可接受。
        """
        system = session.persona.system_prompt
        memory = self._deps.memory
        if memory is not None:
            try:
                facts = await memory.retrieve(session.profile_id, user_text, k=5)
            except Exception as exc:  # noqa: BLE001  记忆面失败不阻断对话
                print(f"[sidecar] 记忆检索失败（本轮无记忆）: {exc}", file=sys.stderr)
            else:
                hint = memory.compose_hint(facts)
                if hint:
                    system = f"{system}\n\n{hint}"

        summary = self._current_summary(session)
        if summary:
            system = f"{system}\n\n此前对话摘要：\n{summary}"

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for turn in self._history.get(session.session_id, []):
            messages.append({"role": "user", "content": turn.user})
            messages.append({"role": "assistant", "content": turn.assistant})
        messages.append({"role": "user", "content": user_text})
        self._fit_budget(messages)
        return messages

    async def _apply_runtime_settings(self, session: Session) -> None:
        """3.4 拉取语义：每 turn 开始前应用 provider/model 与人设覆盖。"""
        loader = self._deps.settings_loader
        if loader is None:
            return
        try:
            settings = loader()
        except Exception as exc:  # noqa: BLE001  设置读取失败不阻断对话
            print(f"[sidecar] 运行期设置读取失败（沿用当前值）: {exc}", file=sys.stderr)
            return

        router = self._deps.llm
        if isinstance(router, ProviderRouter):
            try:
                await router.apply(provider=settings.provider, model=settings.model)
            except Exception as exc:  # noqa: BLE001  provider 构造失败保持旧实例
                print(
                    f"[sidecar] LLM provider 切换失败（沿用旧实例）: {exc}",
                    file=sys.stderr,
                )

        if settings.persona_name and settings.persona_system_prompt:
            session.persona = replace(
                session.persona,
                name=settings.persona_name,
                system_prompt=settings.persona_system_prompt,
                updated_at=time.time(),
            )

        # 音色槽位（ADR-008）：壳写 session.voice_id，sidecar 每轮拉取；
        # 不在 turn 收尾回写，避免覆盖用户在轮间切换的选择。
        storage = self._deps.storage
        if storage is not None:
            row = storage.sessions.get(session.session_id)
            if row is not None:
                session.voice_id = row.voice_id

    def _current_summary(self, session: Session) -> str:
        """取当前摘要（首轮从 DB 懒加载；读失败按无摘要处理）。"""
        summarizer = self._deps.summarizer
        if summarizer is None:
            return ""
        if session.session_id not in self._summaries:
            try:
                self._summaries[session.session_id] = summarizer.load(session.session_id)
            except Exception as exc:  # noqa: BLE001  摘要读失败不阻断对话
                print(f"[sidecar] 会话摘要读取失败（本轮无摘要）: {exc}", file=sys.stderr)
                self._summaries[session.session_id] = None
        state = self._summaries[session.session_id]
        return "" if state is None else state.text

    def _fit_budget(self, messages: list[dict[str, str]]) -> None:
        """预算守卫（5.2）：超限时先丢最旧的一轮历史（user+assistant 成对），
        系统消息与本轮输入永不裁剪。"""
        total = sum(len(m["content"]) for m in messages)
        while total > MAX_CONTEXT_CHARS and len(messages) > 2:
            dropped = messages.pop(1)
            total -= len(dropped["content"])
            if (
                dropped["role"] == "user"
                and len(messages) > 2
                and messages[1]["role"] == "assistant"
            ):
                partner = messages.pop(1)
                total -= len(partner["content"])
            print(
                f"[sidecar] 上下文超预算 {MAX_CONTEXT_CHARS} 字，已丢弃最旧一轮历史（5.2）",
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
                # 首音频以「有样本的帧」为准：零长度 is_final 只是流尾锚点，
                # 拿它当首音频会把 TTFA 记成 0（ADR-012 §2 口径）。
                if progress.tts_first_audio_ms is None and chunk.data:
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

        try:
            await asyncio.to_thread(_write)
        except EchoesError as exc:
            print(f"[sidecar] 会话落库失败（turn 不受影响）: {exc}", file=sys.stderr)

    # ------------------------------ 会话摘要（5.2） ------------------------------

    def _append_history(
        self, session: Session, user_text: str, reply: str, turn_seq: int
    ) -> None:
        """只保留最近 N 轮；更早的上下文由滚动摘要覆盖。"""
        turns = self._history.setdefault(session.session_id, [])
        turns.append(SummaryTurn(turn=turn_seq, user=user_text, assistant=reply))
        if len(turns) > MAX_HISTORY_TURNS:
            del turns[:-MAX_HISTORY_TURNS]

    def _schedule_summary(self, session: Session, turn_seq: int) -> None:
        """10 轮/30 分钟到点才起任务；句柄自持，失败只记日志。"""
        summarizer = self._deps.summarizer
        if summarizer is None:
            return
        if session.session_id not in self._summaries:
            try:
                self._summaries[session.session_id] = summarizer.load(session.session_id)
            except Exception as exc:  # noqa: BLE001  摘要读失败不阻断 turn
                print(f"[sidecar] 会话摘要读取失败: {exc}", file=sys.stderr)
                self._summaries[session.session_id] = None
        state = self._summaries[session.session_id]
        now = time.time()
        if not summarizer.should_update(state, turn_seq=turn_seq, now=now):
            return
        turns = list(self._history.get(session.session_id, []))
        task = asyncio.create_task(
            self._summarize(session, turns, turn_seq, now), name="echoes-summary"
        )
        self._summary_tasks.add(task)
        task.add_done_callback(self._summary_tasks.discard)

    async def _summarize(
        self, session: Session, turns: list[SummaryTurn], turn_seq: int, now: float
    ) -> None:
        summarizer = self._deps.summarizer
        assert summarizer is not None
        try:
            state = await summarizer.update(
                session.session_id, turns, turn_seq=turn_seq, now=now
            )
        except Exception as exc:  # noqa: BLE001  摘要失败保留旧摘要
            print(f"[sidecar] 会话摘要失败（保留旧摘要）: {exc}", file=sys.stderr)
            return
        if state is not None:
            self._summaries[session.session_id] = state

    async def wait_summary_idle(self) -> None:
        """等在途摘要收尾（测试 / 优雅退出用；生产不阻塞 turn）。"""
        if self._summary_tasks:
            await asyncio.gather(*list(self._summary_tasks), return_exceptions=True)

    # ------------------------------ 记忆（5.2） ------------------------------

    def _schedule_memory(
        self, session: Session, user_text: str, reply: str, turn_seq: int
    ) -> None:
        """turn 成功后起后台抽取任务；句柄自持，避免被 GC 静默取消。"""
        if self._deps.extractor is None:
            return
        transcript = f"用户：{user_text}\n助手：{reply}"
        task = asyncio.create_task(
            self._remember(session, transcript, turn_seq), name="echoes-memory"
        )
        self._memory_tasks.add(task)
        task.add_done_callback(self._memory_tasks.discard)

    async def _remember(self, session: Session, transcript: str, turn_seq: int) -> None:
        """抽取失败只记日志：记忆是增强项，不能回噬已成功的 turn。"""
        extractor = self._deps.extractor
        assert extractor is not None
        try:
            await extractor.ingest(
                session.profile_id,
                transcript,
                source_session_id=session.session_id,
                source_turn=turn_seq,
            )
        except Exception as exc:  # noqa: BLE001  最后一道防线（同 TurnRunner）
            print(f"[sidecar] 记忆抽取失败（不影响对话）: {exc}", file=sys.stderr)

    async def wait_memory_idle(self) -> None:
        """等在途抽取收尾（测试 / 优雅退出用；生产不阻塞 turn）。"""
        if self._memory_tasks:
            await asyncio.gather(*list(self._memory_tasks), return_exceptions=True)


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
