"""mock 引擎契约守护（评审修复轮）。

test_mock_asr_final_shape：行为锁定型覆盖断言（mock 现行为固化为 golden 属性，防实现漂移）；
test_mock_clone_*：🔴 修复轮 TDD 对象——mock clone 不得返回保留 ID builtin:default（4.5/5.1）。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.engines.asr.mock import MockASREngine
from echoes_sidecar.engines.tts.mock import MockTTSEngine


class _NoAudio(AudioInputStream):
    """空流：mock 引擎均不消费流（真实实现消费——4.5）。仅服务本测试的输入占位。"""

    def __aiter__(self) -> AsyncIterator[Any]:
        return iter(())


async def test_mock_clone_not_builtin_preserved_id() -> None:
    """评审 🟡-6：builtin:default 是 2.5 none 态保留 ID 且不落库（5.1）——
    mock 克隆必须产出非保留 ID，否则「克隆成功」与「从未克隆」在阶段 0 验收里不可区分。
    """
    voice_id = await MockTTSEngine().clone(_NoAudio())
    assert voice_id != "builtin:default"
    assert voice_id.startswith("voice:mock-")


async def test_mock_clone_id_stable_per_call_shape() -> None:
    """产出形态 = voice:mock-<短尾>（骨架闭环可识别，不暗示资产文件存在）。"""
    voice_id = await MockTTSEngine().clone(_NoAudio())
    suffix = voice_id.removeprefix("voice:mock-")
    assert 6 <= len(suffix) <= 12


async def test_mock_asr_final_shape() -> None:
    """覆盖断言（现行为固化）：mock ASR 恒定一条 final 转写，字段集符合 4.5。"""
    chunks = [c async for c in MockASREngine().transcribe(_NoAudio())]
    assert len(chunks) == 1
    assert set(chunks[0]) == {"text", "is_final", "start_ms", "end_ms"}
    assert chunks[0]["is_final"] is True
