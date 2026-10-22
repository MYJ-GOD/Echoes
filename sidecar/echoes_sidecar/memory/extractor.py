"""memory extractor：turn 结束后异步抽取事实（文档 5.2）。

独立线程执行（3.2 执行约束）；抽取 provider 必须跟随当前全局模式，隐私模式下绝不出网；
质量以 13.3 评测集守护：precision ≥0.85 / recall ≥0.7 / 替代正确率 ≥0.9（阈值随阶段 1 校准）。
"""
from __future__ import annotations


class MemoryExtractor:
    """阶段 1 接线；阶段 0 不存储原始全文（5.2 最后一行）。"""

    async def extract(self, profile_id: str, transcript: str) -> list[dict[str, str]]:
        """抽取 {"fact", "category"} 列表；category ∈ preference|event|identity|other（5.1）。"""
        _ = (profile_id, transcript)
        raise NotImplementedError("阶段 1 接线（13.3 门禁挂钩；隐私模式语义见 4.4/6-风险 12）")
