"""TTS 前文本清洗（5.2 编排层职责；ADR-001 阶段 -1 证据：markdown/emoji 常态输出）。

口径：语音合成读不出「**」和表情符号——清洗在 TTS 边界做一次纯函数变换；
回复文本帧（assistant_text）保持原样（UI 富呈现），音频路径吃清洗后文本。
"""

from __future__ import annotations

import pytest

from echoes_sidecar.orchestration.text_clean import clean_for_tts


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 纯口语不动
        ("今天也辛苦啦，早点睡。", "今天也辛苦啦，早点睡。"),
        # markdown 强调/斜体/代码符号剥离
        ("我是 **Echoes**，一个 AI 陪伴。", "我是 Echoes，一个 AI 陪伴。"),
        ("*很*温柔地陪伴", "很温柔地陪伴"),
        ("记得 `加分` 呀", "记得 加分 呀"),
        # 列表符号/序号剥离（保持词序可听；行内序号也剥）
        ("- 第一：好好吃饭\n- 第二：早点睡", "第一：好好吃饭 第二：早点睡"),
        ("1. 先喝水 2. 再睡觉", "先喝水 再睡觉"),
        ("先热牛奶，2. 再去睡觉", "先热牛奶，再去睡觉"),
        # emoji 全剥
        ("好好躺平、放空～ 😌🛋️", "好好躺平、放空～"),
        ("😢别难过，我在", "别难过，我在"),
        # 标题井号
        ("## 今晚计划", "今晚计划"),
    ],
)
def test_clean_for_tts_rules(raw: str, expected: str) -> None:
    assert clean_for_tts(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "　", "\n\n"],
)
def test_clean_for_tts_emptyish(raw: str) -> None:
    assert clean_for_tts(raw) == ""
