"""4.5 分句纯函数（13.1-L1，零依赖）：它是 TTFA 优化的前置件，必须先锁行为。

关注点：不丢字、不切碎（收尾符号/连写标点/小数点）、过长句有兜底、未知策略报错。
"""

from __future__ import annotations

import pytest

from echoes_sidecar.audio.chunker import split_sentences


def test_empty_and_whitespace_return_no_sentences() -> None:
    assert split_sentences("") == []
    assert split_sentences("   \n\t ") == []


def test_text_without_terminator_is_single_sentence() -> None:
    assert split_sentences("今天有点累") == ["今天有点累"]


def test_chinese_sentences_split_on_punctuation() -> None:
    assert split_sentences("你好。我很好！你呢？") == ["你好。", "我很好！", "你呢？"]


def test_closers_stay_with_their_sentence() -> None:
    assert split_sentences("他说：「好。」然后走了。") == ["他说：「好。」", "然后走了。"]
    assert split_sentences('He said "Hi." Then left.') == ['He said "Hi."', "Then left."]


def test_repeated_terminators_are_not_split_apart() -> None:
    """省略号/连写标点是同一处停顿，切碎会产生 "…" 这样的无音频块。"""
    assert split_sentences("我……算了") == ["我……", "算了"]
    assert split_sentences("真的吗？！") == ["真的吗？！"]


def test_decimal_point_is_not_a_terminator() -> None:
    assert split_sentences("圆周率约等于3.14。") == ["圆周率约等于3.14。"]


def test_newline_acts_as_pause() -> None:
    assert split_sentences("第一句\n第二句") == ["第一句", "第二句"]


def test_english_punctuation() -> None:
    assert split_sentences("Hi. How are you? Fine; thanks.") == [
        "Hi.",
        "How are you?",
        "Fine;",
        "thanks.",
    ]


def test_long_sentence_splits_on_secondary_pause() -> None:
    """软上限 60：首块太大等于首音频延迟大，因此长句必须再切。"""
    long_text = "，".join(["这是一段没有句号的超长句子"] * 12) + "。"
    parts = split_sentences(long_text)
    assert len(parts) > 1
    assert all(len(part) <= 60 for part in parts)
    assert "".join(parts) == long_text


def test_long_run_without_any_pause_is_hard_split() -> None:
    text = "啊" * 150
    parts = split_sentences(text)
    assert len(parts) == 3
    assert all(len(part) <= 60 for part in parts)
    assert "".join(parts) == text


def test_no_character_is_lost() -> None:
    text = "今天面试有点紧张。你记得我说过这件事吗？我记得。那就好！"
    assert "".join(split_sentences(text)) == text


def test_policy_none_keeps_whole_text() -> None:
    assert split_sentences("你好。我很好。", policy="none") == ["你好。我很好。"]


def test_unknown_policy_raises() -> None:
    """3.2 报错而非降级：拼错策略名不该静默套用 punct。"""
    with pytest.raises(ValueError, match="未知分句策略"):
        split_sentences("你好。", policy="puct")


def test_first_max_chars_cuts_first_sentence_at_pause() -> None:
    """首句短切：首句在停顿处提前断一次，其余句子不受影响（ADR-012 §4.1 杠杆）。

    本地 RTF≈1，首音频块要等首句合成完 → 首句长度就是 TTFA 的下界。
    """
    text = "（mock 回复）骨架装配正常，可以开始聊了。"
    assert split_sentences(text) == [text]  # 默认不切：软上限 60 字没到
    parts = split_sentences(text, first_max_chars=16)
    assert parts == ["（mock 回复）骨架装配正常，", "可以开始聊了。"]
    assert "".join(parts) == text


def test_first_max_chars_never_hard_cuts_words() -> None:
    """16 字内没有停顿 → 保持整句（硬切会把词切碎，比慢更糟）。"""
    text = "骨架装配一切正常并且可以开始聊了。"
    assert split_sentences(text, first_max_chars=16) == [text]


def test_first_max_chars_ignores_too_early_pause() -> None:
    """最早的停顿在 4 字以内（"哦，"）→ 不切，否则会输出语音碎片。"""
    text = "哦，好，那我们先从今天最累的一件事说起。"
    assert split_sentences(text, first_max_chars=16) == [text]


def test_first_max_chars_only_affects_first_sentence() -> None:
    """后续句子仍按软上限走：第二句不会被同样的上限切成碎片。"""
    text = "第一句比较长需要在这里断开，后面还可以继续，保持整体节奏不变。"
    parts = split_sentences(text, first_max_chars=16)
    assert parts[0] == "第一句比较长需要在这里断开，"
    assert len(parts) == 2
    assert "".join(parts) == text
