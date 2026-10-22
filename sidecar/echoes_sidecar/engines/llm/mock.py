"""mock LLM：契约测试与无云端/本地模型依赖开发的基础设施（文档 §12 步骤 2）。"""
from __future__ import annotations

from collections.abc import AsyncIterator

from echoes_sidecar.engines.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """恒定产出两段 token 片段；为第一周「文本→LLM→文本」提供无模型闭环（12.3）。"""

    @property
    def name(self) -> str:
        return "mock"

    async def health(self) -> bool:
        return True

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        _ = (messages, stream, max_tokens, temperature)
        yield "（mock 回复）"
        yield "骨架装配正常，可以开始聊了。"


__all__ = ["MockLLMProvider"]
