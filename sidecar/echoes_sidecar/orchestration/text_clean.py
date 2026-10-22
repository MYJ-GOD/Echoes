"""TTS 前文本清洗（5.2 编排层；ADR-001 阶段 -1 证据：markdown/emoji 常态输出）。

口径：语音合成读不出「**」与表情符号——清洗在 TTS 边界做一次纯函数变换。
回复文本帧（assistant_text）保持原样（UI 直渲），音频路径吃清洗后文本。
规则序：先剥结构标记（markdown/列表/标题），再剥 emoji，最后规整空白。
"""

from __future__ import annotations

import re

_MD_INLINE = re.compile(
    r"\*\*(?P<b>.+?)\*\*"  # **粗**
    r"|__(?P<b2>.+?)__"  # __粗__
    r"|\*(?P<i>.+?)\*"  # *斜*
    r"|_(?P<i2>.+?)_"  # _斜_
    r"|`(?P<c>.+?)`",  # `code`
    re.DOTALL,
)
_MD_LIST_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+", re.MULTILINE)
_MD_NUM_INLINE = re.compile(r"\b\d{1,2}[.)]\s+")  # 行内序号「2. 」（点后必空白，「2.5」不误伤）
_MD_HEAD = re.compile(r"^#{1,6}\s+", re.MULTILINE)
# emoji 及各种 pictograph 区段（TTS 无声义，直接剥）
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\ufe0f]",
    flags=re.UNICODE,
)
_WS = re.compile(r"[ \t]+")


def clean_for_tts(text: str) -> str:
    """回复文本 → 可朗读文本（纯函数；详细规则见模块 docstring）。"""

    cleaned = _MD_INLINE.sub(
        lambda m: next(g for g in m.groupdict().values() if g is not None), text
    )
    cleaned = _MD_HEAD.sub("", cleaned)
    cleaned = _MD_LIST_LINE.sub("", cleaned)
    cleaned = _MD_NUM_INLINE.sub("", cleaned)
    cleaned = _EMOJI.sub("", cleaned)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    cleaned = _WS.sub(" ", cleaned)
    return cleaned.strip()


__all__ = ["clean_for_tts"]
