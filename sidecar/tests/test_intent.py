"""R4 4.1 正则意图层：五类意图与优先级。"""

from __future__ import annotations

import pytest

from echoes_sidecar.orchestration.intent import Intent, classify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("我是谁", Intent.PROFILE_QUERY),
        ("我叫什么名字", Intent.PROFILE_QUERY),
        ("我的工作是什么", Intent.PROFILE_QUERY),
        ("我有哪些爱好", Intent.PROFILE_QUERY),
        ("还记得上次说的那本书吗", Intent.MEMORY_RECALL),
        ("你上次说的小王子", Intent.MEMORY_RECALL),
        ("那本吉他书叫什么", Intent.MEMORY_RECALL),
        ("今天好累", Intent.EMOTIONAL_SUPPORT),
        ("压力好大，有点焦虑", Intent.EMOTIONAL_SUPPORT),
        ("帮我查一下天气", Intent.TASK),
        ("提醒我明天开会", Intent.TASK),
        ("今天天气不错", Intent.CHAT),
        ("在吗", Intent.CHAT),
        ("", Intent.CHAT),
        ("   ", Intent.CHAT),
    ],
)
def test_classify_table(text: str, expected: Intent) -> None:
    assert classify(text) is expected


def test_explicit_profile_beats_recall_words() -> None:
    # 「我的工作」是 profile 句式；「上次说的工作」没有「我的」，归回溯
    assert classify("我的工作是什么") is Intent.PROFILE_QUERY
    assert classify("上次说的工作叫什么") is Intent.MEMORY_RECALL
