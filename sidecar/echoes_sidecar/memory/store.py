"""memory store：sqlite-vec 检索与事实写入（文档 5.1/5.2）。

检索时机（5.2）：每轮 turn 开始前，用用户输入 query 检索 top-k 相关 fact
（sqlite-vec 暴力扫描，k=5~8）拼进 system prompt。
"""
from __future__ import annotations


class MemoryStore:
    """阶段 0 第二周接线（文档 §12 步骤 4）；默认档 bge-small-zh 512 维（ADR-006）。"""

    async def retrieve(self, profile_id: str, query: str, *, k: int = 5) -> list[dict[str, str]]:
        """按向量相似度检索 top-k 事实（q：fact 文本域）。"""
        _ = (profile_id, query)
        raise NotImplementedError("阶段 0 第二周接线（文档 §12 步骤 4；表见 5.1）")
