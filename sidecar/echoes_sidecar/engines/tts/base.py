"""TTSEngine 契约（文档 4.5 冻结）。

voice_id 是已解析的资产 ID（含 builtin:default，由编排层按 2.5 解析）；本契约不接受 None，
引擎内部不做状态机判断。分句：调用 audio/chunker 纯函数完成，策略由本引擎注入（4.5 v1.4）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.types import AudioChunk


class TTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_id: str) -> AsyncIterator[AudioChunk]:
        """流式产出音频 chunk（逐句合成、逐句产出；编排层不感知分句——4.5）。"""

    @abstractmethod
    async def clone(self, sample: AudioInputStream) -> str:
        """克隆（技术路线与兜底规则=ADR-009）→ voice_id + 资产目录内缓存文件。

        失败抛 CloneError（core.errors）；CLONE_QUALITY_LOW 由阶段 2 质检模块产出；
        用户取消 = CLONE_CANCELLED（3.4 clone_cancel）。调用方必须向 UI 报错并置
        音色 failed，禁止回退（4.5/2.5）。
        """
