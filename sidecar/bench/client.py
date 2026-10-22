"""真实 HTTP provider 客户端（Ollama / OpenAI 兼容），由 scripts/bench_llm.py 本机驱动。

不进 CI（无网络/模型依赖）；导出协议由测试注入 Fake 锁定。
首 token 延迟 = 首个非空内容 chunk 计时；tok/s：Ollama 取官方 eval 统计，
OpenAI 兼容按字符吞吐近似（辅指标，注明 approx）。
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx


class OllamaClient:
    """Ollama /api/chat 流式（NDJSON）。"""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        *,
        no_think: bool = False,
        temperature: float | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.no_think = no_think
        self.temperature = temperature  # None = Ollama 默认；judge 通道传 0（复现口径）

    async def chat(
        self, context: list[dict[str, str]], user: str, *, model: str
    ) -> dict[str, Any]:
        messages = [*context, {"role": "user", "content": user}]
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
        if self.no_think:
            body["think"] = False  # qwen3 等推理模型：语音场景须关 thinking（延迟）
        if self.temperature is not None:
            body["options"] = {"temperature": self.temperature}
        reply_parts: list[str] = []
        first_token_ms: int | None = None
        tok_s: float | None = None
        t0 = time.perf_counter()
        async with (
            httpx.AsyncClient(timeout=180) as client,
            client.stream("POST", f"{self.base_url}/api/chat", json=body) as resp,
        ):
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    if first_token_ms is None:
                        first_token_ms = int((time.perf_counter() - t0) * 1000)
                    reply_parts.append(content)
                if chunk.get("done"):
                    eval_count = chunk.get("eval_count")
                    eval_duration = chunk.get("eval_duration")
                    if eval_count and eval_duration:
                        tok_s = round(eval_count / (eval_duration / 1e9), 2)
        return {
            "reply": "".join(reply_parts),
            "first_token_ms": first_token_ms,
            "tok_s": tok_s,
            "model": model,
        }


class OpenAICompatClient:
    """OpenAI 兼容 /v1/chat/completions 流式（SSE），云端 DeepSeek 用。

    API key 从环境变量读取（DEEPSEEK_API_KEY），不硬编码（4.4 契约）。
    """

    def __init__(
        self,
        base_url: str = "https://api.deepseek.com",
        api_key: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.temperature = temperature  # None = API 默认；judge 通道传 0

    async def chat(
        self, context: list[dict[str, str]], user: str, *, model: str
    ) -> dict[str, Any]:
        messages = [*context, {"role": "user", "content": user}]
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
        if self.temperature is not None:
            body["temperature"] = self.temperature
        reply_parts: list[str] = []
        first_token_ms: int | None = None
        tok_s: float | None = None
        t0 = time.perf_counter()
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with (
            httpx.AsyncClient(timeout=180) as client,
            client.stream(
                "POST", f"{self.base_url}/v1/chat/completions", json=body, headers=headers
            ) as resp,
        ):
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                delta = (chunk.get("choices") or [{}])[0].get("delta", {})
                content = delta.get("content") or ""
                if content:
                    if first_token_ms is None:
                        first_token_ms = int((time.perf_counter() - t0) * 1000)
                    reply_parts.append(content)
        elapsed = time.perf_counter() - t0
        if reply_parts and elapsed > 0:
            tok_s = round(len("".join(reply_parts)) / elapsed, 2)  # approx：字符吞吐近似
        return {
            "reply": "".join(reply_parts),
            "first_token_ms": first_token_ms,
            "tok_s": tok_s,
            "model": model,
        }
