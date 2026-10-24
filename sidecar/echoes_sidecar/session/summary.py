"""会话滚动摘要（5.2）：每 10 轮或 30 分钟更新 `session_summary`。

**为什么要摘要**：prompt 只放最近 N 轮 + 一份滚动摘要，不能把整段历史一直塞进去。
摘要归会话层（不是事实记忆）：事实是「关于用户的稳定信息」，摘要是「这段对话聊过
什么」；两者在 prompt 里并列，但存储与更新节奏不同。

**执行约束**：LLM 调用是异步的，落库走 `asyncio.to_thread`（3.2）；摘要失败只记
stderr，保留旧摘要，绝不把 `session_summary` 清空或写半截（14.2）。
"""
from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db.repo import SessionRepo

DEFAULT_INTERVAL_TURNS = 10
DEFAULT_INTERVAL_SECONDS = 30 * 60
MAX_SUMMARY_CHARS = 600

_SYSTEM_PROMPT = (
    "你是 Echoes 的会话摘要器。把「已有摘要」和「新增对话」合并成不超过 300 字的"
    "第三人称摘要。\n"
    "只保留稳定的偏好、身份/关系、计划/事件、未完成事项；不逐句复述、不编造，\n"
    "不记录密码/证件/银行卡/精确住址等敏感信息。只输出摘要正文，不要标题或解释。"
)


class SummaryLLM(Protocol):
    """摘要只需要「messages → 文本片流」；不依赖 engines 层 ABC（15.2）。"""

    @property
    def name(self) -> str: ...

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]: ...


@dataclass(frozen=True)
class SummaryTurn:
    """一轮已完成的对话（只喂摘要器，不落库）。"""

    turn: int
    user: str
    assistant: str


@dataclass(frozen=True)
class SummaryState:
    """当前摘要快照（内存态；落库由 SessionRepo 负责）。"""

    text: str
    up_to_turn: int
    updated_at: float


class SessionSummarizer:
    """滚动摘要服务的唯一实现：何时更新归编排层，怎么摘要归本模块。"""

    def __init__(
        self,
        llm: SummaryLLM,
        repo: SessionRepo,
        *,
        interval_turns: int = DEFAULT_INTERVAL_TURNS,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        privacy_mode: bool = True,
    ) -> None:
        if interval_turns <= 0:
            raise ValueError("interval_turns 必须为正")
        self._llm = llm
        self._repo = repo
        self._interval_turns = interval_turns
        self._interval_seconds = interval_seconds
        self._privacy_mode = privacy_mode

    def load(self, session_id: str) -> SummaryState | None:
        """读已有摘要（组合根/首轮注入；无摘要返回 None）。"""
        row = self._repo.get_summary(session_id)
        if row is None:
            return None
        return SummaryState(
            text=row.summary, up_to_turn=row.up_to_turn, updated_at=row.updated_at
        )

    def should_update(
        self, state: SummaryState | None, *, turn_seq: int, now: float
    ) -> bool:
        """10 轮一次或距上次更新 ≥30 分钟；没有新轮次不重复摘要。"""
        if state is None:
            return turn_seq >= self._interval_turns
        if turn_seq <= state.up_to_turn:
            return False
        return (
            turn_seq % self._interval_turns == 0
            or now - state.updated_at >= self._interval_seconds
        )

    async def update(
        self,
        session_id: str,
        turns: Sequence[SummaryTurn],
        *,
        turn_seq: int,
        now: float,
    ) -> SummaryState | None:
        """合并「旧摘要 + 新轮次」并落库；无新轮次/隐私模式返回 None。"""
        state = self.load(session_id)
        up_to = 0 if state is None else state.up_to_turn
        pending = [turn for turn in turns if turn.turn > up_to]
        if not pending:
            return None
        if self._privacy_mode and self._llm.name.startswith("cloud"):
            print(
                "[sidecar] 隐私模式下跳过会话摘要（4.4/5.2：绝不出网）",
                file=sys.stderr,
            )
            return None

        raw = await _collect(
            self._llm.generate(
                _build_messages(state, pending),
                stream=False,
                temperature=0.2,
            )
        )
        text = " ".join(raw.split()).strip()
        if not text:
            raise EchoesError(ErrorCode.INTERNAL_ERROR, "会话摘要输出为空")
        text = text[:MAX_SUMMARY_CHARS]
        row = await asyncio.to_thread(
            self._repo.save_summary,
            session_id,
            summary=text,
            up_to_turn=turn_seq,
            now=now,
        )
        return SummaryState(
            text=row.summary, up_to_turn=row.up_to_turn, updated_at=row.updated_at
        )


async def _collect(stream: AsyncIterator[str]) -> str:
    parts: list[str] = []
    async for piece in stream:
        parts.append(piece)
    return "".join(parts)


def _build_messages(
    state: SummaryState | None, turns: Sequence[SummaryTurn]
) -> list[dict[str, str]]:
    previous = "（无）" if state is None else state.text
    lines = [
        f"第 {turn.turn} 轮\n用户：{turn.user}\n助手：{turn.assistant}"
        for turn in turns
    ]
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"已有摘要：\n{previous}\n\n新增对话：\n" + "\n\n".join(lines),
        },
    ]


__all__ = [
    "DEFAULT_INTERVAL_SECONDS",
    "DEFAULT_INTERVAL_TURNS",
    "MAX_SUMMARY_CHARS",
    "SessionSummarizer",
    "SummaryLLM",
    "SummaryState",
    "SummaryTurn",
]
