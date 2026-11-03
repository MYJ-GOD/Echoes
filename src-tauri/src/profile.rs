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
const KEY_TTS_PROVIDER: &str = "tts_provider";
const KEY_TTS_MODEL: &str = "tts_model";
const KEY_TTS_BASE_URL: &str = "tts_base_url";
const KEY_ASR_PROVIDER: &str = "asr_provider";
const KEY_ASR_MODEL: &str = "asr_model";
const KEY_ASR_BASE_URL: &str = "asr_base_url";
const KEY_LLM_CONSENT: &str = "llm_cloud_consent";
const KEY_ASR_CONSENT: &str = "asr_cloud_consent";
const KEY_TTS_CONSENT: &str = "tts_cloud_consent";
const KEY_FIRST_RUN: &str = "first_run_done";
const KEY_CLOSE_TO_TRAY: &str = "close_to_tray";
const KEY_PTT_SHORTCUT: &str = "ptt_shortcut";
const KEY_PERSONA_NAME: &str = "persona_name";
const KEY_PERSONA_PROMPT: &str = "persona_system_prompt";

const DEFAULT_PROVIDER: &str = "ollama";
const DEFAULT_MODEL: &str = "qwen3:8b";
/// 语音链默认走本地（与 sidecar CLI 默认一致）；云端需要显式选择 + key。
const DEFAULT_TTS_PROVIDER: &str = "cosyvoice2";
const DEFAULT_TTS_MODEL: &str = "tts-1";
const TTS_PROVIDERS: [&str; 3] = ["mock", "cosyvoice2", "openai"];
/// 语音识别默认本地 whisper small（原始录音不出本机）。
const DEFAULT_ASR_PROVIDER: &str = "whisper";
const DEFAULT_ASR_MODEL: &str = "small";
const ASR_PROVIDERS: [&str; 3] = ["mock", "whisper", "openai"];
const MAX_NAME_CHARS: usize = 50;
const MAX_PROMPT_CHARS: usize = 4000;
const MAX_MODEL_CHARS: usize = 100;
const MAX_URL_CHARS: usize = 300;

/// 数据根目录（与 sidecar `db/paths.py` 同口径：env 覆盖 → LOCALAPPDATA\Echoes）。
pub fn root_dir() -> PathBuf {
    match std::env::var("ECHOES_DATA_DIR") {
        Ok(value) if !value.trim().is_empty() => PathBuf::from(value),
        _ => default_root(),
    }
}

/// 数据目录（与 sidecar `db/paths.py` 同口径：env 覆盖 → LOCALAPPDATA\Echoes）。
pub fn db_path() -> PathBuf {
    root_dir().join("db").join("echoes.db")
}

