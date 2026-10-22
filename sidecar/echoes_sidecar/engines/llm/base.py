"""LLMProvider 契约（文档 4.4 冻结）。

约束（4.4 原文）：
- 编排层只接受 messages 结构，不暴露 provider 特有字段；返回流式 token 片段，
  不暴露 logits 或 provider 原生 chunk。
- 上下文预算归编排层：provider 收到的 messages 永远已合预算，接口不提供截断参数。
- 云端 provider 的 API key 从 Settings 读取，不硬编码、不入库明文。
- 隐私模式约束覆盖全部经此 provider 的调用，包括 5.2 记忆抽取；抽取出网即违反 2.2。
- 唯一保留项：ADR-001 定稿后对 provider 抽象做一次复核（12.2）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, str]],  # [{"role": "system|user|assistant", "content": "..."}]
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """流式产出 token 片段（4.4）。"""

    @abstractmethod
    async def health(self) -> bool:
        """provider 可用性检查（供 Settings 页展示，4.4）。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """'ollama' / 'cloud:deepseek' 等（4.4；llama_cpp 条款见 engines/llm/__init__）。"""
