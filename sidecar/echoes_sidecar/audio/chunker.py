"""4.5 分句纯函数模块（v1.4 定案）：零引擎依赖、可 L1 独立单测（13.1）。

策略由 TTSEngine 注入（默认标点级）；本模块不感知引擎路线（ADR-009）。
空实现：阶段 0 第二周随 TTS 接线（文档 §12 步骤 4）。
"""
from __future__ import annotations


def split_sentences(text: str, policy: str = "punct") -> list[str]:
    """按策略切句（policy=分句策略名，由引擎入参传入，4.5）。

    报错而非降级（3.2）：骨架期不做静默假实现。
    """
    _ = (text, policy)
    raise NotImplementedError("阶段 0 第二周接线（文档 §12 步骤 4；L1 对象见 13.1）")


__all__ = ["split_sentences"]
