"""OllamaLLMProvider：4.4 契约实现测试（阶段 0 第二周-1）。

口径：
- /api/chat NDJSON 流式 → 逐片 yield `message.content`（不聚合，片序保真）。
- stream=False → 非流式请求，全量文本单片 yield（iterator 契约不破）。
- health() = GET /api/tags（供 Settings 页展示）。
- think 开关为能力协商位（ADR-001 结论 3）：qwen3 系必须 False，2.5 系 None 不传字段。
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from echoes_sidecar.engines.llm.ollama import OllamaLLMProvider


def _ndjson(*objects: dict[str, Any]) -> bytes:
    return "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in objects).encode()


def _chat_body(request: httpx.Request) -> dict[str, Any]:
    return json.loads(request.read())


@pytest.fixture
def provider_factory():
    """注入 MockTransport 的 provider 工厂：按 path 配响应，记录收到的 body。"""

    def make(
        chat_content: bytes,
        tags_status: int = 200,
        chat_status: int = 200,
    ) -> tuple[OllamaLLMProvider, list[httpx.Request]]:
        seen: list[httpx.Request] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            if request.url.path == "/api/chat":
                return httpx.Response(chat_status, content=chat_content)
            if request.url.path == "/api/tags":
                return httpx.Response(tags_status, json={"models": []})
            return httpx.Response(404, json={"error": "no route"})

        transport = httpx.MockTransport(handler)
        provider = OllamaLLMProvider(
            model="qwen3:8b",
            transport=transport,
        )
        provider._seen = seen  # type: ignore[attr-defined]  # 测试观测点
        provider._transport = transport  # type: ignore[attr-defined]  # 测试观测点
        return provider, seen

    return make


@pytest.mark.asyncio
async def test_generate_yields_content_chunks_in_order(provider_factory) -> None:
    body = _ndjson(
        {"message": {"role": "assistant", "content": "星期"}, "done": False},
        {"message": {"role": "assistant", "content": "天见"}, "done": True},
    )
    provider, _ = provider_factory(body)
    chunks = [c async for c in provider.generate([{"role": "user", "content": "hi"}])]
    assert chunks == ["星期", "天见"]


@pytest.mark.asyncio
async def test_generate_full_reply_single_piece_when_not_stream(provider_factory) -> None:
    body = _ndjson(
        {"message": {"role": "assistant", "content": "整句回复"}, "done": True},
    )
    provider, seen = provider_factory(body)
    chunks = [
        c
        async for c in provider.generate(
            [{"role": "user", "content": "hi"}], stream=False
        )
    ]
    assert chunks == ["整句回复"]
    assert json.loads(seen[-1].read())["stream"] is False


@pytest.mark.asyncio
async def test_generate_carries_messages_and_options(provider_factory) -> None:
    body = _ndjson({"message": {"content": "ok"}, "done": True})
    provider, seen = provider_factory(body)
    _ = [
        c
        async for c in provider.generate(
            [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}],
            temperature=0.2,
            max_tokens=64,
        )
    ]
    parsed = json.loads(seen[-1].read())
    assert parsed["messages"][0] == {"role": "system", "content": "sys"}
    assert parsed["options"] == {"temperature": 0.2, "num_predict": 64}
    assert "think" not in parsed  # 未协商=不传字段（2.5 系兼容）


@pytest.mark.asyncio
async def test_think_false_negotiated(provider_factory) -> None:
    """ADR-001：qwen3 系必须 think:false——能力协商位显式传 body（410 前提）。"""
    body = _ndjson({"message": {"content": "ok"}, "done": True})
    provider, seen = provider_factory(body)
    p = OllamaLLMProvider(model="qwen3:8b", think=False, transport=provider._transport)  # type: ignore[attr-defined]
    _ = [c async for c in p.generate([{"role": "user", "content": "hi"}])]
    assert json.loads(seen[-1].read())["think"] is False


@pytest.mark.asyncio
async def test_health_true_on_tags_200(provider_factory) -> None:
    provider, _ = provider_factory(b"")
    assert await provider.health() is True


@pytest.mark.asyncio
async def test_health_false_on_tags_error(provider_factory) -> None:
    provider, _ = provider_factory(b"", tags_status=503)
    assert await provider.health() is False
