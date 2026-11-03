"""R3a Query Rewrite（§4.2 ①）：条件触发的检索查询改写。

**为什么不是每轮都做**：一次改写 = 一次 LLM 调用（200–800ms + 成本）。只有
「指代 / 追问」才需要上下文补全：

    它怎么样        → 你上次说的那本书怎么样
    那个叫什么来着  → …

R3a 用正则门控（指代词 + 追问词），R4 接入意图路由；不满足条件时**不发请求**。
**失败原样返回**：改写是增强项，超时/报错/空输出都不能拖慢或打断本轮。
"""

from __future__ import annotations

import asyncio
import re
import sys
from collections.abc import AsyncIterator, Sequence
from typing import Protocol


class ChatModel(Protocol):
    """编排层注入的最小 LLM 面（结构化类型；不 import 引擎具体实现）。"""

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


class RecentTurn(Protocol):
    """改写提示里需要的最近一轮（`SummaryTurn` 结构化满足）。

    只读属性而非可变字段：`Sequence` 的协变要求属性只读，否则
    `list[SummaryTurn]` 不能传给 `Sequence[RecentTurn]`。
    """

    @property
    def user(self) -> str: ...

    @property
    def assistant(self) -> str: ...

# 指代 / 时间指涉 / 追问：命中任一才改写
_REWRITE_HINTS = re.compile(
    r"(它|他|她|这个|那个|这些|那些|这条|那条|那本|那件|这位|那位|"
    r"上次|上回|刚才|之前|当时|前面|刚刚|刚才说的|叫什么|是什么|怎么样|后来)"
)
_MAX_QUERY_CHARS = 200
_MAX_HISTORY_TURNS = 3
DEFAULT_TIMEOUT = 2.0

_SYSTEM_PROMPT = (
    "你是检索查询改写器。把用户最后一句话改写成不依赖上下文的独立检索查询，"
    "补全指代（它/那个/上次说的），保留原意与语言。"
    "只输出改写后的查询本身：不要解释、不要引号、不要标点之外的格式。"
    "如果无法改写，原样输出用户最后一句话。"
)


def needs_rewrite(text: str) -> bool:
    """是否需要上下文补全（正则门控，不调 LLM）。"""
    return bool(_REWRITE_HINTS.search(text or ""))


class QueryRewriter:
    """基于当前 LLM 的条件改写器（组合根注入；mock/失败时由调用方兜底）。"""

    def __init__(
        self, llm: ChatModel, *, timeout: float = DEFAULT_TIMEOUT
    ) -> None:
        self._llm = llm
        self._timeout = timeout

    async def rewrite(
        self, question: str, recent: Sequence[RecentTurn], *, force: bool = False
    ) -> str:
        """返回检索用 query；不需要/失败/超时都返回原句。

        `force=True`（memory_recall 意图）跳过正则门控：用户已经在明确要求
        回溯，指代可能不明显（「那本后来怎么样了」），值得多花一次调用。
        """
        text = question.strip()
        if not text or (not force and not needs_rewrite(text)):
            return text
        if getattr(self._llm, "name", "") == "mock":
            return text  # mock 台词不是有效查询，别污染检索
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(text, recent)},
        ]
        try:
            pieces: list[str] = []
            stream = self._llm.generate(
                messages, stream=False, max_tokens=64, temperature=0.0
            )
            async with asyncio.timeout(self._timeout):
                async for piece in stream:
                    pieces.append(piece)
        except TimeoutError:
            print("[sidecar] 查询改写超时（用原句检索）", file=sys.stderr)
            return text
        except Exception as exc:  # noqa: BLE001  改写失败不阻断本轮
            print(f"[sidecar] 查询改写失败（用原句检索）: {exc}", file=sys.stderr)
            return text
        rewritten = " ".join("".join(pieces).split()).strip().strip("\"'“”")
        if not rewritten or len(rewritten) > _MAX_QUERY_CHARS:
            return text
        return rewritten


def _user_prompt(question: str, recent: Sequence[RecentTurn]) -> str:
    lines: list[str] = []
    for turn in list(recent)[-_MAX_HISTORY_TURNS:]:
        user = " ".join(turn.user.split())
        assistant = " ".join(turn.assistant.split())
        if user:
            lines.append(f"用户：{user[:200]}")
        if assistant:
            lines.append(f"助手：{assistant[:200]}")
    context = "\n".join(lines) if lines else "（没有更早的对话）"
    return f"最近对话：\n{context}\n\n用户最后一句话：{question}\n\n独立检索查询："


__all__ = ["DEFAULT_TIMEOUT", "QueryRewriter", "needs_rewrite"]
