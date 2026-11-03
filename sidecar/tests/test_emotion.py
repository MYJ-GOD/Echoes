"""R4 4.7 情感检测：词表口径与阈值。"""

from __future__ import annotations

import pytest

from echoes_sidecar.orchestration.emotion import (
    Emotion,
    detect,
    instruction_for,
    label,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("今天好累", Emotion.TIRED),
        ("我有点难过", Emotion.SAD),
        ("压力好大，很焦虑", Emotion.ANXIOUS),
        ("气死了", Emotion.ANGRY),
        ("今天玩得很开心", Emotion.HAPPY),
        ("今天天气不错", Emotion.NEUTRAL),
        ("我喜欢这个功能", Emotion.NEUTRAL),  # 弱词 0.7 < 阈值 0.8
        ("", Emotion.NEUTRAL),
    ],
)
def test_detect_table(text: str, expected: Emotion) -> None:
    assert detect(text) is expected


def test_labels_are_human_readable() -> None:
    assert label(Emotion.TIRED) == "疲惫"
    assert label(Emotion.NEUTRAL) == "平静"


def test_instruction_is_none_for_neutral_and_natural_language_otherwise() -> None:
    assert instruction_for(Emotion.NEUTRAL) is None
    assert instruction_for(Emotion.HAPPY) is not None
    assert "轻快" in (instruction_for(Emotion.HAPPY) or "")
