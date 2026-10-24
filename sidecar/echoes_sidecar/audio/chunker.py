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
# 首句短切时允许的最小头段（字符）：小于此值的碎片（"嗯，"）不切，保韵律
_MIN_HEAD_CHARS = 4

_POLICIES = ("punct", "none")


def split_sentences(
    text: str, policy: str = "punct", *, first_max_chars: int | None = None
) -> list[str]:
    """按策略切句（4.5）。

    - `punct`（默认）：按句末标点切分，标点与后置引号/括号随前句；
    - `none`：整段一句（给不自作聪明分句的引擎用）；
    - 其余策略名 → ValueError（3.2 报错而非降级：静默当 punct 会掩盖接线错误）。

    `first_max_chars`：**首句短切**上限（引擎注入，默认不启用）。本地 TTS 的
    RTF≈1（ADR-012 §4.1 实测），首音频块要等首句**合成完**才出——首句就是 4.2s
    音频，TTFA 就是 4.2s。给一个上限，头段在**次级停顿**处提前断一次（找不到
    停顿就不切，绝不硬切词），首句越短首音频越早。

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
            _flush(buffer, sentences, first_max_chars)
            continue
        index += 1
    _flush(buffer, sentences, first_max_chars)
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


def _flush(buffer: list[str], sentences: list[str], first_max_chars: int | None = None) -> None:
    """把缓冲落成句子：过长先按次级停顿切，仍过长再硬切（保证无文本丢失）。

    首句（`sentences` 仍为空时）若给了 `first_max_chars`，先尝试在次级停顿处
    提前断一刀——只影响第一句，后续句子仍按软上限走（避免整段碎成语音碎片）。
    """
    segment = "".join(buffer).strip()
    buffer.clear()
    if not segment:
        return
    head = None
    if first_max_chars is not None and not sentences:
        head = _split_head(segment, first_max_chars)
    if head is None:
        sentences.extend(piece for piece in _split_long(segment) if piece)
        return
    first, rest = head
    sentences.append(first)
    sentences.extend(piece for piece in _split_long(rest) if piece)


def _split_head(segment: str, limit: int) -> tuple[str, str] | None:
    """在 `limit` 字内找**最早的自然停顿**把首句断短；找不到返回 None（不硬切）。"""
    for index, char in enumerate(segment[:limit]):
        if char not in _SECONDARY:
            continue
        first = segment[: index + 1].strip()
        rest = segment[index + 1 :].strip()
        if len(first) >= _MIN_HEAD_CHARS and rest:
            return first, rest
        return None  # 最早的停顿太靠前（"哦，"），再切只会更碎：保持整句
    return None


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
