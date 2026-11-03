//! R5 数据面：导出 / 导入 / 手动备份 / 彻底删除 / 诊断包。
//!
//! **导出与导入为什么走 sidecar 一次性进程**：`memory_vec` / `turn_chunk_vec` 是
//! sqlite-vec 虚表，壳的 rusqlite 连接没有加载扩展（`voices.rs` / `memory.rs` 同款
//! 口径）。带向量的导出/导入只能在 Python 侧做；这里只负责起进程、校验一行结果。
//!
//! **手动备份**：`VACUUM INTO` 出一份完整的 .db（含 WAL 里的已提交数据），落在
//! `backup/manual-<ts>.db`，与迁移备份同目录、同恢复入口。
//!
//! **彻底删除**：只删数据根下已知的个人数据子目录与迁移标记，不动模型权重、不动
//! 根目录本身；调用方必须先停 sidecar（Windows 上打开的 .db 删不掉）。

use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::{profile, secrets, setup};

/// 彻底删除需要用户原样输入这句话：误触代价不可逆，不能只靠一个按钮。
pub const WIPE_CONFIRM: &str = "删除全部数据";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WipeResult {
    pub removed: Vec<String>,
    pub cleared_keys: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportResult {
    pub path: String,
    #[serde(default)]
    pub sessions: u64,
    #[serde(default)]
    pub turns: u64,
    #[serde(default)]
    pub memories: u64,
    #[serde(default)]
    pub chunks: u64,
    #[serde(default)]
    pub bytes: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ImportResult {
    #[serde(default)]
    pub sessions: u64,
    #[serde(default)]
    pub turns: u64,
    #[serde(default)]
    pub memories: u64,
    #[serde(default)]
    pub chunks: u64,
}

/// 时间戳后缀：`20261030-153000`（文件名可排序、无特殊字符）。
fn stamp() -> String {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|value| value.as_secs())
        .unwrap_or(0);
    format_utc(now)
}

/// 秒级时间戳 → UTC `YYYYMMDD-HHMMSS`（不引 chrono：只需要文件名）。
fn format_utc(seconds: u64) -> String {
    let days = (seconds / 86_400) as i64;
    let rest = seconds % 86_400;
    let (hour, minute, second) = (rest / 3600, (rest % 3600) / 60, rest % 60);
    // 1970-01-01 起的天数 → 公历年月日（Howard Hinnant 的 civil_from_days）
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = if mp < 10 { mp + 3 } else { mp - 9 };
    let year = if month <= 2 { y + 1 } else { y };
    format!("{year:04}{month:02}{day:02}-{hour:02}{minute:02}{second:02}")
}

pub fn default_export_path(root: &Path) -> PathBuf {
    root.join("exports")
        .join(format!("echoes-export-{}.json", stamp()))
}

pub fn default_diagnostics_path(root: &Path) -> PathBuf {
    root.join("exports")
        .join(format!("echoes-diagnostics-{}.json", stamp()))
}

fn result_payload(value: &Value, action: &str) -> Result<Value, String> {
    if value.get("type").and_then(Value::as_str) == Some("error") {
        return Err(value
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or(action)
            .to_string());
    }
    if value.get("type").and_then(Value::as_str) != Some("result") {
        return Err(format!("{action} 没有返回结果：{value}"));
    }
    Ok(value.clone())
}

fn parse_export(value: &Value) -> Result<ExportResult, String> {
    let payload = result_payload(value, "导出失败")?;
    serde_json::from_value(payload).map_err(|err| format!("导出结果不可解析：{err}"))
}

fn parse_import(value: &Value) -> Result<ImportResult, String> {
    let payload = result_payload(value, "导入失败")?;
    serde_json::from_value(payload).map_err(|err| format!("导入结果不可解析：{err}"))
}

/// 导出到 `dest`（None = 数据根下 `exports/echoes-export-<ts>.json`）。
pub fn export(sidecar_dir: &Path, dest: Option<&Path>) -> Result<ExportResult, String> {
    let target = dest
        .map(Path::to_path_buf)
        .unwrap_or_else(|| default_export_path(&profile::root_dir()));
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("创建导出目录失败：{}（{err}）", parent.display()))?;
    }
    if target.extension().and_then(|ext| ext.to_str()) != Some("json") {
        return Err("导出文件必须是 .json".into());
    }
    let args = vec![
        "data-export".to_string(),
        "--path".to_string(),
        target.to_string_lossy().into_owned(),
    ];
    let value = setup::run(sidecar_dir, &args, |_| {})?;
    parse_export(&value)
}

