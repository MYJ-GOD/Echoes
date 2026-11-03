"""R4 4.3 Grounding 异步质检：回复里关于用户的事实，能否被本轮注入的记忆支持。

**为什么异步**：质检要再跑一次 LLM（几百毫秒到几秒），绝不能占 turn 的关键
路径；它在 `turn_complete` 之后起任务，结果写回 `turn.grounding_*`。

**v1 口径**：
- 只校验「回复里关于用户的陈述」；寒暄/建议/情绪回应不算 claim。
- 没有注入记忆的 turn 不质检（没有证据可比），verdict 留 NULL。
- judge 不可用（mock LLM / 失败）时留 NULL，不伪造「通过」。
- 输出严格 JSON；解析失败按质检失败记日志，不反噬对话。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from echoes_sidecar.memory.extractor import collect_text
from echoes_sidecar.memory.rewrite import ChatModel

DEFAULT_TIMEOUT = 10.0
MAX_REPLY_CHARS = 2000

_SYSTEM = (
    "你是严格的事实质检器。判断「助手回复」里关于用户的陈述是否都能被"
    "「本轮注入的记忆」支持。只输出 JSON，格式："
    '{"faithful": true|false, "score": 0到1的小数, "unsupported_claims": ["..."]}'
    "\n规则："
    "\n- 回复里没有关于用户的事实陈述（寒暄/建议/情绪回应）→ faithful=true, score=1.0"
    "\n- 有陈述但记忆里找不到依据 → faithful=false，把无依据的陈述写进 unsupported_claims"
    "\n- score 表示有依据的比例，1.0 = 全部有据；不要解释、不要 markdown。"
)


@dataclass(frozen=True)
class GroundingResult:
    faithful: bool
    score: float
    unsupported: tuple[str, ...] = ()


class GroundingJudge(Protocol):
    @property
    def available(self) -> bool: ...

    async def check(
        self, reply: str, evidence: Sequence[str]
    ) -> GroundingResult: ...


class LLMGroundingJudge:
    """用当前 LLM 做 claim-vs-evidence 判定（与聊天共用 provider，不另建客户端）。"""

    def __init__(
        self,
        llm: ChatModel,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._llm = llm
        self._timeout = timeout

    @property
    def available(self) -> bool:
        # mock 台词不是有效判定，别把假结论写进质检列
        return getattr(self._llm, "name", "") != "mock"

    async def check(self, reply: str, evidence: Sequence[str]) -> GroundingResult:
        if not self.available:
            return GroundingResult(faithful=True, score=1.0)
        text = reply.strip()
        if not text:
            return GroundingResult(faithful=True, score=1.0)
        if not evidence:
            return GroundingResult(faithful=True, score=1.0)
        messages = [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _user_prompt(text, evidence)},
        ]
        async with asyncio.timeout(self._timeout):
            raw = await collect_text(
                self._llm.generate(
                    messages, stream=False, max_tokens=300, temperature=0.0
                )
            )
        return _parse(raw)


def _user_prompt(reply: str, evidence: Sequence[str]) -> str:
    facts = "\n".join(f"- {item}" for item in evidence if item.strip())
    return f"本轮注入的记忆：\n{facts}\n\n助手回复：\n{reply[:MAX_REPLY_CHARS]}"


def _parse(raw: str) -> GroundingResult:
    """容错解析：允许 ```json 围栏/前后噪声，只取第一个 JSON 对象。"""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"质检输出不是 JSON：{raw[:120]!r}")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"质检输出 JSON 解析失败：{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("质检输出顶层必须是对象")
    faithful = bool(payload.get("faithful", False))
    try:
        score = float(payload.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0
    score = max(0.0, min(1.0, score))
    raw_claims = payload.get("unsupported_claims", [])
    claims = (
        tuple(str(item).strip() for item in raw_claims if str(item).strip())
        if isinstance(raw_claims, list)
        else ()
    )
    return GroundingResult(faithful=faithful, score=score, unsupported=claims)


__all__ = [
    "DEFAULT_TIMEOUT",
    "GroundingJudge",
    "GroundingResult",
    "LLMGroundingJudge",
]
