"""13.2-1/2：golden 正例/反例双向对拍 + schema 单一来源完整性。

golden 文件是文档 3.4 示例的镜像；改协议先改 docs/architecture.md 3.4 并走变更记录（12.2）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from echoes_sidecar.core.errors import ErrorCode
from echoes_sidecar.core.state_machine import AppState
from echoes_sidecar.ipc.schema import StateMsg, parse_line

GOLDEN = Path(__file__).parent / "golden"


def _lines(name: str) -> list[str]:
    text = (GOLDEN / name).read_text(encoding="utf-8")
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_golden_positive_roundtrip() -> None:
    """每条正例可解析，且 dump→再解析 双向稳定（3.4 兼容规则）。"""
    lines = _lines("positive.jsonl")
    # 13.2-2「每类消息至少一条正例」机器化：删任一类型即红（比数量下限更严）
    types = {str(json.loads(line)["type"]) for line in lines}
    assert types == {
        "hello",
        "asr_partial",
        "asr_final",
        "assistant_text",
        "turn_complete",
        "clone_progress",
        "error",
        "state",
        "control",
        "user_text",
        "clone_start",
        "clone_cancel",
    }
    for line in lines:
        msg = parse_line(line)
        again = msg.model_dump_json()
        assert parse_line(again) == msg


def test_golden_negative_rejected() -> None:
    """反例必须被 schema 拒绝（状态机 listening 是壳本地态；错误码不新增即拒绝）。"""
    for line in _lines("negative.jsonl"):
        with pytest.raises(ValidationError):
            parse_line(line)


def test_unknown_fields_ignored() -> None:
    """未知字段必须忽略（3.4 只追加兼容规则的 schema 侧执行点）。"""
    msg = parse_line('{"type": "user_text", "session_id": "s", "text": "在吗？", "x_future": 1}')
    assert msg.text == "在吗？"


def test_error_codes_total_16() -> None:
    """3.4.1 权威错误码共 16 条；只追加、不重命名、不复用（R1a 追加 HISTORY_WRITE_FAILED）。"""
    assert {code.value for code in ErrorCode} == {
        "SAMPLE_TOO_SHORT",
        "SAMPLE_TOO_NOISY",
        "CLONE_QUALITY_LOW",
        "CLONE_ENGINE_FAILED",
        "CLONE_CANCELLED",
        "MODEL_NOT_LOADED",
        "VOICE_NOT_AVAILABLE",
        "MIC_NOT_AVAILABLE",
        "LLM_PROVIDER_UNAVAILABLE",
        "LLM_KEY_MISSING",
        "ASR_ENGINE_ERROR",
        "TTS_ENGINE_ERROR",
        "STORAGE_ERROR",
        "HISTORY_WRITE_FAILED",
        "PROTOCOL_MISMATCH",
        "INTERNAL_ERROR",
    }


def test_state_enum_matches_app_state() -> None:
    """state 消息枚举与 core.AppState 值集一致（3.4/3.5 单一事实）。"""
    literal_values = set(get_args(StateMsg.model_fields["state"].annotation))
    assert literal_values == {state.value for state in AppState}
