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
}
