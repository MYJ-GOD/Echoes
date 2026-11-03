"""模型目录拉取（R2a 2.6）：Ollama /api/tags 与云端 /v1/models。"""

from __future__ import annotations

import pytest

from echoes_sidecar import setup
from echoes_sidecar.core.errors import EchoesError, ErrorCode


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.requested: list[tuple[str, dict[str, str] | None]] = []

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise setup.httpx.HTTPStatusError(
                "boom", request=None, response=None  # type: ignore[arg-type]
            )


def _client(monkeypatch: pytest.MonkeyPatch, response: FakeResponse) -> list[tuple[str, object]]:
    calls: list[tuple[str, object]] = []

    class Client:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def get(self, url: str, headers: dict[str, str] | None = None) -> FakeResponse:
            calls.append((url, headers))
            return response

    monkeypatch.setattr(setup.httpx, "Client", Client)
    return calls


def test_ollama_catalog_lists_tag_names(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _client(
        monkeypatch,
        FakeResponse({"models": [{"name": "qwen3:8b"}, {"name": "qwen3:4b"}, {}]}),
    )
    options = setup.list_models("ollama")
    assert [item.id for item in options] == ["qwen3:8b", "qwen3:4b"]
    assert options[0].owner == "ollama"
    assert calls[0][0].endswith("/api/tags")


def test_cloud_catalog_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch, FakeResponse({"data": []}))
    monkeypatch.setattr(setup, "llm_api_key", lambda: None)
    with pytest.raises(EchoesError) as err:
        setup.list_models("openai", base_url="https://api.example/v1")
    assert err.value.code is ErrorCode.LLM_KEY_MISSING


def test_cloud_catalog_uses_bearer_and_parses_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _client(
        monkeypatch,
        FakeResponse(
            {
                "data": [
                    {"id": "deepseek-chat", "owned_by": "deepseek"},
                    {"id": "deepseek-reasoner"},
                    {"no_id": True},
                ]
            }
        ),
    )
    monkeypatch.setattr(setup, "llm_api_key", lambda: "sk-test")
    options = setup.list_models("openai", base_url="https://api.example/v1/")
    assert [item.id for item in options] == ["deepseek-chat", "deepseek-reasoner"]
    assert options[0].owner == "deepseek"
    url, headers = calls[0]
    assert url == "https://api.example/v1/models"
    assert headers == {"Authorization": "Bearer sk-test"}


def test_unreachable_provider_is_a_loud_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _client(monkeypatch, FakeResponse({}, status=503))
    with pytest.raises(EchoesError) as err:
        setup.list_models("ollama")
    assert err.value.code is ErrorCode.LLM_PROVIDER_UNAVAILABLE


def test_mock_provider_has_no_catalog() -> None:
    with pytest.raises(EchoesError):
        setup.list_models("mock")
