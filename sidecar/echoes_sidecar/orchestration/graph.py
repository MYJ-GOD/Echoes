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
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Literal

from echoes_sidecar.core.cancel import CancelToken, StreamOutcome, TurnCancelled, aclose, pull
from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.core.state_machine import AppState, StateMachine
from echoes_sidecar.core.types import AudioChunk
from echoes_sidecar.db import Storage
from echoes_sidecar.engines.llm.base import LLMProvider, RuntimeConfigurable
from echoes_sidecar.engines.tts.base import TTSEngine, TtsRuntimeConfigurable
from echoes_sidecar.ipc import AssistantTextMsg, ErrorMsg, StateMsg, Timings, TurnCompleteMsg
from echoes_sidecar.memory.extractor import MemoryExtractor
from echoes_sidecar.memory.grounding import GroundingJudge
from echoes_sidecar.memory.index import TurnIndexer
from echoes_sidecar.memory.recall import MemoryRecall, RecallResult
from echoes_sidecar.memory.rewrite import QueryRewriter
from echoes_sidecar.memory.store import MemoryStore
from echoes_sidecar.orchestration.emotion import (
    Emotion,
)
from echoes_sidecar.orchestration.emotion import (
    detect as detect_emotion,
)
from echoes_sidecar.orchestration.emotion import (
    instruction_for as emotion_instruction,
)
from echoes_sidecar.orchestration.emotion import (
    label as emotion_label,
)
from echoes_sidecar.orchestration.intent import Intent, classify
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

# ---- R3a 4.3 分层注入预算（字符近似：≈1 token / 1.5 汉字）----
# 真正的 per-model tokenizer / context_window 元数据归 R3b；这里先把「事实 ≤300
# token、摘要 ≤400 token、原文占大头」的比例固化下来，预算按字符执行。
FACT_BUDGET_CHARS = 450
SUMMARY_BUDGET_CHARS = 600
TURN_HINT_BUDGET_CHARS = 600
# 「我们上周在聊什么」：摘要检索的时间窗（14 天，覆盖「上周」的模糊说法）
SUMMARY_RECENT_SECONDS = 14 * 86_400

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
    # R3a 3.3：三路检索（事实/原文/摘要）；None 时退回 `memory.retrieve` 单路
    recall: MemoryRecall | None = None
    # R3a 3.2：条件式查询改写；None 时用原句检索
    rewriter: QueryRewriter | None = None
    # R3b 3.3b：turn 完成后切块 + 嵌入（异步；None 时原文只有 FTS 一路）
    indexer: TurnIndexer | None = None
    # R4 4.3：turn 完成后异步质检（None / 不可用时 turn 的 grounding_* 保持 NULL）
    grounding: GroundingJudge | None = None
    # R2a 2.5：引擎热切换后重发 hello（active_* 回报）；单测/无壳时省略
    hello_sender: Callable[[], Awaitable[None]] | None = None


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


@dataclass(frozen=True)
class _Composed:
    """提示组装结果：消息 + 本轮注入的事实 id（R3a 3.8）+ 证据文本（R4 4.3）。"""

    messages: list[dict[str, str]]
    fact_ids: list[str]
    evidence: tuple[str, ...] = ()
    emotion: Emotion = Emotion.NEUTRAL


@dataclass(frozen=True)
class _IntentPolicy:
    """R4 4.2 意图 → 检索策略（只影响注入量，不改三路检索本身）。"""

    fact_prompt_k: int = 5
    turn_prompt_k: int = 3
    summary_prompt_k: int = 2
    force_rewrite: bool = False
    emotional_hint: bool = False


_POLICIES: dict[Intent, _IntentPolicy] = {
    Intent.CHAT: _IntentPolicy(),
    # 先接住情绪：事实按需，不带原文/摘要，避免拿旧账说教
    Intent.EMOTIONAL_SUPPORT: _IntentPolicy(3, 0, 0, emotional_hint=True),
    # 明确回溯：放宽注入量，且强制改写（「那本后来怎么样了」指代不明显）
    Intent.MEMORY_RECALL: _IntentPolicy(8, 10, 3, force_rewrite=True),
    # 「我是谁」：汇总型问题，事实给满；原文/摘要此时是噪音
    Intent.PROFILE_QUERY: _IntentPolicy(10, 0, 0, force_rewrite=True),
    # v1 只分类不接工具：按普通检索处理，保留最小事实量
    Intent.TASK: _IntentPolicy(3, 0, 0),
}

