"""运行期设置（3.4 拉取）：默认值、类型校验与人设覆盖键。"""

from __future__ import annotations

from pathlib import Path

from echoes_sidecar.db.repo import Storage
from echoes_sidecar.session.runtime import (
    SETTING_MODEL,
    SETTING_PERSONA_NAME,
    SETTING_PERSONA_PROMPT,
    SETTING_PRIVACY,
    SETTING_PROVIDER,
    load_runtime_settings,
)


def _storage(tmp_path: Path) -> Storage:
    return Storage.open(tmp_path / "db" / "echoes.db")


def test_defaults_when_settings_absent(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    try:
        settings = load_runtime_settings(storage)
        assert settings.provider is None
        assert settings.model is None
        assert settings.privacy_mode is True
        assert settings.persona_name is None
        assert settings.persona_system_prompt is None
    finally:
        storage.close()


def test_reads_valid_settings(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    try:
        storage.settings.set(SETTING_PROVIDER, "ollama")
        storage.settings.set(SETTING_MODEL, "qwen3:8b")
        storage.settings.set(SETTING_PRIVACY, False)
        storage.settings.set(SETTING_PERSONA_NAME, " 小林 ")
        storage.settings.set(SETTING_PERSONA_PROMPT, "你是小林，说话简洁。")
        settings = load_runtime_settings(storage)
        assert settings.provider == "ollama"
        assert settings.model == "qwen3:8b"
        assert settings.privacy_mode is False
        assert settings.persona_name == "小林"
        assert settings.persona_system_prompt == "你是小林，说话简洁。"
    finally:
        storage.close()


def test_invalid_provider_is_ignored_not_downgraded(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    try:
        storage.settings.set(SETTING_PROVIDER, "cloud:someone")
        assert load_runtime_settings(storage).provider is None
    finally:
        storage.close()


def test_non_bool_privacy_falls_back_to_default(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    try:
        storage.settings.set(SETTING_PRIVACY, "yes")
        assert load_runtime_settings(storage).privacy_mode is True
    finally:
        storage.close()


def test_empty_persona_override_is_ignored(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    try:
        storage.settings.set(SETTING_PERSONA_NAME, "   ")
        storage.settings.set(SETTING_PERSONA_PROMPT, "")
        settings = load_runtime_settings(storage)
        assert settings.persona_name is None
        assert settings.persona_system_prompt is None
    finally:
        storage.close()
