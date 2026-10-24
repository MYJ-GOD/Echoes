"""memory extractor：turn 结束后抽取长期事实（文档 5.2 / 13.3）。

**职责边界**：本模块只做「LLM 调用 + 输出解析 + 写入编排」；向量检索/存储归
`MemoryStore`，什么时候抽取归 `TurnGraph`（5.2：每轮 turn 结束后异步）。

**质量门禁**：抽取产线的正确率由 13.3 的 50 条评测集守护（precision ≥0.85 /
recall ≥0.7 / 替代正确率 ≥0.9）。prompt/模型/策略改动必须重跑
`scripts/eval_memory.py`，低于阈值不合入。

**隐私**（4.4/5.2）：抽取 provider 必须跟随全局模式；隐私模式 + 云端 provider
时直接跳过（绝不出网）。敏感信息在解析层再做一次 deny 过滤——prompt 说了不算，
LLM 仍可能吐出证件号/密码，错误记忆比没有记忆更毒。
"""
from __future__ import annotations

import json
import re
import sys
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.db.memory_repo import CATEGORIES, MemoryFact
from echoes_sidecar.memory.store import MemoryStore

# 单轮最多落 8 条：正常对话不会有更多；超了通常是模型在复述/发散。
MAX_FACTS_PER_TURN = 8
# 单条事实字符上限：超过多半是把整段话抄回来了，直接丢（不截断——截断会改语义）。
MAX_FACT_CHARS = 120
# 已知事实候选上限：塞太多会挤占抽取 prompt，也会让 replaces 选错。
MAX_ACTIVE_FACTS = 50

_SYSTEM_PROMPT = (
    "你是 Echoes 的记忆抽取器。只从「用户」的发言中抽取可长期复用的用户事实。\n"
    "\n"
    "规则：\n"
    "1. 只抽取用户明确说出的稳定信息；助手说的话一律不算。\n"
    "2. 类别只能是：preference（偏好/习惯）、event（经历/计划/事件）、\n"
    "   identity（身份/背景/关系）、other（其他稳定事实）。\n"
    "3. 忽略：临时情绪或身体状态（如“今天好累”）、提问、假设（如“如果…”）、\n"
    "   玩笑、对助手的要求、一次性的当下动作。\n"
    "4. 每条事实用第三人称、只保留核心事实（不超过 20 字）；不要添加原文没有的时间、程度、细节。\n"
    "5. 一句话包含多个独立事实时，分别列出，不要合并。\n"
    "6. 不抽取敏感信息：密码、验证码、证件号、银行卡、精确住址、健康诊断、电话号码。\n"
    "7. 更新：若用户说“改了/现在/不再/搬到”等，只输出更新后的事实，\n"
    "   不要把已知旧事实原样再列一遍；把旧事实 id 填进新事实的 replaces。\n"
    "8. 没有可抽取的事实时输出 []。\n"
    "\n"
    "示例：\n"
    "已知：[f1] 用户下周三去上海出差\n"
    "用户：出差改到周五了\n"
    '输出：[{"fact":"用户下周五去上海出差","category":"event","replaces":"f1"}]\n'
    "已知：[]\n"
    "用户：我最近在减肥，晚上不吃主食。\n"
    '输出：[{"fact":"用户最近在减肥","category":"preference"},'
    '{"fact":"用户晚上不吃主食","category":"preference"}]\n'
    "\n"
    "只输出严格 JSON 数组，不要 markdown 代码块，不要解释：\n"
    '[{"fact":"...","category":"preference","replaces":null}]\n'
)

# 解析层的第二道隐私闸：这些词命中即丢弃（prompt 约束不能当安全边界）。
_SENSITIVE = re.compile(
    r"密码|验证码|身份证|银行卡|信用卡|护照|社保|病历|诊断|家庭地址|精确住址"
)
# 11 位以上连续数字：手机号/证件号的高置信形态。
_LONG_DIGITS = re.compile(r"\d{11,}")


