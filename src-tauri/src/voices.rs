//! 音色槽位（ADR-008 / 2.5）：壳读 `voice` 表、写 `session.voice_id`；
//! sidecar 每轮拉取（3.4 同款语义），turn 收尾不回写，避免覆盖轮间切换。
//!
//! `builtin:default` 不落 voice 表（2.5 保留 ID），列表里作为虚拟项返回；
//! 只有 `status=ready` 的克隆音色可被选中。

use std::path::Path;
use std::time::Duration;

use rusqlite::{Connection, OptionalExtension, params};
use serde::{Deserialize, Serialize};

pub const BUILTIN_VOICE_ID: &str = "builtin:default";

/// R2a 2.4：云端预置音色（虚拟项，不落 voice 表）。
///
/// 只有 `tts_provider=openai` 时出现在列表里；选中后写进 `session.voice_id`，
/// sidecar 的 `OpenAITtsEngine._voice_for` 直接透传（`openai:` 前缀）。
pub const CLOUD_VOICES: [(&str, &str); 4] = [
    ("openai:alloy", "云端 · Alloy"),
    ("openai:nova", "云端 · Nova"),
    ("openai:shimmer", "云端 · Shimmer"),
    ("openai:onyx", "云端 · Onyx"),
];

fn cloud_voice_name(voice_id: &str) -> Option<&'static str> {
    CLOUD_VOICES
        .iter()
        .find(|(id, _)| *id == voice_id)
        .map(|(_, name)| *name)
}

