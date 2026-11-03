"""R4 4.7 情感检测（轻量词表版）：用户这句话更接近哪种情绪。

**为什么先做词表**：情感链路的第一步只要「够准地识别明显情绪」，不值得为它
引入一个中文情感模型（选型、权重、许可、延迟都还没定，§5.4）。词表可解释、
零延迟，先让「检测 → 记忆 → 表达」跑通；模型替换点就在这里，调用方不变。

**得分规则**：命中词按权重累加，取最高分；全部为 0 → `neutral`。否定词
（不累/不开心）不在这里处理——「不开心」本身入库为 sad，符合直觉。
"""

from __future__ import annotations

from enum import StrEnum

# 每类情绪的词表（命中即加分；长词优先由分值体现，不做重叠消解）
_LEXICON: dict[str, tuple[tuple[str, float], ...]] = {
    "tired": (
        ("累", 1.0),
        ("困", 0.8),
        ("熬", 0.6),
        ("没力气", 1.0),
        ("撑不住", 1.2),
    ),
    "sad": (
        ("难过", 1.2),
        ("伤心", 1.2),
        ("想哭", 1.2),
        ("失落", 1.0),
        ("委屈", 1.0),
        ("不开心", 1.0),
        ("孤独", 0.9),
    ),
    "anxious": (
        ("焦虑", 1.2),
        ("紧张", 1.0),
        ("压力", 1.0),
        ("担心", 0.9),
        ("害怕", 1.0),
        ("慌", 0.8),
    ),
    "angry": (
        ("生气", 1.2),
        ("气死", 1.2),
        ("烦死", 1.1),
        ("讨厌", 0.9),
        ("火大", 1.1),
    ),
    "happy": (
        ("开心", 1.2),
        ("高兴", 1.2),
        ("太好了", 1.1),
        ("喜欢", 0.7),
        ("兴奋", 1.0),
    ),
}

# 阈值：单个弱词（0.6）不足以判定情绪，避免「我喜欢这个功能」被当成 happy
_MIN_SCORE = 0.8


class Emotion(StrEnum):
    NEUTRAL = "neutral"
    TIRED = "tired"
    SAD = "sad"
    ANXIOUS = "anxious"
    ANGRY = "angry"
    HAPPY = "happy"


def detect(text: str) -> Emotion:
    """中文短句 → 情绪标签（无命中一律 neutral）。"""
    value = (text or "").strip()
    if not value:
        return Emotion.NEUTRAL
    best = Emotion.NEUTRAL
    best_score = 0.0
    for label, entries in _LEXICON.items():
        score = sum(weight for word, weight in entries if word in value)
        if score > best_score:
            best_score = score
            best = Emotion(label)
    return best if best_score >= _MIN_SCORE else Emotion.NEUTRAL


_LABELS = {
    Emotion.NEUTRAL: "平静",
    Emotion.TIRED: "疲惫",
    Emotion.SAD: "低落",
    Emotion.ANXIOUS: "焦虑",
    Emotion.ANGRY: "生气",
    Emotion.HAPPY: "开心",
}

# R2b 2b.6：给 CosyVoice2 instruct2 的自然语言指令（中性不传，保持默认语气）
_INSTRUCTIONS: dict[Emotion, str] = {
    Emotion.TIRED: "用温柔、放慢一点的语气，像在照顾一个很累的人。",
    Emotion.SAD: "用轻柔、安静的语气，先安慰再说话。",
    Emotion.ANXIOUS: "用平稳、让人安心的语气，节奏稍慢，不要催促。",
    Emotion.ANGRY: "用冷静、克制的语气，不要刺激对方。",
    Emotion.HAPPY: "用轻快、带一点笑意的语气。",
}


def label(value: Emotion) -> str:
    """中文标签（进 prompt 的人话）。"""
    return _LABELS[value]


def instruction_for(value: Emotion) -> str | None:
    """情绪 → TTS 风格指令；中性返回 None（不改变默认语气）。"""
    return _INSTRUCTIONS.get(value)


__all__ = ["Emotion", "detect", "instruction_for", "label"]