@dataclass(frozen=True)
class ExtractedFact:
    """一条待写入的抽取结果；`replaces` 是被取代的已知事实 id。"""

    fact: str
    category: str
    replaces: str | None = None


class FactLLM(Protocol):
    """抽取只需要「一段 messages → 文本片流」；不依赖 engines 层的 ABC（15.2）。"""

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


class MemoryExtractor:
    """LLM 事实抽取 + 可选写入（store 为 None 时只抽取，供 13.3 评测）。"""

    def __init__(
        self,
        llm: FactLLM,
        store: MemoryStore | None = None,
        *,
        privacy_mode: bool = True,
    ) -> None:
        self._llm = llm
        self._store = store
        self._privacy_mode = privacy_mode

    async def extract(
        self,
        profile_id: str,
        transcript: str,
        *,
        active_facts: Sequence[MemoryFact | dict[str, str]] | None = None,
    ) -> list[ExtractedFact]:
        """从一段「用户/助手」对话中抽取事实（不写库）。

        `active_facts` 显式给出时不做 store 查询（评测用）；否则从 store 取当前
        有效事实作为 `replaces` 的候选集。
        """
        text = transcript.strip()
        if not text:
            return []
        if self._privacy_mode and self._llm.name.startswith("cloud"):
            print(
                "[sidecar] 隐私模式下跳过记忆抽取（4.4/5.2：绝不出网）",
                file=sys.stderr,
            )
            return []

        active = await self._resolve_active(profile_id, active_facts)
        active_ids = {item["id"] for item in active}
        messages = _build_messages(active, text)
        raw = await collect_text(self._llm.generate(messages, stream=False, temperature=0.0))
        facts = _parse(raw, active_ids)
        return facts[:MAX_FACTS_PER_TURN]

    async def ingest(
        self,
        profile_id: str,
        transcript: str,
        *,
        active_facts: Sequence[MemoryFact | dict[str, str]] | None = None,
        source_session_id: str | None = None,
        source_turn: int | None = None,
    ) -> list[MemoryFact]:
        """抽取并写入；单条失败不影响后续（写入失败的语义由调用方收口）。"""
        if self._store is None:
            raise EchoesError(ErrorCode.INTERNAL_ERROR, "MemoryExtractor 未装配 MemoryStore")
        extracted = await self.extract(profile_id, transcript, active_facts=active_facts)
        stored: list[MemoryFact] = []
        superseded: set[str] = set()
        for item in extracted:
            target = item.replaces if item.replaces not in superseded else None
            try:
                fact = await self._store.remember(
                    fact=item.fact,
                    category=item.category,
                    profile_id=profile_id,
                    source_session_id=source_session_id,
                    source_turn=source_turn,
                    supersedes=target,
                )
            except EchoesError:
                if target is None:
                    raise
                # 目标在抽取后已被本轮另一条事实取代/删除：退化为新增，不丢新信息。
                fact = await self._store.remember(
                    fact=item.fact,
                    category=item.category,
                    profile_id=profile_id,
                    source_session_id=source_session_id,
                    source_turn=source_turn,
                )
            if target is not None:
                superseded.add(target)
            stored.append(fact)
        return stored

    async def _resolve_active(
        self,
        profile_id: str,
        active_facts: Sequence[MemoryFact | dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        if active_facts is not None:
            source: Sequence[MemoryFact | dict[str, str]] = active_facts
        elif self._store is not None:
            source = await self._store.active(profile_id, limit=MAX_ACTIVE_FACTS)
        else:
            source = []
        result: list[dict[str, str]] = []
        for item in source:
            if isinstance(item, MemoryFact):
                result.append({"id": item.id, "fact": item.fact, "category": item.category})
            else:
                result.append(
                    {
                        "id": str(item.get("id", "")),
                        "fact": str(item.get("fact", "")),
                        "category": str(item.get("category", "other")),
                    }
                )
        return result


async def collect_text(stream: AsyncIterator[str]) -> str:
    """把 provider 的 AsyncIterator 收成全量文本（4.4：非流式仍按 iterator 契约）。"""
    parts: list[str] = []
    async for piece in stream:
        parts.append(piece)
    return "".join(parts)


def _build_messages(active: list[dict[str, str]], transcript: str) -> list[dict[str, str]]:
    if active:
        known = "\n".join(
            f"[{item['id']}] {item['fact']}（{item['category']}）" for item in active
        )
    else:
        known = "（无）"
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"已知事实：\n{known}\n\n本轮对话：\n{transcript}",
        },
    ]


