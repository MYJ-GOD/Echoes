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
# R2a 2.5：语音链（ASR/TTS）也走拉取语义
SETTING_ASR_PROVIDER = "asr_provider"
SETTING_ASR_MODEL = "asr_model"
SETTING_ASR_BASE_URL = "asr_base_url"
SETTING_TTS_PROVIDER = "tts_provider"
SETTING_TTS_MODEL = "tts_model"
SETTING_TTS_BASE_URL = "tts_base_url"

DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "qwen3:8b"
PROVIDERS = frozenset({"mock", "ollama", "openai"})
DEFAULT_ASR_PROVIDER = "whisper"
ASR_PROVIDERS = frozenset({"mock", "whisper", "openai"})
DEFAULT_TTS_PROVIDER = "cosyvoice2"
TTS_PROVIDERS = frozenset({"mock", "cosyvoice2", "openai"})


@dataclass(frozen=True)
class RuntimeSettings:
    """一次 turn 开始前看到的设置快照；None = 保持 CLI/当前值。"""

    provider: str | None
    model: str | None
    privacy_mode: bool
    persona_name: str | None
    persona_system_prompt: str | None
    base_url: str | None = None
    asr_provider: str | None = None
    asr_model: str | None = None
    asr_base_url: str | None = None
    tts_provider: str | None = None
    tts_model: str | None = None
    tts_base_url: str | None = None


def load_runtime_settings(storage: Storage) -> RuntimeSettings:
    """读 setting 表（缺失/类型不符按默认；坏 JSON 由 SettingRepo 报 STORAGE_ERROR）。"""
    provider = _text(storage.settings.get(SETTING_PROVIDER))
    model = _text(storage.settings.get(SETTING_MODEL))
    base_url = _text(storage.settings.get(SETTING_BASE_URL))
    asr_provider = _text(storage.settings.get(SETTING_ASR_PROVIDER))
    tts_provider = _text(storage.settings.get(SETTING_TTS_PROVIDER))
    privacy = storage.settings.get(SETTING_PRIVACY)
    return RuntimeSettings(
        provider=provider if provider in PROVIDERS else None,
        model=model,
        privacy_mode=privacy if isinstance(privacy, bool) else True,
        persona_name=_text(storage.settings.get(SETTING_PERSONA_NAME)),
        persona_system_prompt=_text(storage.settings.get(SETTING_PERSONA_PROMPT)),
        base_url=base_url,
        asr_provider=asr_provider if asr_provider in ASR_PROVIDERS else None,
        asr_model=_text(storage.settings.get(SETTING_ASR_MODEL)),
        asr_base_url=_text(storage.settings.get(SETTING_ASR_BASE_URL)),
        tts_provider=(
            tts_provider if tts_provider in TTS_PROVIDERS else None
        ),
        tts_model=_text(storage.settings.get(SETTING_TTS_MODEL)),
        tts_base_url=_text(storage.settings.get(SETTING_TTS_BASE_URL)),
    )


def _text(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


__all__ = [
    "ASR_PROVIDERS",
    "DEFAULT_ASR_PROVIDER",
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "DEFAULT_TTS_PROVIDER",
    "PROVIDERS",
    "RuntimeSettings",
    "SETTING_ASR_BASE_URL",
    "SETTING_ASR_MODEL",
    "SETTING_ASR_PROVIDER",
    "SETTING_BASE_URL",
    "SETTING_MODEL",
    "SETTING_PERSONA_NAME",
    "SETTING_PERSONA_PROMPT",
    "SETTING_PRIVACY",
    "SETTING_PROVIDER",
    "SETTING_TTS_BASE_URL",
    "SETTING_TTS_MODEL",
    "SETTING_TTS_PROVIDER",
    "TTS_PROVIDERS",
    "load_runtime_settings",
]
