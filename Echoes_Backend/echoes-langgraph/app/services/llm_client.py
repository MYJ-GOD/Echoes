"""
LLM 客户端 - OpenAI 兼容端点统一通道

支持 DeepSeek / DashScope 等任意 OpenAI 兼容服务。
base_url / api_key / model / timeout 全部由环境变量配置（见 app/config.py），
切换 provider 只改 .env，不动代码。

- chat_completion: 非流式，返回完整文本
- chat_completion_stream: 流式，逐 delta content 产出
"""
import json
import logging
from typing import AsyncGenerator, Dict, List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _chat_completions_url() -> str:
    """拼接 /chat/completions 端点（容忍 base_url 已带 /v1）"""
    base = settings.LLM_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/chat/completions"


def _headers() -> Dict[str, str]:
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY 未配置（在 echoes-langgraph/.env 中设置）")
    return {"Authorization": f"Bearer {settings.LLM_API_KEY}"}


async def chat_completion(
    messages: List[Dict[str, str]],
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> str:
    """非流式对话补全，返回完整文本（strip 后）"""
    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            _chat_completions_url(), json=payload, headers=_headers()
        )
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


async def chat_completion_stream(
    messages: List[Dict[str, str]],
    max_tokens: int = 1024,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """流式对话补全，逐 delta content 产出（SSE data: 帧解析）"""
    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
        async with client.stream(
            "POST",
            _chat_completions_url(),
            json=payload,
            headers=_headers(),
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
