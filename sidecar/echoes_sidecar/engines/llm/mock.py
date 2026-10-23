"""mock LLM：契约测试与无云端/本地模型依赖开发的基础设施（文档 §12 步骤 2）。"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

from echoes_sidecar.engines.llm.base import LLMProvider

# 片间时延注入（13.3「打断基准自动化」）：三跳打断/延迟预算的自动化用例需要
# 一个"能被卡住"的 mock——真实引擎的耗时不可控，mock 不注入就没法断言预算是
# 否达成。默认 0（不影响任何既有用例），只在显式设环境变量时生效。
CHUNK_DELAY_ENV = "ECHOES_MOCK_CHUNK_DELAY_MS"


def chunk_delay_seconds() -> float:
    """片间时延（秒）：读环境变量，非法值按 0 处理（mock 不做报错仪式）。"""
    raw = os.environ.get(CHUNK_DELAY_ENV, "").strip()
    if not raw:
        return 0.0
    try:
        return max(0.0, float(raw)) / 1000.0
    except ValueError:
        return 0.0


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
        delay = chunk_delay_seconds()
        if delay:
            await asyncio.sleep(delay)  # 三跳打断的窗口（13.3）
        yield "骨架装配正常，可以开始聊了。"


__all__ = ["CHUNK_DELAY_ENV", "MockLLMProvider", "chunk_delay_seconds"]
