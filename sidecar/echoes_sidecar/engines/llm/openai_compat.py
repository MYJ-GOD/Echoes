"""OpenAI 兼容 LLMProvider（4.4）：一套客户端覆盖云端与本地兼容端点。

适用：OpenAI、DeepSeek、Kimi、智谱、硅基流动等云服务，以及 Ollama `/v1`、
LM Studio、vLLM、llama.cpp server 等本地服务——差异只在 `base_url` 与 key。

口径：
- `/chat/completions` SSE 流式，逐片产出 `choices[0].delta.content`；
  `stream=False` 走非流式并以单片产出全量（iterator 契约不破）。
- **key 在请求时才读**（注入 `key_provider`）：设置页刚保存的 key 下一轮就生效，
  不必重建 provider。缺 key 抛 `LLM_KEY_MISSING`（不降级到 mock，3.4.1）。
- HTTP/鉴权失败统一折成 `EchoesError`：编排层只认契约错误码（4.4）。
- 隐私边界不在这里判断：云端 base_url 的出网许可归编排层/设置（5.2）。
"""

from __future__ import annotations

import json
import sys
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.engines.llm.base import LLMProvider

KeyProvider = Callable[[], str | None]


class OpenAICompatibleLLM(LLMProvider):
    """`/v1/chat/completions` 客户端（base_url 填到 `/v1` 为止）。"""

    def __init__(
        self,
        model: str,
        *,
        base_url: str,
        api_key: str | None = None,
        key_provider: KeyProvider | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self._api_key = api_key
        self._key_provider = key_provider
        self._cloud = not is_loopback(base_url)
        self._client = httpx.AsyncClient(
            base_url=base_url.strip().rstrip("/"),
            transport=transport,
            timeout=httpx.Timeout(timeout, connect=5.0),
        )

    @property
    def name(self) -> str:
        """`cloud:openai` 会出网；本机兼容端点（LM Studio/vLLM）仍报 `openai`。

        4.4 的 `cloud:` 前缀是摘要/记忆抽取判断「要不要压住」的依据，不能一律加。
        """
        return "cloud:openai" if self._cloud else "openai"

    async def health(self) -> bool:
        """`GET /models` 探测可达与鉴权；不带 key 直接判不可用（不发无意义请求）。"""
        key = self._key()
        if not key:
            return False
        try:
            resp = await self._client.get(
                "/models", headers={"Authorization": f"Bearer {key}"}
            )
        except httpx.HTTPError as exc:
            print(f"[sidecar] 云端 LLM 不可达：{exc}", file=sys.stderr)
            return False
        if resp.status_code == 401:
            print("[sidecar] 云端 LLM 鉴权失败（401）：检查 API key", file=sys.stderr)
        return resp.status_code == 200

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        key = self._key()
        if not key:
            raise EchoesError(
                ErrorCode.LLM_KEY_MISSING,
                "尚未配置云端 LLM 的 API key（设置 → 引擎）",
            )
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {key}"}

        if not stream:
            payload = await self._request("/chat/completions", body, headers)
            yield _content(payload)
            return

        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=body, headers=headers
            ) as resp:
                await _raise_for_status(resp)
                async for line in resp.aiter_lines():
                    done, piece = _sse_piece(line)
                    if done:
                        return
                    if piece:
                        yield piece
        except httpx.HTTPError as exc:
            raise _transport_error(exc) from exc

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------ 内部 ------------------------------

    def _key(self) -> str | None:
        if self._api_key:
            return self._api_key
        if self._key_provider is None:
            return None
        value = self._key_provider()
        return value or None

    async def _request(
        self, path: str, body: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        try:
            resp = await self._client.post(path, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise _transport_error(exc) from exc
        await _raise_for_status(resp)
        data: dict[str, Any] = resp.json()
        return data


class _Done:
    """SSE 结束哨兵（区别于空片段）。"""


_DONE = _Done()


def _sse_piece(line: str) -> tuple[bool, str]:
    """一行 SSE → (是否结束, 文本片段)；注释、空行、坏 JSON 都按空片段忽略。"""
    text = line.strip()
    if not text or text.startswith(":") or not text.startswith("data:"):
        return False, ""
    payload = text[len("data:") :].strip()
    if payload == "[DONE]":
        return True, ""
    try:
        event = json.loads(payload)
    except ValueError:
        return False, ""
    if not isinstance(event, dict):
        return False, ""
    choices = event.get("choices")
    if not isinstance(choices, list) or not choices:
        return False, ""
    first = choices[0]
    if not isinstance(first, dict):
        return False, ""
    delta = first.get("delta")
    if not isinstance(delta, dict):
        return False, ""
    content = delta.get("content")
    return False, content if isinstance(content, str) else ""


def _content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    return content if isinstance(content, str) else ""


async def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    # 流式响应尚未读体：不 aread 直接取 text 会抛 ResponseNotRead
    detail = ""
    try:
        detail = (await resp.aread()).decode("utf-8", "replace")[:200]
    except Exception:  # noqa: BLE001  错误详情拿不到也不能盖掉状态码
        detail = ""
    if resp.status_code == 401:
        raise EchoesError(
            ErrorCode.LLM_PROVIDER_UNAVAILABLE,
            "云端 LLM 鉴权失败（401）：检查 API key 是否正确/过期",
        )
    if resp.status_code == 429:
        raise EchoesError(
            ErrorCode.LLM_PROVIDER_UNAVAILABLE, "云端 LLM 限流（429）：稍后再试"
        )
    raise EchoesError(
        ErrorCode.LLM_PROVIDER_UNAVAILABLE,
        f"云端 LLM 返回 HTTP {resp.status_code}：{detail}",
    )


def _transport_error(exc: httpx.HTTPError) -> EchoesError:
    return EchoesError(
        ErrorCode.LLM_PROVIDER_UNAVAILABLE, f"云端 LLM 请求失败：{exc}"
    )


def is_loopback(base_url: str | None) -> bool:
    """本机端点判定：LM Studio/vLLM/Ollama `/v1` 不该被当成出网。

    ADR-016 §3 隐私矩阵的判据之一：`openai` + 环回地址在隐私模式下**允许**
    （不出网）；空值/解析失败按出网处理（保守，宁拒勿放）。
    """
    if not base_url:
        return False
    try:
        host = httpx.URL(base_url).host
    except Exception:  # noqa: BLE001  解析不了就按出网处理（保守）
        return False
    return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


__all__ = ["OpenAICompatibleLLM", "is_loopback"]
