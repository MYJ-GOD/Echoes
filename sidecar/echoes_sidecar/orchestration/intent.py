"""R4 4.1 正则意图层（§5.1）：五类意图，可解释、零延迟。

**为什么先是正则**：一次 LLM 判意图 = 每轮一次额外调用（延迟 60% 的来源都在
首包前），而「我是谁 / 还记得上次 / 好累」这类句式高度固定。v1 用正则覆盖，
`task` 只分类不接工具（L3 暂不做）；R4 之后如需更细的路由再接小模型。

**优先级**：profile_query → memory_recall → emotional_support → task → chat。
显式的「我是谁」比「上次说的」更具体；情绪优先于普通闲聊。规则按整句匹配，
不做分词，避免把「上次说的工作」误判成 profile（那里没有「我的工作」）。
"""

from __future__ import annotations

import re
from enum import StrEnum


class Intent(StrEnum):
    CHAT = "chat"
    EMOTIONAL_SUPPORT = "emotional_support"
    MEMORY_RECALL = "memory_recall"
    PROFILE_QUERY = "profile_query"
    TASK = "task"


_PROFILE = re.compile(
    r"(我是谁|我叫什么|我的名字|我是做什么|我的职业|我的工作|我住哪|我住在哪|"
    r"我的家乡|我的生日|我的爱好|我的兴趣|我有哪些|关于我)"
)
_RECALL = re.compile(
    r"(还记得|记得|你说过|你提过|你上次|上次说|上次聊|上回|之前说|之前聊|"
    r"我跟你|我们聊过|叫什么|那本|那条|那个.*叫什么)"
)
_EMOTION = re.compile(
    r"(好累|累死|压力大|压力好大|难受|焦虑|难过|烦死|崩溃|撑不住|不开心|"
    r"抑郁|委屈|想哭)"
)
_TASK = re.compile(
    r"(帮我查|帮我搜|帮我写|帮我算|帮我订|帮我设|提醒我|天气(?:怎么样|如何|预报)|"
    r"几点了|翻译|总结一下)"
)


def classify(text: str) -> Intent:
    """纯函数：中文短句 → 意图（未知一律 chat）。"""
    value = (text or "").strip()
    if not value:
        return Intent.CHAT
    if _PROFILE.search(value):
        return Intent.PROFILE_QUERY
    if _RECALL.search(value):
        return Intent.MEMORY_RECALL
    if _EMOTION.search(value):
        return Intent.EMOTIONAL_SUPPORT
    if _TASK.search(value):
        return Intent.TASK
    return Intent.CHAT


__all__ = ["Intent", "classify"]
