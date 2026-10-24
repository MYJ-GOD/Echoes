"""组合根记忆装配（5.2）：auto/on/off 与权重缺失边界。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from echoes_sidecar.engines.llm.base import LLMProvider
from echoes_sidecar.main import _assemble_memory


class NamedLLM(LLMProvider):
    def __init__(self, name: str) -> None:
        self._name = name

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
        _ = (messages, stream, max_tokens, temperature)
        yield "[]"


class FakeStorage:
    def __init__(self) -> None:
        self.memories = object()


def _weights(tmp_path: Path, *, present: bool = True) -> Path:
    model_dir = tmp_path / "bge-small-zh-v1.5"
    model_dir.mkdir()
    if present:
        (model_dir / "config.json").write_text("{}", encoding="utf-8")
    return model_dir


def test_memory_off_disables_everything(tmp_path: Path) -> None:
    store, extractor = _assemble_memory(
        ["--memory", "off"], FakeStorage(), NamedLLM("ollama"), model_dir=_weights(tmp_path)  # type: ignore[arg-type]
    )
    assert store is None and extractor is None


def test_auto_disables_for_mock_even_with_weights(tmp_path: Path) -> None:
    store, extractor = _assemble_memory(
        ["--memory", "auto"], FakeStorage(), NamedLLM("mock"), model_dir=_weights(tmp_path)  # type: ignore[arg-type]
    )
    assert store is None and extractor is None


def test_auto_disables_when_weights_missing(tmp_path: Path) -> None:
    store, extractor = _assemble_memory(
        ["--memory", "auto"],
        FakeStorage(),  # type: ignore[arg-type]
        NamedLLM("ollama"),
        model_dir=_weights(tmp_path, present=False),
    )
    assert store is None and extractor is None


def test_auto_enables_for_real_llm_with_weights(tmp_path: Path) -> None:
    store, extractor = _assemble_memory(
        ["--memory", "auto"], FakeStorage(), NamedLLM("ollama"), model_dir=_weights(tmp_path)  # type: ignore[arg-type]
    )
    assert store is not None
    assert extractor is not None


def test_on_forces_even_without_weights(tmp_path: Path) -> None:
    store, extractor = _assemble_memory(
        ["--memory", "on"],
        FakeStorage(),  # type: ignore[arg-type]
        NamedLLM("ollama"),
        model_dir=_weights(tmp_path, present=False),
    )
    assert store is not None
    assert extractor is not None


def test_default_is_auto(tmp_path: Path) -> None:
    store, extractor = _assemble_memory(
        [], FakeStorage(), NamedLLM("ollama"), model_dir=_weights(tmp_path)  # type: ignore[arg-type]
    )
    assert store is not None and extractor is not None
