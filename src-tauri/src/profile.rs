//! 人设卡与设置（母文档 3.4 拉取语义 / 16.1）。
//!
//! **为什么壳直写 SQLite**：3.4 定案——壳写入 `setting` 表即完成传播，sidecar 在
//! 每个 turn 开始前读取，协议不设 settings 推送消息。这里只暴露固定 SQL 的窄命令，
//! 不把任意 SQL 交给前端。
//!
//! **人设为什么写 setting 覆盖键**：`PersonaRepo.sync` 每次 sidecar 启动会用代码
//! prompt 校准 persona 表；若人设卡直接写 persona 表，用户编辑会被下次启动覆盖。
//! 因此覆盖存 `persona_name` / `persona_system_prompt`，编排层每轮应用；persona 表
//! 继续作为代码默认值。
//!
//! **API key**：provider 可为 mock/ollama/openai（ADR-016）。云端 key 按 16.1 走
//! Windows 凭据管理器（`secrets.rs`），本表只存 provider/base_url/model，
//! 前端拿到的永远是 `hasKey` 布尔值——明文既不落库也不回传。

use std::path::{Path, PathBuf};
use std::time::Duration;

use rusqlite::{Connection, OptionalExtension, params};
use serde::{Deserialize, Serialize};
use serde_json::Value;

const PERSONA_ID: &str = "default";
const KEY_PROVIDER: &str = "llm_provider";
const KEY_MODEL: &str = "llm_model";
const KEY_BASE_URL: &str = "llm_base_url";
const KEY_PRIVACY: &str = "privacy_mode";
const KEY_PERSONA_NAME: &str = "persona_name";
const KEY_PERSONA_PROMPT: &str = "persona_system_prompt";

const DEFAULT_PROVIDER: &str = "ollama";
const DEFAULT_MODEL: &str = "qwen3:8b";
const MAX_NAME_CHARS: usize = 50;
const MAX_PROMPT_CHARS: usize = 4000;
const MAX_MODEL_CHARS: usize = 100;
const MAX_URL_CHARS: usize = 300;

/// 数据目录（与 sidecar `db/paths.py` 同口径：env 覆盖 → LOCALAPPDATA\Echoes）。
pub fn db_path() -> PathBuf {
    let root = match std::env::var("ECHOES_DATA_DIR") {
        Ok(value) if !value.trim().is_empty() => PathBuf::from(value),
        _ => default_root(),
    };
    root.join("db").join("echoes.db")
}

fn default_root() -> PathBuf {
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        if !local.trim().is_empty() {
            return PathBuf::from(local).join("Echoes");
        }
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home)
            .join(".local")
            .join("share")
            .join("echoes");
    }
    PathBuf::from(".echoes")
}

/// 人设卡视图（前端 `systemPrompt` 由 serde camelCase 映射）。
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PersonaView {
    pub name: String,
    pub system_prompt: String,
}

/// 引擎设置视图（前端 `privacyMode` / `baseUrl` / `hasKey`）。
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SettingsView {
    pub provider: String,
    pub model: String,
    pub privacy_mode: bool,
    /// OpenAI 兼容端点（填到 `/v1` 为止）。仅 provider=openai 时使用。
    #[serde(default)]
    pub base_url: String,
    /// 只读：凭据管理器里是否已有 key（写入时忽略）。
    #[serde(default)]
    pub has_key: bool,
}

impl Default for SettingsView {
    fn default() -> Self {
        Self {
            provider: DEFAULT_PROVIDER.to_string(),
            model: DEFAULT_MODEL.to_string(),
            privacy_mode: true,
            base_url: String::new(),
            has_key: false,
        }
    }
}

/// 读人设：setting 覆盖优先，否则回落到 persona 表的代码默认值。
pub fn read_persona(path: &Path) -> Result<PersonaView, String> {
    let conn = open(path)?;
    let name = read_string(&conn, KEY_PERSONA_NAME)?;
    let prompt = read_string(&conn, KEY_PERSONA_PROMPT)?;
    if let (Some(name), Some(prompt)) = (name, prompt) {
        if !name.trim().is_empty() && !prompt.trim().is_empty() {
            return Ok(PersonaView {
                name: name.trim().to_string(),
                system_prompt: prompt.trim().to_string(),
            });
        }
    }

    let row = conn
        .query_row(
            "SELECT name, system_prompt FROM persona WHERE id = ?1",
            params![PERSONA_ID],
            |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)),
        )
        .optional()
        .map_err(|err| format!("读取人设失败（{}）：{err}", path.display()))?;
    row.map(|(name, system_prompt)| PersonaView {
        name,
        system_prompt,
    })
    .ok_or_else(|| "sidecar 尚未初始化人设（请稍后重试）".to_string())
}