/// 合并导入一个导出包；同 id 保留现有记录。
pub fn import(sidecar_dir: &Path, source: &Path) -> Result<ImportResult, String> {
    if !source.is_file() {
        return Err(format!("找不到导入文件：{}", source.display()));
    }
    let args = vec![
        "data-import".to_string(),
        "--path".to_string(),
        source.to_string_lossy().into_owned(),
    ];
    let value = setup::run(sidecar_dir, &args, |_| {})?;
    parse_import(&value)
}

/// 手动备份：`VACUUM INTO backup/manual-<ts>.db`，返回备份路径。
pub fn backup(root: &Path) -> Result<String, String> {
    let db = root.join("db").join("echoes.db");
    if !db.is_file() {
        return Err("数据库还不存在，先完成首次启动再备份".into());
    }
    let dir = root.join("backup");
    fs::create_dir_all(&dir)
        .map_err(|err| format!("创建备份目录失败：{}（{err}）", dir.display()))?;
    let target = dir.join(format!("manual-{}.db", stamp()));
    let conn = rusqlite::Connection::open(&db)
        .map_err(|err| format!("打开数据库失败：{err}"))?;
    let path = target.to_string_lossy().into_owned();
    conn.execute("VACUUM INTO ?1", [&path])
        .map_err(|err| format!("备份失败：{err}"))?;
    // 同步落盘：备份是灾难恢复资产，不能只停在写缓存里
    if let Ok(file) = fs::File::open(&target) {
        let _ = file.sync_all();
    }
    Ok(path)
}

/// 删除个人数据（调用方须先停 sidecar）。返回实际删除的路径。
pub fn wipe(root: &Path) -> Result<Vec<String>, String> {
    if root.as_os_str().is_empty() {
        return Err("数据目录为空，拒绝删除".into());
    }
    let mut removed = Vec::new();
    for name in ["db", "backup", "assets", "logs", "exports"] {
        let path = root.join(name);
        if !path.exists() {
            continue;
        }
        fs::remove_dir_all(&path)
            .map_err(|err| format!("删除 {} 失败：{err}", path.display()))?;
        removed.push(path.to_string_lossy().into_owned());
    }
    for name in ["migration_failed.json", "settings.json"] {
        let path = root.join(name);
        if path.is_file() {
            fs::remove_file(&path)
                .map_err(|err| format!("删除 {} 失败：{err}", path.display()))?;
            removed.push(path.to_string_lossy().into_owned());
        }
    }
    Ok(removed)
}

/// 清掉所有已保存的云端 key（彻底删除的一部分；凭据在系统凭据管理器里）。
pub fn clear_cloud_keys() -> Vec<String> {
    let accounts = [
        secrets::LLM_ACCOUNT.to_string(),
        secrets::engine_account("asr", "openai"),
        secrets::engine_account("tts", "openai"),
    ];
    let mut cleared = Vec::new();
    for account in accounts {
        if secrets::has_key_for(&account) && secrets::clear_for(&account).is_ok() {
            cleared.push(account);
        }
    }
    cleared
}

