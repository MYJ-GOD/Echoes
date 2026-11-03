"""L1 错误码映射（13.1）：3.4.1 的 14 条 + ADR-016 的 LLM_KEY_MISSING + CloneError（4.5）。"""
from __future__ import annotations

from echoes_sidecar.core.errors import CloneError, EchoesError, ErrorCode


def test_error_code_values_are_frozen_list() -> None:
    """code 值域经 test_ipc_schema 单测锁定；此处锁定枚举数量不增不减。"""
    assert len(ErrorCode) == 16


def test_history_write_failure_has_dedicated_code() -> None:
    """原文写入失败不能伪装成普通 STORAGE_ERROR；UI 要能单独提示「未保存」。"""
    assert ErrorCode.HISTORY_WRITE_FAILED.value == "HISTORY_WRITE_FAILED"


def test_clone_error_carries_code_and_cancellation() -> None:
    """CloneError(CLONE_CANCELLED) = 用户取消 → 音色落 failed 非绑定回退（2.5/3.4）。"""
    error = CloneError(ErrorCode.CLONE_CANCELLED, "用户中途取消", fatal=False)
    assert error.code is ErrorCode.CLONE_CANCELLED
    assert error.fatal is False


def test_fatal_flag_prints_code_in_detail() -> None:
    """fatal=True 表示进入 3.5 error 吸收态（14.1 处置）。"""
    error = EchoesError(ErrorCode.INTERNAL_ERROR, "兜底", fatal=True)
    assert error.fatal is True
    assert "INTERNAL_ERROR" in str(error)