/// 写人设覆盖（不碰 persona 表，避免被 `PersonaRepo.sync` 覆盖）。
pub fn write_persona(path: &Path, persona: &PersonaView) -> Result<(), String> {
    let name = persona.name.trim();
    let prompt = persona.system_prompt.trim();
    if name.is_empty() || name.chars().count() > MAX_NAME_CHARS {
        return Err(format!("人设名字需为 1–{MAX_NAME_CHARS} 字"));
    }
    if prompt.is_empty() || prompt.chars().count() > MAX_PROMPT_CHARS {
        return Err(format!("人设提示词需为 1–{MAX_PROMPT_CHARS} 字"));
    }

    let mut conn = open(path)?;
    let tx = conn
        .transaction()
        .map_err(|err| format!("写入人设失败（{}）：{err}", path.display()))?;
    write_json(&tx, KEY_PERSONA_NAME, &Value::String(name.to_string()))?;
    write_json(&tx, KEY_PERSONA_PROMPT, &Value::String(prompt.to_string()))?;
    tx.commit()
        .map_err(|err| format!("写入人设失败（{}）：{err}", path.display()))
}

const PROVIDERS: [&str; 3] = ["mock", "ollama", "openai"];

/// 读设置：缺省/类型不符回落默认；provider 只接受 mock/ollama/openai。
pub fn read_settings(path: &Path) -> Result<SettingsView, String> {
    let conn = open(path)?;
    let mut settings = SettingsView::default();

    if let Some(provider) = read_string(&conn, KEY_PROVIDER)? {
        if PROVIDERS.contains(&provider.as_str()) {
            settings.provider = provider;
        }
    }
    if let Some(model) = read_string(&conn, KEY_MODEL)? {
        if !model.trim().is_empty() {
            settings.model = model;
        }
    }
    if let Some(base_url) = read_string(&conn, KEY_BASE_URL)? {
        settings.base_url = base_url;
    }
    if let Some(privacy) = read_json(&conn, KEY_PRIVACY)? {
        if let Some(value) = privacy.as_bool() {
            settings.privacy_mode = value;
        }
    }
    Ok(settings)
}

/// 写设置（校验后一次事务写入四个键）。
pub fn write_settings(path: &Path, settings: &SettingsView) -> Result<(), String> {
    if !PROVIDERS.contains(&settings.provider.as_str()) {
        return Err(format!(
            "未知 provider {:?}（仅 mock / ollama / openai）",
            settings.provider
        ));
    }
    let model = settings.model.trim();
    if model.is_empty() || model.chars().count() > MAX_MODEL_CHARS {
        return Err(format!("模型名需为 1–{MAX_MODEL_CHARS} 字"));
    }
    let base_url = settings.base_url.trim();
    if base_url.chars().count() > MAX_URL_CHARS {
        return Err(format!("base URL 过长（> {MAX_URL_CHARS} 字）"));
    }
    if base_url.is_empty() && settings.provider == "openai" {
        return Err("云端 provider 需要填写 base URL（例：https://api.deepseek.com/v1）".into());
    }
    if !base_url.is_empty() && !(base_url.starts_with("http://") || base_url.starts_with("https://"))
    {
        return Err("base URL 需以 http:// 或 https:// 开头".into());
    }
    // 16.1：隐私模式禁止出网；云端 provider 与它互相矛盾，存进去只会每轮报错。
    if settings.provider == "openai" && settings.privacy_mode {
        return Err("云端 LLM 需要关闭隐私模式（或改用本地 Ollama）".into());
    }

    let mut conn = open(path)?;
    let tx = conn
        .transaction()
        .map_err(|err| format!("写入设置失败（{}）：{err}", path.display()))?;
    write_json(&tx, KEY_PROVIDER, &Value::String(settings.provider.clone()))?;
    write_json(&tx, KEY_MODEL, &Value::String(model.to_string()))?;
    write_json(&tx, KEY_BASE_URL, &Value::String(base_url.to_string()))?;
    write_json(&tx, KEY_PRIVACY, &Value::Bool(settings.privacy_mode))?;
    tx.commit()
        .map_err(|err| format!("写入设置失败（{}）：{err}", path.display()))
}

fn open(path: &Path) -> Result<Connection, String> {
    let conn = Connection::open(path)
        .map_err(|err| format!("打开设置库失败（{}）：{err}", path.display()))?;
    conn.busy_timeout(Duration::from_millis(5000))
        .map_err(|err| format!("设置库 busy_timeout 失败（{}）：{err}", path.display()))?;
    Ok(conn)
}

fn read_json(conn: &Connection, key: &str) -> Result<Option<Value>, String> {
    let raw: Option<String> = conn
        .query_row(
            "SELECT value FROM setting WHERE key = ?1",
            params![key],
            |row| row.get(0),
        )
        .optional()
        .map_err(|err| format!("读取 setting[{key}] 失败：{err}"))?;
    match raw {
        None => Ok(None),
        Some(text) => serde_json::from_str(&text)
            .map(Some)
            .map_err(|err| format!("setting[{key}] 不是合法 JSON：{err}")),
    }
}

