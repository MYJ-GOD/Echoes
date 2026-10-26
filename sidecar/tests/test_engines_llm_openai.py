"""OpenAI 兼容 LLM（ADR-016）：SSE 流式、缺 key、鉴权失败、key 热更新。"""
from __future__ import annotations

import json

import httpx
import pytest

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.engines.llm.openai_compat import OpenAICompatibleLLM

BASE = "https://api.example.test/v1"


def _sse(*pieces: str, done: bool = True) -> bytes:
    lines: list[str] = []
    for piece in pieces:
        chunk = {
            "choices": [{"delta": {"content": piece}, "index": 0}]
        }
        lines.append(f"data: {json.dumps(chunk, ensure_ascii=False)}")
    if done:
        lines.append("data: [DONE]")
    return ("\n\n".join(lines) + "\n\n").encode("utf-8")


def _client(handler, *, key: str | None = "sk-test") -> OpenAICompatibleLLM:
    return OpenAICompatibleLLM(
        "gpt-test",
        base_url=BASE,
        api_key=key,
        transport=httpx.MockTransport(handler),
    )


async def test_stream_yields_pieces_until_done() -> None:
    seen_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("authorization", ""))
        body = json.loads(request.content)
        assert body["stream"] is True
        assert body["messages"] == [{"role": "user", "content": "在吗"}]
        return httpx.Response(
            200,
            content=_sse("你", "好", "呀"),
            headers={"content-type": "text/event-stream"},
        )

    llm = _client(handler)
    pieces = [
        piece
        async for piece in llm.generate([{"role": "user", "content": "在吗"}])
    ]

    assert pieces == ["你", "好", "呀"]
    assert seen_auth == ["Bearer sk-test"]
    await llm.aclose()


async def test_non_stream_returns_single_piece() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is False
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "整段回复"}}
                ]
            },
        )

    llm = _client(handler)
    pieces = [
        piece
        async for piece in llm.generate(
            [{"role": "user", "content": "hi"}], stream=False
        )
    ]
    assert pieces == ["整段回复"]
    await llm.aclose()


async def test_missing_key_raises_contract_error() -> None:
    llm = _client(lambda request: httpx.Response(200), key=None)
    with pytest.raises(EchoesError) as excinfo:
        async for _ in llm.generate([{"role": "user", "content": "hi"}]):
            pass
    assert excinfo.value.code is ErrorCode.LLM_KEY_MISSING
    await llm.aclose()


async def test_key_provider_is_read_per_request() -> None:
    """设置页刚保存的 key 下一轮就生效：不缓存、不重建 provider。"""
    keys = iter(["sk-first", "sk-second"])
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["authorization"])
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, content=_sse("好"))

    llm = OpenAICompatibleLLM(
        "m",
        base_url=BASE,
        key_provider=lambda: next(keys, None),
        transport=httpx.MockTransport(handler),
    )
    assert await llm.health() is True
    async for _ in llm.generate([{"role": "user", "content": "hi"}]):
        pass
    assert seen == ["Bearer sk-first", "Bearer sk-second"]
    await llm.aclose()


async def test_401_maps_to_provider_unavailable() -> None:
    llm = _client(
        lambda request: httpx.Response(401, text='{"error": "invalid api key"}')
    )
    with pytest.raises(EchoesError) as excinfo:
        async for _ in llm.generate([{"role": "user", "content": "hi"}]):
            pass
    assert excinfo.value.code is ErrorCode.LLM_PROVIDER_UNAVAILABLE
    assert "401" in excinfo.value.message
    await llm.aclose()


async def test_429_and_5xx_are_reported() -> None:
    for status in (429, 503):
        llm = _client(lambda request, status=status: httpx.Response(status, text="busy"))
        with pytest.raises(EchoesError) as excinfo:
            async for _ in llm.generate([{"role": "user", "content": "hi"}]):
                pass
        assert excinfo.value.code is ErrorCode.LLM_PROVIDER_UNAVAILABLE
        await llm.aclose()


async def test_malformed_sse_lines_are_ignored() -> None:
    payload = (
        b": keep-alive\n\n"
        b"data: not-json\n\n"
        b'data: {"choices": []}\n\n'
        + _sse("ok")
    )

    llm = _client(
        lambda request: httpx.Response(
            200, content=payload, headers={"content-type": "text/event-stream"}
        )
    )
    pieces = [piece async for piece in llm.generate([{"role": "user", "content": "hi"}])]
    assert pieces == ["ok"]
    await llm.aclose()


async def test_health_requires_key() -> None:
    llm = _client(lambda request: httpx.Response(200, json={"data": []}), key=None)
    assert await llm.health() is False
    await llm.aclose()


async def test_name_marks_cloud_vs_local_endpoint() -> None:
    """4.4 的 `cloud:` 前缀决定摘要/抽取是否被压住：本机端点不该被当成出网。"""
    cloud = _client(lambda request: httpx.Response(200))
    assert cloud.name == "cloud:openai"
    await cloud.aclose()

    local = OpenAICompatibleLLM(
        "m",
        base_url="http://127.0.0.1:1234/v1",
        api_key="sk-local",
        transport=httpx.MockTransport(lambda request: httpx.Response(200)),
    )
    assert local.name == "openai"
    await local.aclose()