/// 诊断包：环境 + 数据规模 + 备份 + 模型占用 + 脱敏设置。**不含**对话原文与 key。
pub fn diagnostics(root: &Path) -> Result<Value, String> {
    let db = root.join("db").join("echoes.db");
    let counts = if db.is_file() {
        match rusqlite::Connection::open(&db) {
            Ok(conn) => json!({
                "sessions": count(&conn, "session"),
                "turns": count(&conn, "turn"),
                "memories": count(&conn, "memory_fact"),
                "chunks": count(&conn, "turn_chunk"),
                "summaries": count(&conn, "session_summary"),
            }),
            Err(err) => json!({ "error": err.to_string() }),
        }
    } else {
        json!(null)
    };

    let settings = profile::read_settings(&db).ok().map(|settings| {
        json!({
            "llmProvider": settings.provider,
            "llmModel": settings.model,
            "llmBaseUrl": mask_url(&settings.base_url),
            "hasLlmKey": secrets::has_key(),
            "asrProvider": settings.asr_provider,
            "asrModel": settings.asr_model,
            "asrBaseUrl": mask_url(&settings.asr_base_url),
            "hasAsrKey": secrets::has_key_for(&secrets::engine_account("asr", "openai")),
            "ttsProvider": settings.tts_provider,
            "ttsModel": settings.tts_model,
            "ttsBaseUrl": mask_url(&settings.tts_base_url),
            "hasTtsKey": secrets::has_key_for(&secrets::engine_account("tts", "openai")),
            "privacyMode": settings.privacy_mode,
            "llmCloudConsent": settings.llm_cloud_consent,
            "asrCloudConsent": settings.asr_cloud_consent,
            "ttsCloudConsent": settings.tts_cloud_consent,
        })
    });

    let models_root = models_root();
    let mut models = Vec::new();
    if let Ok(entries) = fs::read_dir(&models_root) {
        for entry in entries.flatten() {
            let path = entry.path();
            if !path.is_dir() {
                continue;
            }
            models.push(json!({
                "name": entry.file_name().to_string_lossy(),
                "bytes": dir_size(&path),
            }));
        }
    }
    models.sort_by(|left, right| {
        left.get("name")
            .and_then(Value::as_str)
            .cmp(&right.get("name").and_then(Value::as_str))
    });

    Ok(json!({
        "generatedAt": SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|value| value.as_secs())
            .unwrap_or(0),
        "appVersion": env!("CARGO_PKG_VERSION"),
        "os": std::env::consts::OS,
        "arch": std::env::consts::ARCH,
        "dataRoot": root.to_string_lossy(),
        "db": {
            "path": db.to_string_lossy(),
            "exists": db.is_file(),
            "bytes": fs::metadata(&db).map(|meta| meta.len()).unwrap_or(0),
            "counts": counts,
        },
        "migrationFailed": root.join("migration_failed.json").is_file(),
        "backupDir": root.join("backup").to_string_lossy(),
        "modelsRoot": models_root.to_string_lossy(),
        "models": models,
        "settings": settings,
        "note": "诊断包不含对话原文、记忆内容与 API key",
    }))
}

/// 写诊断包到数据根 `exports/`，返回 `{path, bytes}`。
pub fn write_diagnostics(root: &Path) -> Result<Value, String> {
    let value = diagnostics(root)?;
    let target = default_diagnostics_path(root);
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("创建导出目录失败：{}（{err}）", parent.display()))?;
    }
    let text = serde_json::to_string_pretty(&value)
        .map_err(|err| format!("诊断包序列化失败：{err}"))?;
    fs::write(&target, &text)
        .map_err(|err| format!("写诊断包失败：{}（{err}）", target.display()))?;
    Ok(json!({
        "path": target.to_string_lossy(),
        "bytes": text.len(),
    }))
}

fn count(conn: &rusqlite::Connection, table: &str) -> Option<i64> {
    conn.query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |row| row.get(0))
        .ok()
}

/// 保留 scheme + host，遮掉 path/query（base_url 可能带网关前缀或临时 token）。
fn mask_url(url: &str) -> String {
    let trimmed = url.trim().trim_end_matches('/');
    if trimmed.is_empty() {
        return String::new();
    }
    match trimmed.split_once("://") {
        Some((scheme, rest)) => {
            let host = rest.split('/').next().unwrap_or(rest);
            format!("{scheme}://{host}")
        }
        None => trimmed.split('/').next().unwrap_or(trimmed).to_string(),
    }
}

fn models_root() -> PathBuf {
    match std::env::var("ECHOES_MODELS_DIR") {
        Ok(value) if !value.trim().is_empty() => PathBuf::from(value),
        _ => {
            let home = std::env::var("HOME")
                .or_else(|_| std::env::var("USERPROFILE"))
                .unwrap_or_default();
            PathBuf::from(home).join(".cache").join("echoes").join("models")
        }
    }
}