fn default_root() -> PathBuf {
    if let Ok(local) = std::env::var("LOCALAPPDATA")
        && !local.trim().is_empty()
    {
        return PathBuf::from(local).join("Echoes");
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
    /// 只读：首启向导是否已完成（写入时忽略；`complete_setup` 单独置位）。
    #[serde(default)]
    pub first_run_done: bool,
    /// R2a 2.5：语音合成链（mock / cosyvoice2 / openai）。
    #[serde(default)]
    pub tts_provider: String,
    /// 云端 TTS 模型（cosyvoice2/mock 忽略）。
    #[serde(default)]
    pub tts_model: String,
    /// 云端 TTS 的 OpenAI 兼容端点（填到 `/v1` 为止）。
    #[serde(default)]
    pub tts_base_url: String,
    /// 只读：凭据管理器里是否已有 TTS key（写入时忽略）。
    #[serde(default)]
    pub has_tts_key: bool,
    /// R2a 2.1/2.2：语音识别链（mock / whisper / openai）。
    #[serde(default)]
    pub asr_provider: String,
    /// whisper 档位（tiny/base/small）或云端模型名。
    #[serde(default)]
    pub asr_model: String,
    /// 云端 ASR 的 OpenAI 兼容端点。
    #[serde(default)]
    pub asr_base_url: String,
    /// 只读：凭据管理器里是否已有 ASR key（写入时忽略）。
    #[serde(default)]
    pub has_asr_key: bool,
    /// R2a 2.11：云端逐链同意（数据出境告知）。写入时必须为真才能保存公网端点。
    #[serde(default)]
    pub llm_cloud_consent: bool,
    #[serde(default)]
    pub asr_cloud_consent: bool,
    #[serde(default)]
    pub tts_cloud_consent: bool,
}

impl Default for SettingsView {
    fn default() -> Self {
        Self {
            provider: DEFAULT_PROVIDER.to_string(),
            model: DEFAULT_MODEL.to_string(),
            privacy_mode: true,
            base_url: String::new(),
            has_key: false,
            first_run_done: false,
            tts_provider: DEFAULT_TTS_PROVIDER.to_string(),
            tts_model: DEFAULT_TTS_MODEL.to_string(),
            tts_base_url: String::new(),
            has_tts_key: false,
            asr_provider: DEFAULT_ASR_PROVIDER.to_string(),
            asr_model: DEFAULT_ASR_MODEL.to_string(),
            asr_base_url: String::new(),
            has_asr_key: false,
            llm_cloud_consent: false,
            asr_cloud_consent: false,
            tts_cloud_consent: false,
        }
    }
}

/// 读人设：setting 覆盖优先，否则回落到 persona 表的代码默认值。
pub fn read_persona(path: &Path) -> Result<PersonaView, String> {
    let conn = open(path)?;
    let name = read_string(&conn, KEY_PERSONA_NAME)?;
    let prompt = read_string(&conn, KEY_PERSONA_PROMPT)?;
    if let (Some(name), Some(prompt)) = (name, prompt)
        && !name.trim().is_empty()
        && !prompt.trim().is_empty()
    {
        return Ok(PersonaView {
            name: name.trim().to_string(),
            system_prompt: prompt.trim().to_string(),
        });
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

    if let Some(provider) = read_string(&conn, KEY_PROVIDER)?
        && PROVIDERS.contains(&provider.as_str())
    {
        settings.provider = provider;
    }
    if let Some(model) = read_string(&conn, KEY_MODEL)?
        && !model.trim().is_empty()
    {
        settings.model = model;
    }
    if let Some(base_url) = read_string(&conn, KEY_BASE_URL)? {
        settings.base_url = base_url;
    }
    if let Some(flag) = read_json(&conn, KEY_PRIVACY)?.and_then(|value| value.as_bool()) {
        settings.privacy_mode = flag;
    }
    if let Some(provider) = read_string(&conn, KEY_TTS_PROVIDER)?
        && TTS_PROVIDERS.contains(&provider.as_str())
    {
        settings.tts_provider = provider;
    }
    if let Some(model) = read_string(&conn, KEY_TTS_MODEL)? {
        settings.tts_model = model;
    }
    if let Some(base_url) = read_string(&conn, KEY_TTS_BASE_URL)? {
        settings.tts_base_url = base_url;
    }
    if let Some(provider) = read_string(&conn, KEY_ASR_PROVIDER)?
        && ASR_PROVIDERS.contains(&provider.as_str())
    {
        settings.asr_provider = provider;
    }
    if let Some(model) = read_string(&conn, KEY_ASR_MODEL)? {
        settings.asr_model = model;
    }
    if let Some(base_url) = read_string(&conn, KEY_ASR_BASE_URL)? {
        settings.asr_base_url = base_url;
    }
    settings.llm_cloud_consent = read_json(&conn, KEY_LLM_CONSENT)?
        .and_then(|value| value.as_bool())
        .unwrap_or(false);
    settings.asr_cloud_consent = read_json(&conn, KEY_ASR_CONSENT)?
        .and_then(|value| value.as_bool())
        .unwrap_or(false);
    settings.tts_cloud_consent = read_json(&conn, KEY_TTS_CONSENT)?
        .and_then(|value| value.as_bool())
        .unwrap_or(false);
    if let Some(done) = read_json(&conn, KEY_FIRST_RUN)?.and_then(|value| value.as_bool()) {
        settings.first_run_done = done;
    }
    Ok(settings)
}

/// 首启完成标记（ADR-016）：与 settings 分开写，避免「保存设置」把向导又弹出来。
pub fn write_first_run_done(path: &Path, done: bool) -> Result<(), String> {
    let conn = open(path)?;
    write_json(&conn, KEY_FIRST_RUN, &Value::Bool(done))
        .map_err(|err| format!("写入首启标记失败（{}）：{err}", path.display()))
}

/// base URL 是否指向本机（LM Studio / vLLM / Ollama 的 `/v1`）。
///
/// 与 sidecar `engines/llm/openai_compat.py::is_loopback` 同口径：只认
/// `localhost` / `127.0.0.1` / `::1` / `0.0.0.0`；解析不出来按出网处理（保守）。
fn is_loopback_base_url(base_url: &str) -> bool {
    let rest = base_url.trim();
    // 只剥 scheme，不校验它（write_settings 已单独校验 http/https 前缀）
    let rest = match rest.split_once("://") {
        Some((_, tail)) => tail,
        None => rest,
    };
    let authority = rest.split(['/', '?', '#']).next().unwrap_or("");
    // IPv6 字面量形如 `[::1]:1234`：方括号内的冒号不是端口分隔符
    let host = match authority.strip_prefix('[') {
        Some(inner) => inner.split(']').next().unwrap_or(""),
        None => authority.split(':').next().unwrap_or(""),
    };
    ["localhost", "127.0.0.1", "::1", "0.0.0.0"]
        .iter()
        .any(|candidate| host.eq_ignore_ascii_case(candidate))
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
    // 16.1 / ADR-016 §3：隐私模式禁止「出网」，但本机兼容端点（环回地址）不出网。
    // 判据与 sidecar 侧 `openai_compat.is_loopback` 同口径，两侧不一致会让
    // 「写得进去、每轮报错」，或反过来「明明能跑却不让保存」。
    if settings.provider == "openai" && settings.privacy_mode && !is_loopback_base_url(base_url) {
        return Err(
            "隐私模式只允许本机 LLM 端点（如 http://127.0.0.1:1234/v1）；云端需要关闭隐私模式"
                .into(),
        );
    }
    // 2.11：公网端点必须逐链同意（数据出境告知），环回端点不出网、不要求。
    if settings.provider == "openai"
        && !is_loopback_base_url(base_url)
        && !settings.llm_cloud_consent
    {
        return Err(
            "云端 LLM 会把对话文本发送至第三方：请先勾选「我知晓数据将发送至该端点」".into(),
        );
    }

    // R2a 2.5：语音链与 LLM 同口径（provider 白名单 + 云端端点 + 隐私矩阵）。
    if !TTS_PROVIDERS.contains(&settings.tts_provider.as_str()) {
        return Err(format!(
            "未知 TTS provider {:?}（仅 mock / cosyvoice2 / openai）",
            settings.tts_provider
        ));
    }
    let tts_model = settings.tts_model.trim();
    if tts_model.chars().count() > MAX_MODEL_CHARS {
        return Err(format!("TTS 模型名过长（> {MAX_MODEL_CHARS} 字）"));
    }
    let tts_base = settings.tts_base_url.trim();
    if tts_base.chars().count() > MAX_URL_CHARS {
        return Err(format!("TTS base URL 过长（> {MAX_URL_CHARS} 字）"));
    }
    if settings.tts_provider == "openai" {
        if tts_model.is_empty() {
            return Err("云端 TTS 需要填写模型名（例：tts-1 / gpt-4o-mini-tts）".into());
        }
        if tts_base.is_empty() {
            return Err("云端 TTS 需要填写 base URL（例：https://api.openai.com/v1）".into());
        }
    }
    if !tts_base.is_empty()
        && !(tts_base.starts_with("http://") || tts_base.starts_with("https://"))
    {
        return Err("TTS base URL 需以 http:// 或 https:// 开头".into());
    }
    if settings.tts_provider == "openai"
        && settings.privacy_mode
        && !is_loopback_base_url(tts_base)
    {
        return Err(
            "隐私模式只允许本机 TTS 端点（如 http://127.0.0.1:1234/v1）；云端需要关闭隐私模式"
                .into(),
        );
    }
    if settings.tts_provider == "openai"
        && !is_loopback_base_url(tts_base)
        && !settings.tts_cloud_consent
    {
        return Err(
            "云端 TTS 会把合成文本发送至第三方：请先勾选「我知晓数据将发送至该端点」".into(),
        );
    }

    // R2a 2.1/2.2：ASR 链（原始录音出境，隐私口径与 LLM/TTS 一致）。
    if !ASR_PROVIDERS.contains(&settings.asr_provider.as_str()) {
        return Err(format!(
            "未知 ASR provider {:?}（仅 mock / whisper / openai）",
            settings.asr_provider
        ));
    }
    let asr_model = settings.asr_model.trim();
    if asr_model.chars().count() > MAX_MODEL_CHARS {
        return Err(format!("ASR 模型名过长（> {MAX_MODEL_CHARS} 字）"));
    }
    let asr_base = settings.asr_base_url.trim();
    if asr_base.chars().count() > MAX_URL_CHARS {
        return Err(format!("ASR base URL 过长（> {MAX_URL_CHARS} 字）"));
    }
    if settings.asr_provider != "mock" && asr_model.is_empty() {
        return Err("ASR 需要填写模型名（本地：tiny/base/small；云端：whisper-1）".into());
    }
    if settings.asr_provider == "openai" && asr_base.is_empty() {
        return Err("云端 ASR 需要填写 base URL（例：https://api.openai.com/v1）".into());
    }
    if !asr_base.is_empty()
        && !(asr_base.starts_with("http://") || asr_base.starts_with("https://"))
    {
        return Err("ASR base URL 需以 http:// 或 https:// 开头".into());
    }
    if settings.asr_provider == "openai"
        && settings.privacy_mode
        && !is_loopback_base_url(asr_base)
    {
        return Err(
            "隐私模式只允许本机 ASR 端点；云端语音识别会让原始录音出网，需关闭隐私模式"
                .into(),
        );
    }
    if settings.asr_provider == "openai"
        && !is_loopback_base_url(asr_base)
        && !settings.asr_cloud_consent
    {
        return Err(
            "云端 ASR 会把原始录音发送至第三方：请先勾选「我知晓录音将发送至该端点」".into(),
        );
    }

    let mut conn = open(path)?;
    let tx = conn
        .transaction()
        .map_err(|err| format!("写入设置失败（{}）：{err}", path.display()))?;
    write_json(&tx, KEY_PROVIDER, &Value::String(settings.provider.clone()))?;
    write_json(&tx, KEY_MODEL, &Value::String(model.to_string()))?;
    write_json(&tx, KEY_BASE_URL, &Value::String(base_url.to_string()))?;
    write_json(&tx, KEY_PRIVACY, &Value::Bool(settings.privacy_mode))?;
    write_json(
        &tx,
        KEY_TTS_PROVIDER,
        &Value::String(settings.tts_provider.clone()),
    )?;
    write_json(&tx, KEY_TTS_MODEL, &Value::String(tts_model.to_string()))?;
    write_json(&tx, KEY_TTS_BASE_URL, &Value::String(tts_base.to_string()))?;
    write_json(
        &tx,
        KEY_ASR_PROVIDER,
        &Value::String(settings.asr_provider.clone()),
    )?;
    write_json(&tx, KEY_ASR_MODEL, &Value::String(asr_model.to_string()))?;
    write_json(&tx, KEY_ASR_BASE_URL, &Value::String(asr_base.to_string()))?;
    write_json(
        &tx,
        KEY_LLM_CONSENT,
        &Value::Bool(settings.llm_cloud_consent),
    )?;
    write_json(
        &tx,
        KEY_ASR_CONSENT,
        &Value::Bool(settings.asr_cloud_consent),
    )?;
    write_json(
        &tx,
        KEY_TTS_CONSENT,
        &Value::Bool(settings.tts_cloud_consent),
    )?;
    // 云端音色只在 openai 链下有效：切走时清掉槽位，避免 sidecar 拿
    // `openai:nova` 去问本地 CosyVoice2（那会变成"选了但没用"）。
    if settings.tts_provider != "openai" {
        let _ = tx.execute(
            "UPDATE session SET voice_id = NULL WHERE voice_id LIKE 'openai:%'",
            [],
        );
    }
    tx.commit()
        .map_err(|err| format!("写入设置失败（{}）：{err}", path.display()))
}

/// R5：关窗是否驻留托盘（默认 true，兼容旧行为）。
pub fn read_close_to_tray(path: &Path) -> bool {
    open(path)
        .ok()
        .and_then(|conn| read_json(&conn, KEY_CLOSE_TO_TRAY).ok().flatten())
        .and_then(|value| value.as_bool())
        .unwrap_or(true)
}

pub fn write_close_to_tray(path: &Path, enabled: bool) -> Result<(), String> {
    let conn = open(path)?;
    write_json(&conn, KEY_CLOSE_TO_TRAY, &serde_json::Value::Bool(enabled))
}

/// R5：全局 PTT 快捷键（Tauri accelerator 字符串，如 `Alt+Space`）。
pub fn read_ptt_shortcut(path: &Path) -> Option<String> {
    open(path)
        .ok()
        .and_then(|conn| read_string(&conn, KEY_PTT_SHORTCUT).ok().flatten())
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

pub fn write_ptt_shortcut(path: &Path, accelerator: &str) -> Result<(), String> {
    let conn = open(path)?;
    write_json(
        &conn,
        KEY_PTT_SHORTCUT,
        &serde_json::Value::String(accelerator.trim().to_string()),
    )
}

fn open(path: &Path) -> Result<Connection, String> {    let conn = Connection::open(path)
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
    fn first_run_flag_is_independent_of_settings() {
        let path = temp_db();
        seed(&path);
        assert!(!read_settings(&path).expect("defaults").first_run_done);

        write_first_run_done(&path, true).expect("mark");
        assert!(read_settings(&path).expect("read").first_run_done);

        // 保存设置不该重置向导状态
        write_settings(&path, &SettingsView::default()).expect("save settings");
        assert!(read_settings(&path).expect("read").first_run_done);

        write_first_run_done(&path, false).expect("reset");
        assert!(!read_settings(&path).expect("read").first_run_done);
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
            ..SettingsView::default()
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

        let missing_consent = SettingsView {
            privacy_mode: false,
            base_url: "https://api.deepseek.com/v1".to_string(),
            ..cloud_with_privacy.clone()
        };
        let err =
            write_settings(&path, &missing_consent).expect_err("未勾选逐链同意应拒绝");
        assert!(err.contains("第三方"), "{err}");

        let ok = SettingsView {
            llm_cloud_consent: true,
            ..missing_consent
        };
        write_settings(&path, &ok).expect("write cloud");
        let read = read_settings(&path).expect("read");
        assert_eq!(read.provider, "openai");
        assert_eq!(read.base_url, "https://api.deepseek.com/v1");
        assert!(!read.privacy_mode);
        let _ = std::fs::remove_file(&path);
    }

    /// ADR-016 §3 矩阵：隐私模式下 `openai` + 环回地址允许（不出网），公网拒绝。
    #[test]
    fn loopback_openai_is_allowed_in_privacy_mode() {
        let path = temp_db();
        seed(&path);

        let loopback = SettingsView {
            provider: "openai".to_string(),
            model: "qwen3:8b".to_string(),
            privacy_mode: true,
            base_url: "http://127.0.0.1:11434/v1".to_string(),
            ..SettingsView::default()
        };
        write_settings(&path, &loopback).expect("环回端点应允许写库");
        let read = read_settings(&path).expect("read");
        assert_eq!(read.base_url, "http://127.0.0.1:11434/v1");
        assert!(read.privacy_mode);

        let public = SettingsView {
            base_url: "https://api.deepseek.com/v1".to_string(),
            ..loopback
        };
        let err = write_settings(&path, &public).expect_err("公网地址应被隐私模式拒绝");
        assert!(err.contains("隐私模式"), "{err}");

        // 判定只看主机名：端口、主机名大小写、IPv6 字面量都算本机
        assert!(is_loopback_base_url("http://LocalHost:1234/v1"));
        assert!(is_loopback_base_url("http://[::1]:1234/v1"));
        assert!(is_loopback_base_url("http://0.0.0.0:8080"));
        // 形近域名不能放行（防「127.0.0.1.evil.test」这类绕过）
        assert!(!is_loopback_base_url("https://127.0.0.1.evil.test/v1"));
        assert!(!is_loopback_base_url("https://api.openai.com/v1"));
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

    #[test]
    fn tts_settings_round_trip_and_privacy_matrix() {
        let path = temp_db();
        seed(&path);
        // 默认本地语音链
        assert_eq!(
            read_settings(&path).expect("defaults").tts_provider,
            "cosyvoice2"
        );

        let cloud = SettingsView {
            privacy_mode: false,
            tts_provider: "openai".to_string(),
            tts_model: "tts-1".to_string(),
            tts_base_url: "https://api.openai.com/v1".to_string(),
            tts_cloud_consent: true,
            ..SettingsView::default()
        };
        write_settings(&path, &cloud).expect("write tts cloud");
        // 未勾选逐链同意 → 拒绝
        let no_consent = SettingsView {
            tts_cloud_consent: false,
            ..cloud.clone()
        };
        assert!(write_settings(&path, &no_consent).is_err());
        let read = read_settings(&path).expect("read");
        assert_eq!(read.tts_provider, "openai");
        assert_eq!(read.tts_model, "tts-1");
        assert_eq!(read.tts_base_url, "https://api.openai.com/v1");

        // 云端 + 隐私模式：与 LLM 同口径拒绝
        let blocked = SettingsView {
            privacy_mode: true,
            ..cloud.clone()
        };
        assert!(write_settings(&path, &blocked).is_err());

        // 云端缺 base URL 拒绝
        let no_url = SettingsView {
            tts_base_url: String::new(),
            ..cloud
        };
        assert!(write_settings(&path, &no_url).is_err());

        // 未知 provider 拒绝（不静默改成 mock）
        let bad = SettingsView {
            tts_provider: "sovits".to_string(),
            ..SettingsView::default()
        };
        assert!(write_settings(&path, &bad).is_err());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn asr_settings_require_model_and_block_public_cloud_in_privacy_mode() {
        let path = temp_db();
        seed(&path);
        assert_eq!(
            read_settings(&path).expect("defaults").asr_provider,
            "whisper"
        );

        // 本地 whisper 缺模型名 → 拒绝
        let no_model = SettingsView {
            asr_model: String::new(),
            ..SettingsView::default()
        };
        assert!(write_settings(&path, &no_model).is_err());

        let cloud = SettingsView {
            privacy_mode: false,
            asr_provider: "openai".to_string(),
            asr_model: "whisper-1".to_string(),
            asr_base_url: "https://api.openai.com/v1".to_string(),
            asr_cloud_consent: true,
            ..SettingsView::default()
        };
        write_settings(&path, &cloud).expect("write asr cloud");
        // 未勾选逐链同意 → 拒绝
        let no_consent = SettingsView {
            asr_cloud_consent: false,
            ..cloud.clone()
        };
        assert!(write_settings(&path, &no_consent).is_err());
        let read = read_settings(&path).expect("read");
        assert_eq!(read.asr_provider, "openai");
        assert_eq!(read.asr_model, "whisper-1");

        // 云端 + 隐私模式：原始录音不出网
        let blocked = SettingsView {
            privacy_mode: true,
            ..cloud.clone()
        };
        assert!(write_settings(&path, &blocked).is_err());

        // 云端缺 base URL
        let no_url = SettingsView {
            asr_base_url: String::new(),
            ..cloud
        };
        assert!(write_settings(&path, &no_url).is_err());

        // 未知 provider
        let bad = SettingsView {
            asr_provider: "sensevoice".to_string(),
            ..SettingsView::default()
        };
        assert!(write_settings(&path, &bad).is_err());
        let _ = std::fs::remove_file(&path);
    }
}
