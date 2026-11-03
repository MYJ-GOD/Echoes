"""TTSEngine 契约（文档 4.5 冻结）。

voice_id 是已解析的资产 ID（含 builtin:default，由编排层按 2.5 解析）；本契约不接受 None，
引擎内部不做状态机判断。分句：调用 audio/chunker 纯函数完成，策略由本引擎注入（4.5 v1.4）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from echoes_sidecar.audio.stream import AudioInputStream
from echoes_sidecar.core.types import AudioChunk


@runtime_checkable
class TtsRuntimeConfigurable(Protocol):
    """可选能力（R2a 2.5）：turn 边界按设置切换 TTS provider。

    与 LLM 的 `RuntimeConfigurable` 同构：编排层只认 Protocol，不认识
    `TtsRouter` 这个具体类（3.2 装配清单门禁）。
    """

    async def apply(
        self,
        *,
        provider: str | None,
        model: str | None,
        base_url: str | None = None,
        allow_cloud: bool = True,
    ) -> None: ...

    @property
    def current(self) -> tuple[str, str]: ...


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

    # ---- 可选能力：说话人相似度质检（4.5 v1.4.4 追加，阶段 2） ----
    # 之前是编排层 `getattr(tts, "speaker_similarity", None)` 的鸭子探测：能力靠
    # 实现细节约定，改名/删方法都是静默降级（质检悄悄消失）。改成显式能力位后，
    # 「支持质检」是一个契约事实，实现方必须同时覆盖属性与方法。

    @property
    def supports_similarity_check(self) -> bool:
        """能否做原样本 vs 克隆音色的相似度质检（默认不支持：mock/纯合成引擎）。"""
        return False

    async def speaker_similarity(self, sample_pcm: bytes, synth_pcm: bytes) -> float:
        """说话人相似度（0–1，campplus 余弦一类的口径）。

        只在 `supports_similarity_check` 为真时被调用；默认实现直接报错，
        避免「能力位说支持、调用时静默返回 0」这种假通过。
        """
        raise NotImplementedError("该 TTS 引擎未实现说话人相似度质检")

    # ---- 可选能力：情感/风格指令（R2b 2b.6，为 R4 4.7 表达铺路） ----
    # 编排层每轮按情绪设置一次，引擎把它翻译成自己的 instruct 参数；
    # 默认引擎不支持时能力位为假，编排层不调用，避免「设了但没生效」的假象。

    @property
    def supports_instruction(self) -> bool:
        """能否接受自然语言风格/情感指令（默认不支持：mock/云端固定音色）。"""
        return False

    def set_instruction(self, text: str | None) -> None:
        """设置本轮风格指令（None = 回到默认语气）。默认实现忽略。"""
        _ = text


__all__ = ["TTSEngine", "TtsRuntimeConfigurable"]
