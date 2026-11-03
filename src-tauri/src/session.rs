//! R1c 会话生命周期：列表 / 新建 / 改名 / 归档 / 删除。
//!
//! 写操作仍是壳侧直接 SQLite（与 voices/profile 同口径）；sidecar 只负责
//! “当前活跃会话”的运行时切换。

use std::path::Path;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionView {
    pub id: String,
    pub title: Option<String>,
    pub started_at: f64,
    pub last_active_at: f64,
    pub archived_at: Option<f64>,
}

pub fn list(path: &Path, include_archived: bool) -> Result<Vec<SessionView>, String> {
    let conn = open(path)?;
    let sql = if include_archived {
        "SELECT id, title, started_at, last_active_at, archived_at
         FROM session ORDER BY last_active_at DESC"
    } else {
        "SELECT id, title, started_at, last_active_at, archived_at
         FROM session WHERE archived_at IS NULL ORDER BY last_active_at DESC"
    };
    let mut stmt = conn
        .prepare(sql)
        .map_err(|err| format!("读取会话列表失败：{err}"))?;
    let rows = stmt
        .query_map([], session_from_row)
        .map_err(|err| format!("读取会话列表失败：{err}"))?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|err| format!("读取会话列表失败：{err}"))
}

pub fn latest_id(path: &Path) -> Result<String, String> {
    let conn = open(path)?;
    conn.query_row(
        "SELECT id FROM session WHERE archived_at IS NULL
         ORDER BY last_active_at DESC LIMIT 1",
        [],
        |row| row.get(0),
    )
    .optional()
    .map_err(|err| format!("读取当前会话失败：{err}"))?
    .ok_or_else(|| "还没有可用会话".to_string())
}

pub fn create(path: &Path, title: Option<String>) -> Result<SessionView, String> {
    let now = unix_now();
    let title = title
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());
    let id = format!(
        "s-{}",
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or(0)
    );
    let conn = open(path)?;
    conn.execute(
        "INSERT INTO session
         (id, profile_id, persona_id, voice_id, started_at, last_active_at, title)
         VALUES (?1, 'default', 'default', NULL, ?2, ?2, ?3)",
        params![id, now, title],
    )
    .map_err(|err| format!("新建会话失败（默认人设是否已创建？）：{err}"))?;
    Ok(SessionView {
        id,
        title,
        started_at: now,
        last_active_at: now,
        archived_at: None,
    })
}

pub fn rename(path: &Path, session_id: &str, title: &str) -> Result<(), String> {
    let title = title.trim();
    if title.is_empty() {
        return Err("会话标题不能为空".into());
    }
    if title.chars().count() > 80 {
        return Err("会话标题过长（>80 字）".into());
    }
    let conn = open(path)?;
    let changed = conn
        .execute(
            "UPDATE session SET title = ?1 WHERE id = ?2",
            params![title, session_id],
        )
        .map_err(|err| format!("重命名会话失败：{err}"))?;
    if changed == 0 {
        return Err("会话不存在".into());
    }
    Ok(())
}

pub fn archive(path: &Path, session_id: &str) -> Result<(), String> {
    let conn = open(path)?;
    let changed = conn
        .execute(
            "UPDATE session SET archived_at = ?1 WHERE id = ?2 AND archived_at IS NULL",
            params![unix_now(), session_id],
        )
        .map_err(|err| format!("归档会话失败：{err}"))?;
    if changed == 0 {
        return Err("会话不存在或已归档".into());
    }
    Ok(())
}

pub fn delete(path: &Path, session_id: &str) -> Result<(), String> {
    let mut conn = open(path)?;
    let tx = conn
        .transaction()
        .map_err(|err| format!("删除会话失败：{err}"))?;
    tx.execute(
        "DELETE FROM session_summary WHERE session_id = ?1",
        params![session_id],
    )
    .map_err(|err| format!("删除会话摘要失败：{err}"))?;
    let changed = tx
        .execute("DELETE FROM session WHERE id = ?1", params![session_id])
        .map_err(|err| format!("删除会话失败：{err}"))?;
    if changed == 0 {
        return Err("会话不存在".into());
    }
    tx.commit().map_err(|err| format!("删除会话失败：{err}"))
}

fn open(path: &Path) -> Result<Connection, String> {
    let conn = Connection::open(path)
        .map_err(|err| format!("打开会话库失败：{}（{err}）", path.display()))?;
    conn.busy_timeout(Duration::from_millis(5000))
        .map_err(|err| format!("会话库 busy_timeout 失败：{err}"))?;
    conn.execute_batch("PRAGMA foreign_keys = ON")
        .map_err(|err| format!("会话库外键开关失败：{err}"))?;
    Ok(conn)
}

fn unix_now() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs_f64())
        .unwrap_or(0.0)
}

fn session_from_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<SessionView> {
    Ok(SessionView {
        id: row.get(0)?,
        title: row.get(1)?,
        started_at: row.get(2)?,
        last_active_at: row.get(3)?,
        archived_at: row.get(4)?,
    })
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
            "echoes-session-test-{}-{stamp}.db",
            std::process::id()
        ))
    }

    fn seed(path: &Path) {
        let conn = Connection::open(path).expect("open");
        conn.execute_batch(
            "CREATE TABLE persona (id TEXT PRIMARY KEY);
             INSERT INTO persona VALUES ('default');
             CREATE TABLE session (
                id TEXT PRIMARY KEY,
                profile_id TEXT NOT NULL DEFAULT 'default',
                persona_id TEXT NOT NULL,
                voice_id TEXT,
                started_at REAL NOT NULL,
                last_active_at REAL NOT NULL,
                title TEXT,
                archived_at REAL,
                FOREIGN KEY (persona_id) REFERENCES persona(id)
             );
             CREATE TABLE session_summary (
                session_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                up_to_turn INTEGER NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE
             );
             CREATE TABLE turn (
                turn_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                user_text TEXT NOT NULL,
                assistant_text TEXT,
                tokens TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                fail_reason TEXT,
                started_at REAL NOT NULL,
                ended_at REAL,
                superseded_by TEXT,
                FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE
             );
             INSERT INTO session VALUES
               ('old', 'default', 'default', NULL, 1, 1, '旧会话', NULL);
             INSERT INTO session_summary VALUES ('old', '摘要', 1, 1);",
        )
        .expect("schema");
    }

    #[test]
    fn create_list_rename_archive_delete() {
        let path = temp_db();
        seed(&path);
        let created = create(&path, Some("新会话".into())).expect("create");
        assert_eq!(list(&path, false).expect("list").len(), 2);
        rename(&path, &created.id, "改名后").expect("rename");
        archive(&path, &created.id).expect("archive");
        let active = list(&path, false).expect("list");
        assert_eq!(active.len(), 1);
        assert_eq!(active[0].id, "old");
        assert_eq!(list(&path, true).expect("all").len(), 2);

        delete(&path, &created.id).expect("delete");
        assert_eq!(list(&path, true).expect("all").len(), 1);
        std::fs::remove_file(path).ok();
    }
}