/// 读 setting 表的语音链 provider（JSON 编码的字符串；表缺失按空处理）。
fn tts_provider(conn: &Connection) -> String {
    let raw: Option<String> = conn
        .query_row(
            "SELECT value FROM setting WHERE key = 'tts_provider'",
            [],
            |row| row.get(0),
        )
        .optional()
        .ok()
        .flatten();
    raw.and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
        .and_then(|value| value.as_str().map(|text| text.to_string()))
        .unwrap_or_default()
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VoiceView {
    pub id: String,
    pub display_name: String,
    pub status: String,
    pub quality_score: Option<f64>,
    pub created_at: f64,
    pub selected: bool,
}

/// 列出内置音色 + 全部克隆音色（含 training/failed，UI 置灰）。
pub fn list_voices(path: &Path) -> Result<Vec<VoiceView>, String> {
    let conn = open(path)?;
    let current: Option<String> = conn
        .query_row(
            "SELECT voice_id FROM session ORDER BY last_active_at DESC LIMIT 1",
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|err| format!("读取当前音色失败（{}）：{err}", path.display()))?
        .flatten();

    let mut voices = vec![VoiceView {
        id: BUILTIN_VOICE_ID.to_string(),
        display_name: "内置音色".to_string(),
        status: "ready".to_string(),
        quality_score: None,
        created_at: 0.0,
        selected: current.is_none(),
    }];

    if tts_provider(&conn) == "openai" {
        for (id, name) in CLOUD_VOICES {
            voices.push(VoiceView {
                id: id.to_string(),
                display_name: name.to_string(),
                status: "ready".to_string(),
                quality_score: None,
                created_at: 0.0,
                selected: current.as_deref() == Some(id),
            });
        }
    }

    let mut stmt = conn
        .prepare(
            "SELECT id, display_name, status, quality_score, created_at
             FROM voice ORDER BY created_at ASC",
        )
        .map_err(|err| format!("读取音色列表失败（{}）：{err}", path.display()))?;
    let rows = stmt
        .query_map([], |row| {
            Ok(VoiceView {
                id: row.get(0)?,
                display_name: row.get(1)?,
                status: row.get(2)?,
                quality_score: row.get(3)?,
                created_at: row.get(4)?,
                selected: false,
            })
        })
        .map_err(|err| format!("读取音色列表失败（{}）：{err}", path.display()))?;
    for row in rows {
        let mut voice = row.map_err(|err| format!("读取音色行失败：{err}"))?;
        voice.selected = current.as_deref() == Some(voice.id.as_str());
        voices.push(voice);
    }
    Ok(voices)
}

/// 切换当前会话音色；`builtin:default` 写 NULL（2.5 none 态）。
pub fn select_voice(path: &Path, voice_id: &str) -> Result<(), String> {
    let voice_id = voice_id.trim();
    if voice_id.is_empty() {
        return Err("voice_id 不能为空".to_string());
    }

    let mut conn = open(path)?;
    let tx = conn
        .transaction()
        .map_err(|err| format!("切换音色失败（{}）：{err}", path.display()))?;

    let session_id: Option<String> = tx
        .query_row(
            "SELECT id FROM session ORDER BY last_active_at DESC LIMIT 1",
            [],
            |row| row.get(0),
        )
        .optional()
        .map_err(|err| format!("读取会话失败：{err}"))?;
    let Some(session_id) = session_id else {
        return Err("sidecar 尚未创建会话（请稍后重试）".to_string());
    };

    if voice_id == BUILTIN_VOICE_ID {
        tx.execute(
            "UPDATE session SET voice_id = NULL WHERE id = ?1",
            params![session_id],
        )
        .map_err(|err| format!("切回内置音色失败：{err}"))?;
    } else if cloud_voice_name(voice_id).is_some() {
        // R2a 2.4：云端预置音色是虚拟项，不查 voice 表，只写会话槽位
        tx.execute(
            "UPDATE session SET voice_id = ?1 WHERE id = ?2",
            params![voice_id, session_id],
        )
        .map_err(|err| format!("切换云端音色失败：{err}"))?;
    } else {
        let status: Option<String> = tx
            .query_row(
                "SELECT status FROM voice WHERE id = ?1",
                params![voice_id],
                |row| row.get(0),
            )
            .optional()
            .map_err(|err| format!("读取音色失败：{err}"))?;
        let Some(status) = status else {
            return Err(format!("音色不存在：{voice_id}"));
        };
        if status != "ready" {
            return Err(format!("音色尚未就绪或已失败（status={status}）"));
        }
        tx.execute(
            "UPDATE session SET voice_id = ?1 WHERE id = ?2",
            params![voice_id, session_id],
        )
        .map_err(|err| format!("切换音色失败：{err}"))?;
    }

    tx.commit()
        .map_err(|err| format!("切换音色失败（{}）：{err}", path.display()))
}

fn open(path: &Path) -> Result<Connection, String> {
    let conn = Connection::open(path)
        .map_err(|err| format!("打开音色库失败（{}）：{err}", path.display()))?;
    conn.busy_timeout(Duration::from_millis(5000))
        .map_err(|err| format!("音色库 busy_timeout 失败（{}）：{err}", path.display()))?;
    Ok(conn)
}

/// R5：音色改名（只改显示名，不动样本/克隆产物）。
pub fn rename_voice(path: &Path, voice_id: &str, display_name: &str) -> Result<(), String> {
    let name = display_name.trim();
    if name.is_empty() {
        return Err("音色名不能为空".into());
    }
    if name.chars().count() > MAX_VOICE_NAME_CHARS {
        return Err(format!("音色名过长（> {MAX_VOICE_NAME_CHARS} 字）"));
    }
    let conn = open(path)?;
    let changed = conn
        .execute(
            "UPDATE voice SET display_name = ?1 WHERE id = ?2",
            params![name, voice_id],
        )
        .map_err(|err| format!("音色改名失败（{}）：{err}", path.display()))?;
    if changed == 0 {
        return Err(format!("音色不存在：{voice_id}"));
    }
    Ok(())
}

/// R5：删除音色。被任何会话绑定时拒绝（会给出 `VOICE_IN_USE` 语义的提示），
/// 删除成功后再清理 assets 下的样本/克隆文件（越界路径一律不碰）。
pub fn delete_voice(path: &Path, voice_id: &str) -> Result<(), String> {
    let mut conn = open(path)?;
    let tx = conn
        .transaction()
        .map_err(|err| format!("删除音色失败（{}）：{err}", path.display()))?;
    let assets: Option<(Option<String>, Option<String>)> = tx
        .query_row(
            "SELECT sample_path, model_path FROM voice WHERE id = ?1",
            params![voice_id],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .optional()
        .map_err(|err| format!("读取音色失败：{err}"))?;
    let Some((sample, model)) = assets else {
        return Err(format!("音色不存在：{voice_id}"));
    };

    let bound: i64 = tx
        .query_row(
            "SELECT COUNT(*) FROM session WHERE voice_id = ?1",
            params![voice_id],
            |row| row.get(0),
        )
        .map_err(|err| format!("检查音色占用失败：{err}"))?;
    if bound > 0 {
        return Err("该音色正被会话使用：请先切换到内置音色再删除（VOICE_IN_USE）".into());
    }

    tx.execute("DELETE FROM voice WHERE id = ?1", params![voice_id])
        .map_err(|err| format!("删除音色失败：{err}"))?;
    tx.commit()
        .map_err(|err| format!("删除音色失败（{}）：{err}", path.display()))?;

    if let Some(root) = asset_root(path) {
        for relative in [sample, model].into_iter().flatten() {
            remove_asset(&root, &relative);
        }
    }
    Ok(())
}

const MAX_VOICE_NAME_CHARS: usize = 30;

/// `<data>/assets`：与 sidecar `db/paths.py` 同布局（db 目录的上一级）。
fn asset_root(db_file: &Path) -> Option<std::path::PathBuf> {
    let db_dir = db_file.parent()?;
    let data_root = db_dir.parent()?;
    Some(data_root.join("assets"))
}

/// 只删 assets 内的相对路径；`..` / 绝对路径 / 不存在的文件都跳过。
fn remove_asset(root: &Path, relative: &str) {
    let rel = Path::new(relative);
    if rel.is_absolute()
        || rel.components().any(|part| {
            matches!(
                part,
                std::path::Component::ParentDir | std::path::Component::RootDir
            )
        })
    {
        return;
    }
    let target = root.join(rel);
    if target.is_file() {
        let _ = std::fs::remove_file(target);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_db() -> std::path::PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir().join(format!(
            "echoes-voices-test-{}-{stamp}.db",
            std::process::id()
        ))
    }

    fn seed(path: &Path) {
        let conn = Connection::open(path).expect("open");
        conn.execute_batch(
            "CREATE TABLE voice (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                sample_path TEXT NOT NULL,
                model_path TEXT,
                status TEXT NOT NULL,
                quality_score REAL,
                created_at REAL NOT NULL
            );
            CREATE TABLE session (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL,
                persona_id TEXT NOT NULL,
                voice_id TEXT,
                started_at REAL NOT NULL,
                last_active_at REAL NOT NULL
            );
            INSERT INTO voice VALUES ('clone:ready', '音色 1', 'a.wav', 'a.pt', 'ready', NULL, 2);
            INSERT INTO voice VALUES ('clone:failed', '音色 2', 'b.wav', NULL, 'failed', NULL, 3);
            INSERT INTO session VALUES ('default', 'default', 'default', 'clone:ready', 1, 1);",
        )
        .expect("schema");
    }

    #[test]
    fn list_includes_builtin_and_marks_selected() {
        let path = temp_db();
        seed(&path);
        let voices = list_voices(&path).expect("list");
        assert_eq!(voices.len(), 3);
        assert_eq!(voices[0].id, BUILTIN_VOICE_ID);
        assert!(!voices[0].selected);
        assert!(
            voices
                .iter()
                .any(|voice| voice.id == "clone:ready" && voice.selected)
        );
        assert!(
            voices
                .iter()
                .any(|voice| voice.id == "clone:failed" && voice.status == "failed")
        );
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn select_ready_voice_and_builtin() {
        let path = temp_db();
        seed(&path);
        select_voice(&path, "clone:ready").expect("ready");
        assert!(
            list_voices(&path)
                .expect("list")
                .iter()
                .any(|voice| voice.id == "clone:ready" && voice.selected)
        );

        select_voice(&path, BUILTIN_VOICE_ID).expect("builtin");
        let voices = list_voices(&path).expect("list");
        assert!(voices[0].selected);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn rejects_failed_missing_and_empty() {
        let path = temp_db();
        seed(&path);
        assert!(select_voice(&path, "clone:failed").is_err());
        assert!(select_voice(&path, "clone:missing").is_err());
        assert!(select_voice(&path, "   ").is_err());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn missing_session_is_an_error() {
        let path = temp_db();
        let conn = Connection::open(&path).expect("open");
        conn.execute_batch(
            "CREATE TABLE voice (id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
             sample_path TEXT NOT NULL, model_path TEXT, status TEXT NOT NULL,
             quality_score REAL, created_at REAL NOT NULL);
             CREATE TABLE session (id TEXT PRIMARY KEY, profile_id TEXT NOT NULL,
             persona_id TEXT NOT NULL, voice_id TEXT, started_at REAL NOT NULL,
             last_active_at REAL NOT NULL);",
        )
        .expect("schema");
        drop(conn);
        assert!(select_voice(&path, BUILTIN_VOICE_ID).is_err());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn rename_voice_updates_name_and_rejects_bad_input() {
        let path = temp_db();
        seed(&path);
        rename_voice(&path, "clone:ready", "  小雨  ").expect("rename");
        let voices = list_voices(&path).expect("list");
        assert!(
            voices
                .iter()
                .any(|voice| voice.id == "clone:ready" && voice.display_name == "小雨")
        );
        assert!(rename_voice(&path, "clone:ready", "  ").is_err());
        assert!(rename_voice(&path, "clone:missing", "x").is_err());
        assert!(rename_voice(&path, "clone:ready", &"x".repeat(31)).is_err());
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn delete_voice_rejects_bound_and_removes_assets() {
        let root = std::env::temp_dir().join(format!(
            "echoes-voices-del-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock")
                .as_nanos()
        ));
        std::fs::create_dir_all(root.join("db")).expect("db dir");
        std::fs::create_dir_all(root.join("assets")).expect("assets dir");
        let path = root.join("db").join("echoes.db");
        seed(&path);
        std::fs::write(root.join("assets").join("b.wav"), b"x").expect("sample");

        // 被会话绑定的音色不能删
        let err = delete_voice(&path, "clone:ready").expect_err("bound");
        assert!(err.contains("VOICE_IN_USE"), "{err}");

        // 未绑定的失败音色可以删，样本文件一并清理
        delete_voice(&path, "clone:failed").expect("delete");
        assert!(!root.join("assets").join("b.wav").exists());
        assert!(
            !list_voices(&path)
                .expect("list")
                .iter()
                .any(|voice| voice.id == "clone:failed")
        );

        // 解绑后可删 ready 音色
        let conn = Connection::open(&path).expect("open");
        conn.execute("UPDATE session SET voice_id = NULL", [])
            .expect("unbind");
        drop(conn);
        delete_voice(&path, "clone:ready").expect("delete ready");
        assert!(
            !list_voices(&path)
                .expect("list")
                .iter()
                .any(|voice| voice.id == "clone:ready")
        );
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn delete_voice_ignores_assets_outside_root() {
        let root = std::env::temp_dir().join(format!(
            "echoes-voices-escape-{}-{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock")
                .as_nanos()
        ));
        std::fs::create_dir_all(root.join("db")).expect("db dir");
        let path = root.join("db").join("echoes.db");
        seed(&path);
        let outside = root.join("outside.wav");
        std::fs::write(&outside, b"keep").expect("outside");
        let conn = Connection::open(&path).expect("open");
        conn.execute(
            "UPDATE voice SET sample_path = '../outside.wav' WHERE id = 'clone:failed'",
            [],
        )
        .expect("escape path");
        drop(conn);

        delete_voice(&path, "clone:failed").expect("delete");
        assert!(outside.exists(), "越界路径不应被删除");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn cloud_voices_appear_only_when_tts_provider_is_openai() {        let path = temp_db();
        seed(&path);
        // 默认本地链：列表里没有云端音色
        assert!(
            !list_voices(&path)
                .expect("list")
                .iter()
                .any(|voice| voice.id.starts_with("openai:"))
        );

        let conn = Connection::open(&path).expect("open");
        conn.execute_batch(
            "CREATE TABLE setting (key TEXT PRIMARY KEY, value TEXT NOT NULL);
             INSERT INTO setting VALUES ('tts_provider', '\"openai\"');",
        )
        .expect("setting");
        drop(conn);

        let voices = list_voices(&path).expect("list");
        assert!(voices.iter().any(|voice| voice.id == "openai:nova"));
        select_voice(&path, "openai:nova").expect("select cloud voice");
        let voices = list_voices(&path).expect("list");
        assert!(
            voices
                .iter()
                .any(|voice| voice.id == "openai:nova" && voice.selected)
        );

        // 未登记的云端音色不能选（避免手改库写出引擎不认识的 id）
        assert!(select_voice(&path, "openai:unknown").is_err());
        let _ = std::fs::remove_file(&path);
    }
}
