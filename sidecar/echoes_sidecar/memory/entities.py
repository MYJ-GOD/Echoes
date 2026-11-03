"""R3b 3.6 实体加分：query 里的词在候选文本中命中多少。

**为什么用轻量分词而不是再跑一个 NER**：实体加分的目的是「同一句话里提到的
人名/地名/作品名」把相关条目往上抬，不是构建知识图谱。jieba + 停用词在
中文短 query 上足够，误判的代价只是一次重排，不是写入错误记忆。

口径（§4.2 ⑤）：`bonus = min(entity_hits × 0.1, 0.3)`，与 rerank 归一化分相加，
**不直接在 logits 上加**。
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import jieba  # type: ignore[import-untyped]

ENTITY_BONUS_STEP = 0.1
ENTITY_BONUS_CAP = 0.3
MAX_ENTITIES = 8

# 指代/疑问/时间虚词：它们出现在每条候选里都不稀奇，算实体只会放大噪音
_STOPWORDS = frozenset(
    {
        "什么",
        "怎么",
        "怎样",
        "哪个",
        "哪些",
        "这个",
        "那个",
        "这些",
        "那些",
        "上次",
        "上回",
        "刚才",
        "之前",
        "当时",
        "后来",
        "现在",
        "今天",
        "昨天",
        "明天",
        "一下",
        "还是",
        "就是",
        "可以",
        "我们",
        "你们",
        "他们",
        "自己",
        "怎么样",
        "叫什么",
        "是不是",
    }
)
_ASCII_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9._+-]{1,}")


def query_entities(text: str) -> tuple[str, ...]:
    """从 query 抽实体候选（去重、保序、封顶）。"""
    seen: set[str] = set()
    entities: list[str] = []
    for token in jieba.cut(text or "", cut_all=False):
        word = token.strip()
        if len(word) < 2 or word in _STOPWORDS:
            continue
        if word.isdigit():
            continue
        if word in seen:
            continue
        seen.add(word)
        entities.append(word)
        if len(entities) >= MAX_ENTITIES:
            break
    return tuple(entities)


def entity_hits(entities: Sequence[str], text: str) -> int:
    """候选文本里命中的实体个数（子串匹配，大小写不敏感）。"""
    haystack = text.casefold()
    return sum(1 for entity in entities if entity.casefold() in haystack)


def entity_bonus(entities: Sequence[str], text: str) -> float:
    """§4.2 ⑤ 的加分（封顶 0.3）。"""
    return min(entity_hits(entities, text) * ENTITY_BONUS_STEP, ENTITY_BONUS_CAP)


__all__ = [
    "ENTITY_BONUS_CAP",
    "ENTITY_BONUS_STEP",
    "MAX_ENTITIES",
    "entity_bonus",
    "entity_hits",
    "query_entities",
]
