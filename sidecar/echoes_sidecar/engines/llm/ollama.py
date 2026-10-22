"""Ollama 本地 LLMProvider（4.4 契约实现；阶段 0 第二周-1）。

口径（ADR-001 结论 3 能力协商位）：
- think 开关：qwen3 系必须 `think=false`（语音场景首 token 硬前提），
  None = 不传字段（qwen2.5 等原生指令模型兼容不做协商）。
- /api/chat NDJSON 流式，逐行产出 `message.content` 片段的 AsyncIterator；
  stream=False 走非流式请求并以单片产出全量文本（iterator 契约不破）。
- 隐私模式（4.4）：本 provider 恒本地（127.0.0.1），身份上不触隐私边界；
  但仍接受调用方在编排层预过滤（provider 不感知隐私开关，5.2 归属）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from echoes_sidecar.engines.llm.base import LLMProvider


class OllamaLLMProvider(LLMProvider):
    """Ollama /api/chat 客户端（base_url 默认本机 11434）。"""

    def __init__(
        self,
        model: str,
        *,
        base_url: str = "http://127.0.0.1:11434",
        think: bool | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.think = think
        self._client = httpx.AsyncClient(
            base_url=base_url.strip("/"),
            transport=transport,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )

    @property
    def name(self) -> str:
        return "ollama"

    async def health(self) -> bool:
        try:
            resp = await self._client.get("/api/tags")
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if self.think is not None:  # 能力协商位：None 不传字段
            body["think"] = self.think

        if not stream:
            resp = await self._client.post("/api/chat", json=body)
            resp.raise_for_status()
            reply = resp.json()["message"]["content"]
            yield reply
            return

        async with self._client.stream("POST", "/api/chat", json=body) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                event = _ndjson_event(line)
                piece = event.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if event.get("done"):
                    return

    async def aclose(self) -> None:
        await self._client.aclose()


def _ndjson_event(line: str) -> dict[str, Any]:
    """单行 NDJSON → dict；坏行/非 dict 视为空事件（忽略不崩，3.4 同款姿态）。"""
    try:
        parsed: dict[str, Any] = json.loads(line)
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        return {}


__all__ = ["OllamaLLMProvider"]
