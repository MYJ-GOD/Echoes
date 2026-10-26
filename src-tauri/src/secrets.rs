//! 云端 LLM 的 API key（ADR-016）：Windows 凭据管理器，只写不读。
//!
//! **口径必须与 sidecar 对齐**：`keyring` crate 在 Windows 默认用 `user.service`
//! 作 target，而 python-keyring 先读 `service`、再退到 `user@service`。两侧不对齐
//! 就会「写着成功、读着为空」。因此这里用 `new_with_target(SERVICE, SERVICE, ACCOUNT)`，
//! sidecar 用 `keyring.get_password(SERVICE, ACCOUNT)`——实测双向互通。
//!
//! 边界：明文只在内存里过一手；不写日志、不回传前端（前端只拿 `hasKey`）。

use keyring::Entry;

const SERVICE: &str = "Echoes";
const ACCOUNT: &str = "llm-api-key";
const MAX_KEY_CHARS: usize = 512;

fn entry() -> Result<Entry, String> {
    Entry::new_with_target(SERVICE, SERVICE, ACCOUNT)
        .map_err(|err| format!("打开 Windows 凭据管理器失败：{err}"))
}

/// 保存 key（覆盖旧值）。空串等于清除。
pub fn save(key: &str) -> Result<(), String> {
    let key = key.trim();
    if key.is_empty() {
        return clear();
    }
    if key.chars().count() > MAX_KEY_CHARS {
        return Err(format!("API key 过长（> {MAX_KEY_CHARS} 字）"));
    }
    entry()?
        .set_password(key)
        .map_err(|err| format!("写入凭据失败：{err}"))
}

/// 清除 key；本来就没有也算成功（幂等）。
pub fn clear() -> Result<(), String> {
    match entry() {
        Ok(entry) => match entry.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(err) => Err(format!("删除凭据失败：{err}")),
        },
        Err(err) => Err(err),
    }
}

/// 是否已保存 key（前端只显示「已保存 / 未保存」）。
pub fn has_key() -> bool {
    match entry() {
        Ok(entry) => entry.get_password().is_ok_and(|value| !value.trim().is_empty()),
        Err(_) => false,
    }
}