def _parse(raw: str, active_ids: set[str]) -> list[ExtractedFact]:
    """严格 JSON 解析 + 逐条校验；非法输出报错，非法条目丢弃并记 stderr。"""
    payload = _extract_json_array(raw)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise EchoesError(
            ErrorCode.INTERNAL_ERROR,
            f"记忆抽取输出不是合法 JSON：{exc.msg}（原始输出前 200 字：{raw[:200]!r}）",
        ) from exc
    if not isinstance(data, list):
        raise EchoesError(
            ErrorCode.INTERNAL_ERROR, f"记忆抽取输出必须是数组，实际 {type(data).__name__}"
        )

    facts: list[ExtractedFact] = []
    seen: set[str] = set()
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            _warn(f"第 {index} 条不是对象，已丢弃")
            continue
        fact = item.get("fact")
        category = item.get("category")
        if not isinstance(fact, str) or not fact.strip():
            _warn(f"第 {index} 条缺 fact，已丢弃")
            continue
        fact = " ".join(fact.split())
        if len(fact) > MAX_FACT_CHARS:
            _warn(f"第 {index} 条超过 {MAX_FACT_CHARS} 字，已丢弃")
            continue
        if not isinstance(category, str) or category.strip().lower() not in CATEGORIES:
            _warn(f"第 {index} 条类别非法（{category!r}），已丢弃")
            continue
        category = category.strip().lower()
        if _looks_sensitive(fact) or "助手" in fact:
            _warn(f"第 {index} 条命中隐私/助手过滤，已丢弃")
            continue
        key = _normalize(fact)
        if key in seen:
            continue
        seen.add(key)
        replaces = item.get("replaces")
        if not isinstance(replaces, str) or not replaces.strip():
            replaces = None
        elif replaces not in active_ids:
            _warn(f"第 {index} 条 replaces={replaces!r} 不在已知事实中，按新增处理")
            replaces = None
        facts.append(ExtractedFact(fact=fact, category=category, replaces=replaces))
        if len(facts) >= MAX_FACTS_PER_TURN:
            break
    return facts


def _extract_json_array(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        # 去掉首尾代码围栏：```json ... ``` / ``` ... ```
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if text.startswith("{"):
        raise EchoesError(
            ErrorCode.INTERNAL_ERROR,
            f"记忆抽取输出必须是数组，实际是对象（原始输出前 200 字：{raw[:200]!r}）",
        )
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        raise EchoesError(
            ErrorCode.INTERNAL_ERROR,
            f"记忆抽取输出找不到 JSON 数组（原始输出前 200 字：{raw[:200]!r}）",
        )
    return text[start : end + 1]


def _looks_sensitive(fact: str) -> bool:
    return bool(_SENSITIVE.search(fact) or _LONG_DIGITS.search(fact))


def _normalize(text: str) -> str:
    return re.sub(r"[\s，。！？、；：,.!?;:（）()【】\[\]“”\"']", "", text).lower()


def _warn(message: str) -> None:
    print(f"[sidecar] 记忆抽取：{message}", file=sys.stderr)


__all__ = [
    "MAX_ACTIVE_FACTS",
    "MAX_FACT_CHARS",
    "MAX_FACTS_PER_TURN",
    "ExtractedFact",
    "FactLLM",
    "MemoryExtractor",
    "collect_text",
]