fn read_string(conn: &Connection, key: &str) -> Result<Option<String>, String> {
    Ok(read_json(conn, key)?.and_then(|value| value.as_str().map(str::to_string)))
}

fn write_json(conn: &Connection, key: &str, value: &Value) -> Result<(), String> {
    let text =
        serde_json::to_string(value).map_err(|err| format!("setting[{key}] 序列化失败：{err}"))?;
    conn.execute(
        "INSERT INTO setting (key, value) VALUES (?1, ?2)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        params![key, text],
    )
    .map_err(|err| format!("写入 setting[{key}] 失败：{err}"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_db() -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir().join(format!(
            "echoes-profile-test-{}-{stamp}.db",
            std::process::id()
        ))
    }

    fn seed(path: &Path) {
        let conn = Connection::open(path).expect("open");
        conn.execute_batch(
            "CREATE TABLE persona (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                system_prompt TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO persona VALUES ('default', '默认人设', 's', 0, 0);",
        )
        .expect("schema");
    }

    #[test]
    fn settings_default_then_roundtrip() {
        let path = temp_db();
        seed(&path);
        assert_eq!(
            read_settings(&path).expect("defaults"),
            SettingsView::default()
        );

        let settings = SettingsView {
            provider: "mock".to_string(),
            model: "qwen3:4b".to_string(),
            privacy_mode: false,
            ..SettingsView::default()
        };
        write_settings(&path, &settings).expect("write");
        assert_eq!(read_settings(&path).expect("read"), settings);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn openai_settings_require_base_url_and_local_privacy() {
        let path = temp_db();
        seed(&path);

        let cloud_with_privacy = SettingsView {
            provider: "openai".to_string(),
            model: "deepseek-chat".to_string(),
            privacy_mode: true,
            base_url: "https://api.deepseek.com/v1".to_string(),
            has_key: false,
        };
        let err = write_settings(&path, &cloud_with_privacy).expect_err("隐私模式应拒绝云端");
        assert!(err.contains("隐私模式"), "{err}");

        let no_url = SettingsView {
            privacy_mode: false,
            base_url: String::new(),
            ..cloud_with_privacy.clone()
        };
        let err = write_settings(&path, &no_url).expect_err("缺 base URL 应拒绝");
        assert!(err.contains("base URL"), "{err}");

        let ok = SettingsView {
            privacy_mode: false,
            base_url: "https://api.deepseek.com/v1".to_string(),
            ..cloud_with_privacy
        };
        write_settings(&path, &ok).expect("write cloud");
        let read = read_settings(&path).expect("read");
        assert_eq!(read.provider, "openai");
        assert_eq!(read.base_url, "https://api.deepseek.com/v1");
        assert!(!read.privacy_mode);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn invalid_provider_is_rejected_on_write_but_ignored_on_read() {
        let path = temp_db();
        seed(&path);
        let conn = Connection::open(&path).expect("open");
        write_json(&conn, KEY_PROVIDER, &Value::String("cloud:x".to_string())).expect("write");
        drop(conn);

        assert_eq!(
            read_settings(&path).expect("read").provider,
            DEFAULT_PROVIDER
        );
        let bad = SettingsView {
            provider: "cloud:x".to_string(),
            ..SettingsView::default()
        };
        assert!(write_settings(&path, &bad).is_err());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn persona_falls_back_to_table_then_override_wins() {
        let path = temp_db();
        seed(&path);
        assert_eq!(
            read_persona(&path).expect("fallback"),
            PersonaView {
                name: "默认人设".to_string(),
                system_prompt: "s".to_string()
            }
        );

        let persona = PersonaView {
            name: "小林".to_string(),
            system_prompt: "你是小林，说话简洁。".to_string(),
        };
        write_persona(&path, &persona).expect("write");
        assert_eq!(read_persona(&path).expect("override"), persona);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn persona_validation_rejects_empty_and_too_long() {
        let path = temp_db();
        seed(&path);
        assert!(
            write_persona(
                &path,
                &PersonaView {
                    name: " ".to_string(),
                    system_prompt: "s".to_string()
                }
            )
            .is_err()
        );
        assert!(
            write_persona(
                &path,
                &PersonaView {
                    name: "x".repeat(MAX_NAME_CHARS + 1),
                    system_prompt: "s".to_string()
                }
            )
            .is_err()
        );
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn missing_persona_table_is_an_error_not_a_fake_default() {
        let path = temp_db();
        let conn = Connection::open(&path).expect("open");
        conn.execute_batch("CREATE TABLE setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
            .expect("setting");
        drop(conn);
        assert!(read_persona(&path).is_err());
        let _ = std::fs::remove_file(&path);
    }
}