_EMOTIONAL_HINT = (
    "用户此刻情绪不好：先用一两句接住情绪，再给具体、可执行的建议；"
    "不要罗列记忆条目，也不要说教。"
)


def _policy_for(intent: Intent) -> _IntentPolicy:
    return _POLICIES[intent]


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
        # R5 §2.7：连续历史写失败计数（成功一次即清零；≥3 只读由 UI 兜底）
        self._history_failures = 0
        # 5.2 抽取是「turn 结束后」的后台活：任务句柄必须自持，否则可能被 GC。
        self._memory_tasks: set[asyncio.Task[None]] = set()
        # R3b 3.3b 原文索引：同一类后台活，失败只记日志。
        self._index_tasks: set[asyncio.Task[None]] = set()
        # R4 4.3 Grounding 质检：turn 收尾后异步，结果写 turn.grounding_*。
        self._grounding_tasks: set[asyncio.Task[None]] = set()
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
        supersede: str | None = None,
    ) -> TurnOutcome:
        """跑一次 turn（4.3 冻结签名 + 关键字 token）。

        `supersede` = 重说/编辑的旧 turn id（R4 4.4/4.5）：本轮成功后由编排层
        把旧 turn 标记为被取代；失败/打断则不动，旧内容继续可见。

        收尾的不变式（三跳 3.4 与 3.5 共同要求）：一次 turn 恒有且只有一条
        `turn_complete`，状态机恒回 `ready`——异常路径也不允许把 UI 锁在 generating。
        """
        if trigger is not TriggerSource.USER_INPUT:
            raise NotImplementedError(f"{trigger.value} 为非阶段 0 触发源（4.3：防主动开口改签名）")
        text = _require_text(payload)
        if self._manager is None:
            return await self._execute(session, text, token, supersede=supersede)
        # 4.6 串行化守卫：正常路径下 TurnRunner 已保证单在途，这里是不变式断言
        with self._manager.serialize_turn(session.session_id):
            return await self._execute(session, text, token, supersede=supersede)

    async def _execute(
        self,
        session: Session,
        text: str,
        token: CancelToken | None,
        *,
        supersede: str | None = None,
    ) -> TurnOutcome:
        token = token if token is not None else CancelToken()
        status: TurnStatus = "SUCCESS"
        progress = _Progress()
        timings = Timings(total_ms=0)
        reply = ""
        turn_id: str | None = None
        fail_reason: str | None = None
        evidence: tuple[str, ...] = ()
        emotion = Emotion.NEUTRAL

        self._machine.transition(AppState.GENERATING)
        await self._emit_state(session)

        try:
            await self._apply_runtime_settings(session)
            turn_id = await self._begin_turn(session, text)
            composed = await self._compose_turn(session, text)
            evidence = composed.evidence
            emotion = composed.emotion
            if turn_id is not None and composed.fact_ids:
                await self._link_memory(turn_id, composed.fact_ids)
            reply = await self._generate(session, composed.messages, progress, token)
            self._machine.transition(AppState.SPEAKING)
            await self._emit_state(session)
            await self._speak(session, reply, progress, token, emotion)
        except TurnCancelled:
            # 三跳收尾：不再产出音频（在途 chunk 丢弃），壳侧播放在首跳已清空
            status = "CANCELLED"
            print("[sidecar] turn 被三跳打断，按 CANCELLED 收尾", file=sys.stderr)
        except EchoesError as exc:
            # 引擎错误不静默不降级（3.4.1）：turn FAILED 收束，状态机照常回 ready
            status = "FAILED"
            fail_reason = exc.code.value
            print(
                f"[sidecar] turn 失败（{exc.code}），按 FAILED 收尾: {exc.message}",
                file=sys.stderr,
            )
            await self._emit_error(session, exc)
        finally:
            await token.close()
            if status == "SUCCESS" and token.cancelled:
                status = "CANCELLED"  # 收尾瞬间才置位：最后一个检查点没赶上，语义仍算打断
            if turn_id is None:
                # 无 storage（单测）或原文写入失败：保持旧的内存序号行为
                session.turn_seq += 1
            timings = Timings(
                total_ms=self._now_ms(),
                llm_first_token_ms=progress.llm_first_token_ms,
                tts_first_audio_ms=progress.tts_first_audio_ms,
            )
            # 原文先落盘再发 turn_complete：UI 看到完成时 DB 必须已是终态。
            await self._finish_turn(
                turn_id,
                reply=reply,
                status=status,
                timings=timings,
                fail_reason=fail_reason,
                emotion=None if emotion is Emotion.NEUTRAL else emotion.value,
            )
            # R4 4.4/4.5：新 turn 成功收尾后才取代旧 turn；失败/打断不取代。
            if (
                status == "SUCCESS"
                and supersede
                and turn_id is not None
                and self._deps.storage is not None
            ):
                try:
                    await asyncio.to_thread(
                        self._deps.storage.turns.supersede, supersede, turn_id
                    )
                except Exception as exc:  # noqa: BLE001  旧内容仍在，只是两条都可见
                    print(
                        f"[sidecar] 重说标记失败（旧 turn 仍在历史里）: {exc}",
                        file=sys.stderr,
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
                await self._schedule_summary(session, session.turn_seq)
                self._schedule_memory(session, text, reply, session.turn_seq)
                self._schedule_index(turn_id)
                self._schedule_grounding(turn_id, reply, evidence)

        return TurnOutcome(status=status, turn_seq=session.turn_seq, timings=timings)

    async def _begin_turn(self, session: Session, text: str) -> str | None:
        """原文先落盘；失败不阻断语音，但要上报 HISTORY_WRITE_FAILED（§2.7）。"""
        storage = self._deps.storage
        if storage is None:
            return None
        try:
            record = await asyncio.to_thread(
                storage.turns.insert,
                session_id=session.session_id,
                user_text=text,
                now=time.time(),
                profile_id=session.profile_id,
                voice_id=session.voice_id,
                persona_id=session.persona.id,
            )
        except EchoesError as exc:
            self._history_failures += 1
            print(
                f"[sidecar] 原文写入失败（连续第 {self._history_failures} 次，"
                f"本轮继续、不保存）: {exc}",
                file=sys.stderr,
            )
            read_only = self._history_failures >= 3
            await self._emit_error(
                session,
                EchoesError(
                    ErrorCode.HISTORY_WRITE_FAILED,
                    f"历史写入失败（连续第 {self._history_failures} 次），本轮不会保存"
                    + ("；已进入只读模式，请确认磁盘/权限后重启 Echoes" if read_only else ""),
                ),
            )
            return None
        self._history_failures = 0
        session.turn_seq = record.seq
        try:
            await asyncio.to_thread(
                storage.sessions.set_title_if_empty, session.session_id, text
            )
        except EchoesError as exc:
            print(f"[sidecar] 会话标题写入失败（不影响 turn）: {exc}", file=sys.stderr)
        return record.turn_id

    async def _finish_turn(
        self,
        turn_id: str | None,
        *,
        reply: str,
        status: TurnStatus,
        timings: Timings,
        fail_reason: str | None,
        emotion: str | None = None,
    ) -> None:
        storage = self._deps.storage
        if storage is None or turn_id is None:
            return
        db_status = {
            "SUCCESS": "complete",
            "CANCELLED": "cancelled",
            "FAILED": "failed",
        }[status]
        try:
            await asyncio.to_thread(
                storage.turns.finish,
                turn_id,
                assistant_text=reply or None,
                status=db_status,
                now=time.time(),
                latency_ms=timings.total_ms,
                fail_reason=fail_reason if status == "FAILED" else None,
                emotion=emotion,
            )
        except EchoesError as exc:
            print(f"[sidecar] turn 收尾落库失败（保持 pending 待启动清洗）: {exc}", file=sys.stderr)

    # ------------------------------ 三节点 ------------------------------

    async def _compose_messages(self, session: Session, user_text: str) -> list[dict[str, str]]:
        """节点 1：提示组装（兼容入口；`_execute` 用 `_compose_turn` 拿来源 id）。"""
        return (await self._compose_turn(session, user_text)).messages

    async def _compose_turn(self, session: Session, user_text: str) -> _Composed:
        """节点 1：三层注入 + 预算裁剪（R3a 3.1/3.3）。

        system = 人设 + 长期事实（≤450 字）+ 中期摘要（≤600 字）+ 原文命中，
        短期历史按剩余预算从最新往回填。记忆是增强项：检索失败只记 stderr，
        本轮照常无记忆回答——错误记忆比没有记忆更毒，但「检索坏了就聊不了」
        同样不可接受。
        """
        system = session.persona.system_prompt
        fact_ids: list[str] = []
        evidence: tuple[str, ...] = ()
        emotion = detect_emotion(user_text)
        intent = classify(user_text)
        policy = _policy_for(intent)
        if intent is not Intent.CHAT:
            print(f"[sidecar] 意图：{intent.value}", file=sys.stderr)
        history = await self._recent_history(session)
        recall = self._deps.recall
        if recall is not None:
            query = user_text
            rewriter = self._deps.rewriter
            if rewriter is not None:
                try:
                    query = await rewriter.rewrite(
                        user_text, history, force=policy.force_rewrite
                    )
                except Exception as exc:  # noqa: BLE001  改写失败用原句
                    print(
                        f"[sidecar] 查询改写失败（用原句检索）: {exc}",
                        file=sys.stderr,
                    )
            try:
                result = await recall.recall(
                    profile_id=session.profile_id,
                    query=query,
                    since=time.time() - SUMMARY_RECENT_SECONDS,
                )
            except Exception as exc:  # noqa: BLE001  三路全失败也只是一轮无记忆
                print(f"[sidecar] 记忆检索失败（本轮无记忆）: {exc}", file=sys.stderr)
                result = RecallResult()
            system, fact_ids, evidence = self._system_after_recall(
                session, result, policy
            )
        else:
            system = await self._inject_legacy_memory(session, system, user_text)
        if policy.emotional_hint:
            system = (
                f"{system}\n\n用户此刻情绪：{emotion_label(emotion)}。"
                f"{_EMOTIONAL_HINT}"
            )

        summary = self._current_summary(session)
        if summary:
            system = f"{system}\n\n此前对话摘要：\n{summary}"

        selected = self._fit_history(history, system, user_text)
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for turn in selected:
            messages.append({"role": "user", "content": turn.user})
            messages.append({"role": "assistant", "content": turn.assistant})
        messages.append({"role": "user", "content": user_text})
        self._fit_budget(messages)
        return _Composed(
            messages=messages,
            fact_ids=fact_ids,
            evidence=evidence,
            emotion=emotion,
        )

    def _system_after_recall(
        self, session: Session, result: RecallResult, policy: _IntentPolicy
    ) -> tuple[str, list[str], tuple[str, ...]]:
        """按预算拼接三层：事实 → 其他会话摘要 → 原文片段。

        `policy` 决定每层注入多少（R4 4.2）：情绪/任务意图把原文与摘要压到 0，
        明确回溯意图放宽原文；返回的 fact_ids / evidence 只包含**真正进了
        prompt 的事实**（预算截断后），来源回溯与 Grounding 才不会把「检索到
        但没注入」的账算到本轮头上。
        """
        system = session.persona.system_prompt
        fact_ids: list[str] = []
        evidence: tuple[str, ...] = ()
        facts = result.facts[: policy.fact_prompt_k]
        if facts:
            block, used = _clip_lines([f"- {item.text}" for item in facts], FACT_BUDGET_CHARS)
            fact_ids = [item.ref_id for item in facts[:used]]
            evidence = tuple(item.text for item in facts[:used])
            if block:
                system = (
                    f"{system}\n\n关于用户的已知信息"
                    f"（只在相关时自然提起，别逐条复述）：\n{block}"
                )

        summaries = result.summaries[: policy.summary_prompt_k]
        if summaries:
            block, _ = _clip_lines(
                [f"- [{item.title}] {item.text}" for item in summaries],
                SUMMARY_BUDGET_CHARS,
            )
            if block:
                system = f"{system}\n\n其他会话的相关摘要：\n{block}"

        turns = result.turns[: policy.turn_prompt_k]
        if turns:
            block, _ = _clip_lines(
                [f"- [{item.title}] {item.text}" for item in turns],
                TURN_HINT_BUDGET_CHARS,
            )
            if block:
                system = (
                    f"{system}\n\n可能相关的历史原话"
                    f"（用于指代/回溯，不是当前轮）：\n{block}"
                )
        return system, fact_ids, evidence

    async def _inject_legacy_memory(
        self, session: Session, system: str, user_text: str
    ) -> str:
        """无三路检索时的兼容路径（单测 / memory off 的组合根）。"""
        memory = self._deps.memory
        if memory is None:
            return system
        try:
            facts = await memory.retrieve(session.profile_id, user_text, k=5)
        except Exception as exc:  # noqa: BLE001  记忆面失败不阻断对话
            print(f"[sidecar] 记忆检索失败（本轮无记忆）: {exc}", file=sys.stderr)
            return system
        hint = memory.compose_hint(facts)
        return f"{system}\n\n{hint}" if hint else system

    def _fit_history(
        self, turns: list[SummaryTurn], system: str, user_text: str
    ) -> list[SummaryTurn]:
        """短期原文预算：从最新往回填，剩余额度占大头（4.3）。

        单轮超预算也保留（宁可后半段被 `_fit_budget` 兜底裁掉，也不整轮丢）；
        没有历史时返回空表，调用方照常拼 system + 本轮输入。
        """
        remaining = MAX_CONTEXT_CHARS - len(system) - len(user_text) - 256
        if remaining <= 0:
            return turns[-1:] if turns else []
        selected: list[SummaryTurn] = []
        used = 0
        for turn in reversed(turns):
            cost = len(turn.user) + len(turn.assistant)
            if selected and used + cost > remaining:
                break
            selected.append(turn)
            used += cost
        selected.reverse()
        return selected

    async def _link_memory(self, turn_id: str, fact_ids: list[str]) -> None:
        """写 `turn_memory_ref`（R3a 3.8）；失败不影响本轮对话。"""
        storage = self._deps.storage
        if storage is None or not fact_ids:
            return
        try:
            await asyncio.to_thread(storage.turns.link_memory, turn_id, fact_ids)
        except Exception as exc:  # noqa: BLE001  来源回溯是附加账，不反噬 turn
            print(f"[sidecar] 记忆来源写入失败（不影响本轮）: {exc}", file=sys.stderr)

    async def _recent_history(self, session: Session) -> list[SummaryTurn]:
        """prompt 窗口：有 DB 时以 turn 表为准；单测无 storage 时退回内存。"""
        storage = self._deps.storage
        if storage is None:
            return list(self._history.get(session.session_id, []))
        try:
            rows = await asyncio.to_thread(
                storage.turns.recent, session.session_id, limit=MAX_HISTORY_TURNS
            )
        except EchoesError as exc:
            print(f"[sidecar] 历史读取失败（本轮无历史）: {exc}", file=sys.stderr)
            return []
        return [
            SummaryTurn(
                turn=row.seq,
                user=row.user_text,
                assistant=row.assistant_text or "",
            )
            for row in rows
        ]

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
        llm_before = getattr(router, "current", None)
        # 能力位探测（4.4 v1.4.4）：编排只认 Protocol，不认识 ProviderRouter 这个具体类
        if isinstance(router, RuntimeConfigurable):
            try:
                await router.apply(
                    provider=settings.provider,
                    model=settings.model,
                    base_url=settings.base_url,
                    allow_cloud=not settings.privacy_mode,
                )
            except Exception as exc:  # noqa: BLE001  provider 构造失败保持旧实例
                print(
                    f"[sidecar] LLM provider 切换失败（沿用旧实例）: {exc}",
                    file=sys.stderr,
                )

        # 语音链热切换（R2a 2.5）：与 LLM 同一边界——turn 开始前应用。
        # 构造失败/未知 provider 由路由器保持旧引擎；隐私模式下选中云端会在
        # synthesize 时报错（不静默回退本地）。
        tts = self._deps.tts
        tts_before = getattr(tts, "current", None)
        if isinstance(tts, TtsRuntimeConfigurable):
            try:
                await tts.apply(
                    provider=settings.tts_provider,
                    model=settings.tts_model,
                    base_url=settings.tts_base_url,
                    allow_cloud=not settings.privacy_mode,
                )
            except Exception as exc:  # noqa: BLE001  切换失败保持旧引擎
                print(
                    f"[sidecar] TTS 引擎切换失败（沿用旧引擎）: {exc}",
                    file=sys.stderr,
                )

        # 生效引擎变了就重发 hello（hello 是引擎状态的唯一载体；设置页据此
        # 区分「目标值」与「实际生效」，2.5 / 2.12）
        llm_after = getattr(router, "current", None)
        tts_after = getattr(tts, "current", None)
        if (llm_after != llm_before or tts_after != tts_before) and (
            self._deps.hello_sender is not None
        ):
            try:
                await self._deps.hello_sender()
            except Exception as exc:  # noqa: BLE001  回报失败不影响本轮对话
                print(f"[sidecar] 引擎状态回报失败: {exc}", file=sys.stderr)

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
        emotion: Emotion = Emotion.NEUTRAL,
    ) -> None:
        """节点 3：逐句出声（分句归引擎，编排层只消费 chunk 流 —— 4.5）。

        R2b 2b.6：情绪命中且引擎支持 instruct 时，先设置本轮语气指令，合成结束
        在 finally 复位——引擎是共享实例，不能把这一轮的情绪漏给下一轮。
        """
        voice_id = session.voice_id or BUILTIN_VOICE_ID
        speakable = clean_for_tts(reply)  # 5.2：音频吃清洗后文本；assistant_text 帧保持原样
        tts = self._deps.tts
        instruction = emotion_instruction(emotion) if tts.supports_instruction else None
        if tts.supports_instruction:
            tts.set_instruction(instruction)
        stream = tts.synthesize(speakable, voice_id)
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
            if tts.supports_instruction:
                tts.set_instruction(None)

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
        """turn 收尾打点（轮次原文由 TurnRepo 落 0003 turn 表；此处只更新活跃时间）。

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

    async def _schedule_summary(self, session: Session, turn_seq: int) -> None:
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

        storage = self._deps.storage
        if storage is not None:
            after_seq = 0 if state is None else state.up_to_turn
            try:
                rows = await asyncio.to_thread(
                    storage.turns.unsummarized,
                    session.session_id,
                    after_seq=after_seq,
                    limit=1000,
                )
            except EchoesError as exc:
                print(f"[sidecar] 摘要补偿读取失败（保留旧摘要）: {exc}", file=sys.stderr)
                return
            turns = [
                SummaryTurn(
                    turn=row.seq,
                    user=row.user_text,
                    assistant=row.assistant_text or "",
                )
                for row in rows
            ]
        else:
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
        """等在途抽取/原文索引/Grounding 收尾（测试 / 优雅退出用；生产不阻塞 turn）。"""
        pending = [*self._memory_tasks, *self._index_tasks, *self._grounding_tasks]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    # ------------------------------ 原文索引（R3b 3.3b） ------------------------------

    def _schedule_index(self, turn_id: str | None) -> None:
        """turn 成功后异步切块 + 嵌入；句柄自持，失败不回噬 turn。"""
        if turn_id is None or self._deps.indexer is None or self._deps.storage is None:
            return
        task = asyncio.create_task(self._index_turn(turn_id), name="echoes-index")
        self._index_tasks.add(task)
        task.add_done_callback(self._index_tasks.discard)

    async def _index_turn(self, turn_id: str) -> None:
        indexer = self._deps.indexer
        storage = self._deps.storage
        assert indexer is not None and storage is not None
        try:
            row = await asyncio.to_thread(storage.turns.get, turn_id)
            if row is not None:
                await indexer.index_turn(row)
        except Exception as exc:  # noqa: BLE001  检索增强项，失败只记日志
            print(f"[sidecar] 原文索引失败（不影响对话）: {exc}", file=sys.stderr)

    # ------------------------------ Grounding（R4 4.3） ------------------------------

    def _schedule_grounding(
        self, turn_id: str | None, reply: str, evidence: tuple[str, ...]
    ) -> None:
        """turn 成功后异步质检；没有注入记忆就不质检（无证据可比）。"""
        judge = self._deps.grounding
        if (
            turn_id is None
            or judge is None
            or not judge.available
            or not reply
            or not evidence
            or self._deps.storage is None
        ):
            return
        task = asyncio.create_task(
            self._ground(turn_id, reply, evidence), name="echoes-grounding"
        )
        self._grounding_tasks.add(task)
        task.add_done_callback(self._grounding_tasks.discard)

    async def _ground(
        self, turn_id: str, reply: str, evidence: tuple[str, ...]
    ) -> None:
        judge = self._deps.grounding
        storage = self._deps.storage
        assert judge is not None and storage is not None
        try:
            result = await judge.check(reply, evidence)
            await asyncio.to_thread(
                storage.turns.set_grounding,
                turn_id,
                score=result.score,
                verdict="faithful" if result.faithful else "unfaithful",
                claims=list(result.unsupported),
                now=time.time(),
            )
        except Exception as exc:  # noqa: BLE001  质检是观测项，失败只记日志
            print(f"[sidecar] Grounding 质检失败（不影响对话）: {exc}", file=sys.stderr)


def _clip_lines(lines: list[str], budget: int) -> tuple[str, int]:
    """按字符预算逐行装入；首行就超预算时截断（保证总长不破预算）。

    返回 (文本, 装入行数)——行数用于「来源回溯只记真正注入的条目」。
    """
    selected: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + 1
        if not selected and cost > budget:
            selected.append(line[: max(0, budget - 1)] + "…")
            break
        if selected and used + cost > budget:
            break
        selected.append(line)
        used += cost
    return "\n".join(selected), len(selected)


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
