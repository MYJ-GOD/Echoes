"""4.5 分句纯函数模块（v1.4 定案）：零引擎依赖、可 L1 独立单测（13.1）。

策略由 TTSEngine 注入（4.5「分句策略作为入参由引擎注入」）；本模块不感知引擎路线（ADR-009）。

为什么需要它：CosyVoice2 目前整段 `inference_zero_shot` 一把出音频，TTFA 实测 3.7s
（a5ccc75），验收预算 P50 ≤2.5s。逐句合成 + 首句先出是缩小 TTFA 的主要杠杆，
前提是先有稳定、可测的句切（本模块）；接线由引擎侧完成，编排层仍只消费 chunk 流。
"""
from __future__ import annotations

# 句末终止符：中英标点 + 换行（换行在陪伴场景里等价于语义停顿）
_PRIMARY = frozenset("。！？；!?;…\n")
# 终止符后紧跟的收尾符号，必须并入同一句（否则切出 " 」" 这类碎片）
_CLOSERS = frozenset("”’」』）)】》〉\"'")
# 次级停顿：仅当单句过长时才用（避免一句 200 字把首音频块拖死）
_SECONDARY = frozenset("，、：,:")
# 单句软上限（字符）：超过先按次级停顿切，仍超则硬切
_SOFT_MAX_CHARS = 60

_POLICIES = ("punct", "none")


def split_sentences(text: str, policy: str = "punct") -> list[str]:
    """按策略切句（4.5）。

    - `punct`（默认）：按句末标点切分，标点与后置引号/括号随前句；
    - `none`：整段一句（给不自作聪明分句的引擎用）；
    - 其余策略名 → ValueError（3.2 报错而非降级：静默当 punct 会掩盖接线错误）。

    返回已 strip 的非空句列表；空输入返回 `[]`（调用方不必判空串）。
    """
    if policy not in _POLICIES:
        raise ValueError(f"未知分句策略：{policy!r}（4.5 支持 {'/'.join(_POLICIES)}）")

    stripped = text.strip()
    if not stripped:
        return []
    if policy == "none":
        return [stripped]

    sentences: list[str] = []
    buffer: list[str] = []
    index = 0
    length = len(stripped)
    while index < length:
        char = stripped[index]
        buffer.append(char)
        if _is_terminator(stripped, index):
            index += 1
            # 收尾符号与连写标点并入本句：`他说：「好。」` 的 」、
            # `我……算了` 的第二个 … 都不该切到下一句
            while index < length and (
                stripped[index] in _CLOSERS or stripped[index] in _PRIMARY
            ):
                buffer.append(stripped[index])
                index += 1
            _flush(buffer, sentences)
            continue
        index += 1
    _flush(buffer, sentences)
    return sentences


def _is_terminator(text: str, index: int) -> bool:
    """该位置是否句末（`.` 夹在数字中间视作小数点，不切）。"""
    char = text[index]
    if char in _PRIMARY:
        return True
    if char == ".":
        prev_char = text[index - 1] if index > 0 else ""
        next_char = text[index + 1] if index + 1 < len(text) else ""
        return not (prev_char.isdigit() and next_char.isdigit())
    return False


def _flush(buffer: list[str], sentences: list[str]) -> None:
    """把缓冲落成句子：过长先按次级停顿切，仍过长再硬切（保证无文本丢失）。"""
    segment = "".join(buffer).strip()
    buffer.clear()
    if not segment:
        return
    sentences.extend(piece for piece in _split_long(segment) if piece)


def _split_long(segment: str) -> list[str]:
    if len(segment) <= _SOFT_MAX_CHARS:
        return [segment]

    pieces: list[str] = []
    buffer: list[str] = []
    for char in segment:
        buffer.append(char)
        if char in _SECONDARY or len(buffer) >= _SOFT_MAX_CHARS:
            piece = "".join(buffer).strip()
            if piece:
                pieces.append(piece)
            buffer.clear()
    tail = "".join(buffer).strip()
    if tail:
        pieces.append(tail)
    return pieces


__all__ = ["split_sentences"]
