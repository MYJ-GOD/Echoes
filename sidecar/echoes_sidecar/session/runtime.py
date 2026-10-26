"""运行期设置（3.4 拉取语义 / 16.1）：每轮 turn 前从 setting 表读取。

**为什么是拉取而不是推送**：母文档 3.4 定案——壳写入 SQLite 即完成传播，协议不设
settings 推送消息。sidecar 在每个 turn 开始前读一次，避免进程内状态与库分叉。

**人设覆盖**：`PersonaRepo.sync` 的语义是「代码 prompt 是默认来源，启动时校准 DB」，
用户编辑若直接写 persona 表会被下次启动覆盖。因此人设卡写两个 setting 键
（`persona_name` / `persona_system_prompt`），编排层每轮应用为 `session.persona`；
persona 表继续作为代码默认值。
"""
from __future__ import annotations

from dataclasses import dataclass

from echoes_sidecar.db import Storage

SETTING_PROVIDER = "llm_provider"
SETTING_MODEL = "llm_model"
SETTING_BASE_URL = "llm_base_url"
SETTING_PRIVACY = "privacy_mode"
SETTING_PERSONA_NAME = "persona_name"
SETTING_PERSONA_PROMPT = "persona_system_prompt"

DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "qwen3:8b"
PROVIDERS = frozenset({"mock", "ollama", "openai"})


@dataclass(frozen=True)
class RuntimeSettings:
    """一次 turn 开始前看到的设置快照；None = 保持 CLI/当前值。"""

    provider: str | None
    model: str | None
    privacy_mode: bool
    persona_name: str | None
    persona_system_prompt: str | None
    base_url: str | None = None


def load_runtime_settings(storage: Storage) -> RuntimeSettings:
    """读 setting 表（缺失/类型不符按默认；坏 JSON 由 SettingRepo 报 STORAGE_ERROR）。"""
    provider = _text(storage.settings.get(SETTING_PROVIDER))
    model = _text(storage.settings.get(SETTING_MODEL))
    base_url = _text(storage.settings.get(SETTING_BASE_URL))
    privacy = storage.settings.get(SETTING_PRIVACY)
    return RuntimeSettings(
        provider=provider if provider in PROVIDERS else None,
        model=model,
        privacy_mode=privacy if isinstance(privacy, bool) else True,
        persona_name=_text(storage.settings.get(SETTING_PERSONA_NAME)),
        persona_system_prompt=_text(storage.settings.get(SETTING_PERSONA_PROMPT)),
        base_url=base_url,
    )


def _text(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "PROVIDERS",
    "RuntimeSettings",
    "SETTING_BASE_URL",
    "SETTING_MODEL",
    "SETTING_PERSONA_NAME",
    "SETTING_PERSONA_PROMPT",
    "SETTING_PRIVACY",
    "SETTING_PROVIDER",
    "load_runtime_settings",
]
