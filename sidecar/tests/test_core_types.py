"""core 类型守护（评审修复轮新增）：WS 帧位建档（3.4 v1.4）与 core 出口完整性。"""
from __future__ import annotations

from echoes_sidecar.core import AudioChunk, Persona, WSFrameFlags  # noqa: F401


def test_ws_frame_flags_bits_distinct() -> None:
    """3.4 偏移 5 的 flags：三位互不重叠（bit0/bit1/bit2 语义独立可叠加）。"""
    assert WSFrameFlags.IS_FINAL.value & WSFrameFlags.INTERRUPT_HINT.value == 0
    assert WSFrameFlags.IS_FINAL.value & WSFrameFlags.CLONE_SAMPLE.value == 0
    assert WSFrameFlags.INTERRUPT_HINT.value & WSFrameFlags.CLONE_SAMPLE.value == 0


def test_ws_frame_flags_values_match_doc() -> None:
    """位值与文档一致：bit0=0x01 / bit1=0x02 / bit2=0x04。"""
    assert WSFrameFlags.IS_FINAL.value == 0x01
    assert WSFrameFlags.INTERRUPT_HINT.value == 0x02
    assert WSFrameFlags.CLONE_SAMPLE.value == 0x04
