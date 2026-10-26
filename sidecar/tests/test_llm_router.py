"""ProviderRouter（3.4 拉取）：切换、关闭旧实例、未知 provider 不降级。"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from echoes_sidecar.core.errors import EchoesError, ErrorCode
from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.engines.llm.router import ProviderRouter
from echoes_sidecar.memory.extractor import MemoryExtractor


class FakeLLM(LLMProvider):
    def __init__(self, name: str) -> None:
        self._name = name
        self.calls: list[list[dict[str, str]]] = []
        self.closed = False

    @property
    def name(self) -> str:
        return self._name

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
        _ = (stream, max_tokens, temperature)
        self.calls.append(messages)
        yield f"{self._name}回复"

    async def aclose(self) -> None:
        self.closed = True


class Factory:
    def __init__(self) -> None:
        self.created: list[tuple[str, str, str | None, FakeLLM]] = []

    def __call__(
        self, provider: str, model: str, base_url: str | None = None
    ) -> LLMProvider:
        instance = FakeLLM(provider)
        self.created.append((provider, model, base_url, instance))
        return instance


async def test_apply_switches_provider_and_closes_old() -> None:
    initial = FakeLLM("mock")
    factory = Factory()
    router = ProviderRouter(initial, factory, provider="mock", model="m")

    await router.apply(provider="ollama", model="qwen3:8b")

    assert router.name == "ollama"
    assert [(p, m) for p, m, _, _ in factory.created] == [("ollama", "qwen3:8b")]
    assert initial.closed is True


async def test_apply_switches_on_base_url_change() -> None:
    initial = FakeLLM("openai")
    factory = Factory()
    router = ProviderRouter(initial, factory, provider="openai", model="m")

    await router.apply(
        provider="openai", model="m", base_url="https://example.test/v1"
    )

    assert [(p, u) for p, _, u, _ in factory.created] == [
        ("openai", "https://example.test/v1")
    ]


async def test_privacy_mode_blocks_cloud_without_silent_fallback() -> None:
    """隐私模式下云端 provider 不放行：generate 报错，而不是偷偷用本地（16.1）。"""
    initial = FakeLLM("mock")
    router = ProviderRouter(
        initial, Factory(), provider="openai", model="gpt-x", base_url="https://x/v1"
    )
    await router.apply(
        provider="openai", model="gpt-x", base_url="https://x/v1", allow_cloud=False
    )

    with pytest.raises(EchoesError) as excinfo:
        async for _ in router.generate([{"role": "user", "content": "hi"}]):
            pass

    assert excinfo.value.code is ErrorCode.LLM_PROVIDER_UNAVAILABLE
    assert initial.calls == []


async def test_apply_same_config_does_not_rebuild() -> None:
    initial = FakeLLM("ollama")
    factory = Factory()
    router = ProviderRouter(initial, factory, provider="ollama", model="qwen3:8b")

    await router.apply(provider="ollama", model="qwen3:8b")

    assert factory.created == []
    assert initial.closed is False


async def test_unknown_provider_is_ignored() -> None:
    initial = FakeLLM("ollama")
    factory = Factory()
    router = ProviderRouter(initial, factory, provider="ollama", model="qwen3:8b")

    await router.apply(provider="cloud:someone", model="x")

    assert router.name == "ollama"
    assert factory.created == []


async def test_generate_delegates_to_current_provider() -> None:
    initial = FakeLLM("mock")
    router = ProviderRouter(initial, Factory(), provider="mock", model="m")

    pieces = [
        piece
        async for piece in router.generate([{"role": "user", "content": "hi"}])
    ]

    assert pieces == ["mock回复"]
    assert len(initial.calls) == 1


async def test_aclose_closes_current_provider() -> None:
    initial = FakeLLM("ollama")
    router = ProviderRouter(initial, Factory(), provider="ollama", model="m")
    await router.aclose()
    assert initial.closed is True


class JsonMock(FakeLLM):
    def __init__(self) -> None:
        super().__init__("mock")

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        _ = (messages, stream, max_tokens, temperature)
        self.calls.append([{"role": "user", "content": "called"}])
        yield '[{"fact":"用户喜欢猫","category":"preference"}]'


async def test_mock_provider_never_extracts_fake_memories() -> None:
    llm = JsonMock()
    extractor = MemoryExtractor(llm)

    facts = await extractor.extract("default", "用户：我喜欢猫。")

    assert facts == []
    assert llm.calls == []