fn dir_size(path: &Path) -> u64 {
    let mut total = 0;
    let Ok(entries) = fs::read_dir(path) else {
        return 0;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            total += dir_size(&path);
        } else {
            total += entry.metadata().map(|meta| meta.len()).unwrap_or(0);
        }
    }
    total
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_root(tag: &str) -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir().join(format!(
            "echoes-data-{tag}-{}-{nanos}",
            std::process::id()
        ))
    }

    #[test]
    fn utc_format_matches_known_dates() {
        assert_eq!(format_utc(0), "19700101-000000");
        // 2026-10-30T12:00:00Z
        assert_eq!(format_utc(1_793_361_600), "20261030-120000");
        assert_eq!(format_utc(1_709_164_800), "20240229-000000");
    }

    #[test]
    fn default_paths_live_under_exports() {
        let root = Path::new("C:/tmp/echoes");
        assert!(default_export_path(root).starts_with(root.join("exports")));
        assert!(
            default_export_path(root)
                .extension()
                .is_some_and(|ext| ext == "json")
        );
        assert!(default_diagnostics_path(root).starts_with(root.join("exports")));
    }

    #[test]
    fn backup_writes_a_readable_copy() {
        let root = temp_root("backup");
        fs::create_dir_all(root.join("db")).expect("db dir");
        let db = root.join("db").join("echoes.db");
        let conn = rusqlite::Connection::open(&db).expect("open");
        conn.execute_batch("CREATE TABLE t (x TEXT); INSERT INTO t VALUES ('hi');")
            .expect("seed");
        drop(conn);

        let path = backup(&root).expect("backup");
        let copy = rusqlite::Connection::open(&path).expect("open backup");
        let value: String = copy
            .query_row("SELECT x FROM t", [], |row| row.get(0))
            .expect("read backup");
        assert_eq!(value, "hi");
        drop(copy);
        assert!(Path::new(&path).starts_with(root.join("backup")));
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn backup_without_database_is_an_error() {
        let root = temp_root("nodb");
        fs::create_dir_all(&root).expect("root");
        assert!(backup(&root).is_err());
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn wipe_removes_personal_dirs_but_keeps_root_and_others() {
        let root = temp_root("wipe");
        for name in ["db", "backup", "assets", "logs", "exports"] {
            fs::create_dir_all(root.join(name)).expect("dir");
            fs::write(root.join(name).join("x.txt"), b"x").expect("file");
        }
        fs::write(root.join("migration_failed.json"), b"{}").expect("marker");
        fs::write(root.join("keep.txt"), b"keep").expect("keep");

        let removed = wipe(&root).expect("wipe");
        assert_eq!(removed.len(), 6);
        for name in ["db", "backup", "assets", "logs", "exports"] {
            assert!(!root.join(name).exists(), "{name} 应被删除");
        }
        assert!(!root.join("migration_failed.json").exists());
        assert_eq!(fs::read(root.join("keep.txt")).expect("keep"), b"keep");
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn diagnostics_redacts_url_paths_and_omits_transcripts() {
        let root = temp_root("diag");
        fs::create_dir_all(root.join("db")).expect("db dir");
        let db = root.join("db").join("echoes.db");
        let conn = rusqlite::Connection::open(&db).expect("open");
        conn.execute_batch(
            "CREATE TABLE session (id TEXT); CREATE TABLE turn (user_text TEXT);\
             INSERT INTO session VALUES ('s1');\
             INSERT INTO turn VALUES ('很私密的一句话');",
        )
        .expect("seed");
        drop(conn);

        let value = diagnostics(&root).expect("diagnostics");
        let text = value.to_string();
        assert_eq!(value["db"]["counts"]["sessions"], json!(1));
        assert_eq!(value["db"]["counts"]["turns"], json!(1));
        assert!(!text.contains("很私密的一句话"));
        assert!(!text.contains("apiKey"));
        fs::remove_dir_all(root).ok();
    }

    #[test]
    fn mask_url_keeps_only_origin() {
        assert_eq!(
            mask_url("https://gw.example.com/v1?token=abc"),
            "https://gw.example.com"
        );
        assert_eq!(mask_url("http://127.0.0.1:11434/v1"), "http://127.0.0.1:11434");
        assert_eq!(mask_url(""), "");
    }

    #[test]
    fn result_payload_surfaces_sidecar_errors() {
        let value = json!({"type": "error", "message": "导出失败：磁盘满"});
        assert!(result_payload(&value, "导出失败").is_err());
        let ok = json!({"type": "result", "path": "x.json", "turns": 2});
        let parsed = parse_export(&ok).expect("parse");
        assert_eq!(parsed.turns, 2);
        assert_eq!(parsed.sessions, 0);
    }
}
