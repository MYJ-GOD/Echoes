"""API key 读取：Windows 凭据管理器（ADR-016），壳写 sidecar 读。

**为什么不是 SQLite**：4.4 明文禁令 + 备份/同步会把库带走。凭据管理器按用户隔离，
不随数据目录拷贝，也不会出现在日志里。

**为什么两侧都用 `target=service`**：python-keyring 在 Windows 上默认先读
`target=service`，若 `UserName` 不匹配再退到 `user@service` 复合名；Rust 的
`keyring` crate 默认用 `user.service`。两侧口径不一致就会「写着成功、读着为空」。
因此约定：壳用 `Entry::new_with_target(SERVICE, SERVICE, ACCOUNT)` 写，sidecar
用 `keyring.get_password(SERVICE, ACCOUNT)` 读——实测双向互通。

**分链账号**（R2a 2.13）：LLM 用 `llm-api-key`（历史账号，不能改名）；云端
ASR/TTS 用 `<chain>-<provider>`，例如 `tts-openai` / `asr-openai`。同一个
provider 在两条链上可以是不同 key（不同项目配额），所以不能共用账号。

**边界**：只读不写（写入归壳的设置页）；读失败不抛，返回 None 由引擎报
`*_KEY_MISSING`（14.1 不静默降级）。
"""
from __future__ import annotations

import sys

import keyring

SERVICE = "Echoes"
ACCOUNT = "llm-api-key"  # LLM 的历史账号名（壳侧 secrets.rs 同值）


def engine_account(chain: str, provider: str) -> str:
    """云端引擎账号名：`<chain>-<provider>`（chain = asr / tts）。"""
    return f"{chain}-{provider}"


def read_api_key(account: str) -> str | None:
    """读指定账号的 key；未配置/后端不可用时返回 None。"""
    try:
        value = keyring.get_password(SERVICE, account)
    except Exception as exc:  # noqa: BLE001  凭据后端异常不该拖垮 turn 启动
        print(f"[secrets] 读取凭据失败（{SERVICE}/{account}）：{exc}", file=sys.stderr)
        return None
    if not value:
        return None
    key = value.strip()
    return key or None


def llm_api_key() -> str | None:
    """读云端 LLM 的 API key。"""
    return read_api_key(ACCOUNT)


def engine_api_key(chain: str, provider: str) -> str | None:
    """读云端 ASR/TTS 的 API key（分链分 provider）。"""
    return read_api_key(engine_account(chain, provider))


__all__ = [
    "ACCOUNT",
    "SERVICE",
    "engine_account",
    "engine_api_key",
    "llm_api_key",
    "read_api_key",
]
