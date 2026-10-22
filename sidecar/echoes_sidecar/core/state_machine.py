"""3.5 统一应用状态机（冻结）：state 归 sidecar 所有，壳/UI 只是渲染者。

合法迁移以 tests/fixtures/state_transitions.json 为机器可读 fixture（13.2-4），
本文件保持与之对拍的运行时镜像；两边漂移=红。
"""
from __future__ import annotations

from enum import StrEnum


class AppState(StrEnum):
    """状态集合（3.5）：booting | ready | generating | speaking | error。"""

    BOOTING = "booting"
    READY = "ready"
    GENERATING = "generating"
    SPEAKING = "speaking"
    ERROR = "error"


# booting→ready 的必需引擎集合 = {ASR, LLM}；TTS 就绪不改状态机（3.5 v1.4）
LEGAL_TRANSITIONS: dict[AppState, frozenset[AppState]] = {
    AppState.BOOTING: frozenset({AppState.READY, AppState.ERROR}),
    AppState.ERROR: frozenset({AppState.BOOTING}),  # 唯一出口：壳按 14.1 重启→hello→booting
    AppState.READY: frozenset({AppState.GENERATING}),
    AppState.GENERATING: frozenset(
        {AppState.SPEAKING, AppState.READY, AppState.GENERATING}  # FAILED 无音频 / 重入
    ),
    AppState.SPEAKING: frozenset({AppState.READY, AppState.GENERATING}),  # 播完 / 重入
}


class IllegalTransitionError(Exception):
    """非法迁移（3.5 规则行：出现即 sidecar 自身 bug，按 INTERNAL_ERROR 上报并写日志）。"""

    def __init__(self, from_state: AppState, to_state: AppState) -> None:
        super().__init__(f"非法迁移: {from_state.value} -> {to_state.value}")
        self.from_state = from_state
        self.to_state = to_state


def is_legal(from_state: AppState, to_state: AppState) -> bool:
    """3.5 合法迁移判定（纯函数，供 fixture 对拍与状态机共用）。"""
    return to_state in LEGAL_TRANSITIONS.get(from_state, frozenset())


class StateMachine:
    """sidecar 状态机：transition() 校验合法迁移，非法抛 IllegalTransitionError。

    非致命错误不进状态机（只发 error 事件，见 3.5 v1.4 error 吸收态定义）。
    """

    def __init__(self) -> None:
        self.state: AppState = AppState.BOOTING

    def transition(self, to_state: AppState) -> AppState:
        """迁移并返回新状态；非法迁移抛 IllegalTransitionError 且原地不动。"""
        from_state = self.state
        if not is_legal(from_state, to_state):
            raise IllegalTransitionError(from_state, to_state)
        self.state = to_state
        return to_state
