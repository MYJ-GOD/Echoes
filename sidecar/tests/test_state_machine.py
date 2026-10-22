"""13.2-4：3.5 迁移表 fixture 对拍 + 逐条迁移真机走查 + 非零非法迁移。

口读文档时人眼会漏行；fixture 化之后「非法迁移」有了机械守护（13.2-4 / 6-阶段 0 验收 7 条）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from echoes_sidecar.core.state_machine import (
    LEGAL_TRANSITIONS,
    REQUIRED_ENGINES_FOR_READY,
    AppState,
    IllegalTransitionError,
    StateMachine,
    is_legal,
    required_engines_ready,
)

FIXTURE = Path(__file__).parent / "fixtures" / "state_transitions.json"


def _fixture() -> dict[str, list[list[str]]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_runtime_table_matches_fixture() -> None:
    """core 运行时迁移表与 3.5 fixture 完全一致（单一事实，漂移即红）。"""
    runtime = {
        (src.value, tuple(sorted(dst.value for dst in targets)))
        for src, targets in LEGAL_TRANSITIONS.items()
    }
    fixture = {
        (legal_src, tuple(sorted(dst for _, dst in pairs)))
        for legal_src, group in _fixture_legal_by_source().items()
        for pairs in [group]
    }
    assert runtime == fixture


def _fixture_legal_by_source() -> dict[str, list[tuple[str, str]]]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    for src, dst in _fixture()["legal"]:
        grouped.setdefault(src, []).append((src, dst))
    return grouped


@pytest.mark.parametrize("src,dst", _fixture()["legal"])
def test_legal_transition_accepted(src: str, dst: str) -> None:
    assert is_legal(AppState(src), AppState(dst))


@pytest.mark.parametrize("src,dst", _fixture()["illegal"])
def test_illegal_transition_rejected(src: str, dst: str) -> None:
    assert not is_legal(AppState(src), AppState(dst))


def test_state_machine_raises_and_keeps_state() -> None:
    """非法迁移抛 IllegalTransitionError，状态机原地不动（3.5 规则行）。"""
    machine = StateMachine()
    assert machine.state is AppState.BOOTING
    machine.transition(AppState.READY)
    with pytest.raises(IllegalTransitionError):
        machine.transition(AppState.ERROR)
    assert machine.state is AppState.READY


# ---------------- 修复轮（评审 🔴-2）：booting→READY 的必需引擎 gate ----------------


def test_required_engine_set_frozen() -> None:
    """3.5 v1.4：booting→ready 的必需引擎集合 = {ASR, LLM}，冻结值。"""
    assert set(REQUIRED_ENGINES_FOR_READY) == {"asr", "llm"}


def test_required_engines_ready_full_set_passes() -> None:
    """必需集合全就绪 → True（TTS 未就绪不阻塞 READY，3.5 v1.4）。"""
    assert required_engines_ready([("asr", True), ("tts", False), ("llm", True)]) is True


def test_required_engines_ready_missing_asr_blocks() -> None:
    assert required_engines_ready([("asr", False), ("tts", True), ("llm", True)]) is False


def test_required_engines_ready_missing_llm_blocks() -> None:
    assert required_engines_ready([("asr", True), ("llm", False)]) is False


def test_required_engines_ready_missing_entry_blocks() -> None:
    """hello 引擎清单缺必需条目 = 未就绪（防半张清单混过 gate）。"""
    assert required_engines_ready([("llm", True)]) is False


def test_required_engines_ready_empty_blocks() -> None:
    assert required_engines_ready([]) is False
