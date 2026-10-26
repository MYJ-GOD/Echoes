"""API key 读取（ADR-016）：只读、缺失返 None、后端异常不拖垮启动。"""
from __future__ import annotations

import pytest

from echoes_sidecar import secrets


def test_reads_saved_key(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_get(service: str, account: str) -> str | None:
        calls.append((service, account))
        return "sk-live-123"

    monkeypatch.setattr(secrets.keyring, "get_password", fake_get)
    assert secrets.llm_api_key() == "sk-live-123"
    assert calls == [(secrets.SERVICE, secrets.ACCOUNT)]


def test_missing_key_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets.keyring, "get_password", lambda service, account: None)
    assert secrets.llm_api_key() is None


def test_blank_key_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets.keyring, "get_password", lambda service, account: "   ")
    assert secrets.llm_api_key() is None


def test_backend_failure_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(service: str, account: str) -> str:
        raise RuntimeError("credential backend unavailable")

    monkeypatch.setattr(secrets.keyring, "get_password", boom)
    assert secrets.llm_api_key() is None
