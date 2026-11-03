//! 云端引擎 API key（ADR-016 / R2a 2.13）：Windows 凭据管理器，只写不读。
//!
//! **口径必须与 sidecar 对齐**：`keyring` crate 在 Windows 默认用 `user.service`
//! 作 target，而 python-keyring 先读 `service`、再退到 `user@service`。两侧不对齐
//! 就会「写着成功、读着为空」。因此这里用 `new_with_target(SERVICE, SERVICE, ACCOUNT)`，
//! sidecar 用 `keyring.get_password(SERVICE, ACCOUNT)`——实测双向互通。
//!
//! **分链账号**：LLM 用历史账号 `llm-api-key`；ASR/TTS 用 `<chain>-<provider>`，
//! 与 sidecar `secrets.engine_account` 同口径。同一 provider 在两条链上可以是
//! 不同 key（不同项目配额），不能共用一个账号。
//!
//! 边界：明文只在内存里过一手；不写日志、不回传前端（前端只拿 `hasKey`）。

use keyring::Entry;

const SERVICE: &str = "Echoes";
/// LLM 的历史账号名（不能改名：已安装用户的 key 存在这里）。
pub const LLM_ACCOUNT: &str = "llm-api-key";
const MAX_KEY_CHARS: usize = 512;

/// 云端引擎账号名：`<chain>-<provider>`（chain = asr / tts）。
pub fn engine_account(chain: &str, provider: &str) -> String {
    format!("{chain}-{provider}")
}

fn entry(account: &str) -> Result<Entry, String> {
    Entry::new_with_target(SERVICE, SERVICE, account)
        .map_err(|err| format!("打开 Windows 凭据管理器失败：{err}"))
}

/// 保存 key（覆盖旧值）。空串等于清除。
pub fn save_for(account: &str, key: &str) -> Result<(), String> {
    let key = key.trim();
    if key.is_empty() {
        return clear_for(account);
    }
    if key.chars().count() > MAX_KEY_CHARS {
        return Err(format!("API key 过长（> {MAX_KEY_CHARS} 字）"));
    }
    entry(account)?
        .set_password(key)
        .map_err(|err| format!("写入凭据失败：{err}"))
}

/// 清除 key；本来就没有也算成功（幂等）。
pub fn clear_for(account: &str) -> Result<(), String> {
    match entry(account) {
        Ok(entry) => match entry.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(err) => Err(format!("删除凭据失败：{err}")),
        },
        Err(err) => Err(err),
    }
}

/// 是否已保存 key（前端只显示「已保存 / 未保存」）。
pub fn has_key_for(account: &str) -> bool {
    match entry(account) {
        Ok(entry) => entry.get_password().is_ok_and(|value| !value.trim().is_empty()),
        Err(_) => false,
    }
}

// ---- LLM 的旧调用面（命令名与账号保持兼容） ----

pub fn save(key: &str) -> Result<(), String> {
    save_for(LLM_ACCOUNT, key)
}

pub fn clear() -> Result<(), String> {
    clear_for(LLM_ACCOUNT)
}

pub fn has_key() -> bool {
    has_key_for(LLM_ACCOUNT)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn engine_account_matches_sidecar_convention() {
        assert_eq!(engine_account("tts", "openai"), "tts-openai");
        assert_eq!(engine_account("asr", "openai"), "asr-openai");
        // 同一 provider 两条链账号不同，避免配额/项目串用
        assert_ne!(
            engine_account("tts", "openai"),
            engine_account("asr", "openai")
        );
    }

    #[test]
    fn too_long_key_is_rejected_before_touching_keyring() {
        // 长度校验在 entry() 之前：无凭据后端的环境也不会误写
        assert!(save_for("tts-openai-test", &"k".repeat(MAX_KEY_CHARS + 1)).is_err());
    }
}
