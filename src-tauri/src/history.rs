//! R1a 历史读接口：turn 原文列表 / 单条 / 搜索。
//!
//! 这是 UI 只读面；写入仍由 sidecar 的 TurnRepo 唯一负责（sidecar 是状态源）。
//! 查询走只读 SQLite 连接，WAL + busy_timeout 与现有 voices.rs 口径一致。

use std::path::Path;
use std::time::Duration;

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TurnView {
    pub turn_id: String,
    pub session_id: String,
    pub seq: i64,
    pub user_text: String,
    pub assistant_text: Option<String>,
    pub status: String,
    pub fail_reason: Option<String>,
    pub started_at: f64,
    pub ended_at: Option<f64>,
    /// R4 4.4：被哪条新 turn 取代（NULL = 当前可见）；「查看完整历史」据此标记
    pub superseded_by: Option<String>,
    /// R4 4.3：异步质检结论（NULL = 未质检）
    pub grounding_verdict: Option<String>,
    pub grounding_score: Option<f64>,
    /// 未被记忆支撑的说法（JSON 数组文本；前端解析）
    pub grounding_claims: Option<String>,
}

pub fn list(
    path: &Path,
    session_id: &str,
    limit: u32,
    offset: u32,
    include_superseded: bool,
) -> Result<Vec<TurnView>, String> {
    if limit == 0 {
        return Ok(Vec::new());
    }
    let conn = open(path)?;
    let superseded_clause = if include_superseded {
        ""
    } else {
        " AND superseded_by IS NULL"
    };
    let sql = format!(
        "SELECT turn_id, session_id, seq, user_text, assistant_text, status, fail_reason,
                started_at, ended_at, superseded_by, grounding_verdict, grounding_score, grounding_claims
         FROM turn
         WHERE session_id = ?1 AND status IN ('complete', 'cancelled', 'failed'){superseded_clause}
         ORDER BY seq DESC LIMIT ?2 OFFSET ?3"
    );
    let mut stmt = conn
        .prepare(&sql)
        .map_err(|err| format!("读取历史失败：{err}"))?;
    let rows = stmt
        .query_map(
            params![session_id, i64::from(limit.min(500)), i64::from(offset)],
            turn_from_row,
        )
        .map_err(|err| format!("读取历史失败：{err}"))?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|err| format!("读取历史失败：{err}"))
}

pub fn get(path: &Path, turn_id: &str) -> Result<Option<TurnView>, String> {
    let conn = open(path)?;
    conn.query_row(
        "SELECT turn_id, session_id, seq, user_text, assistant_text, status, fail_reason,
                started_at, ended_at, superseded_by, grounding_verdict, grounding_score, grounding_claims
         FROM turn WHERE turn_id = ?1",
        params![turn_id],
        turn_from_row,
    )
    .optional()
    .map_err(|err| format!("读取 turn 失败：{err}"))
}

pub fn search(
    path: &Path,
    query: &str,
    session_id: Option<&str>,
    limit: u32,
    offset: u32,
    include_superseded: bool,
) -> Result<Vec<TurnView>, String> {
    let query = query.trim();
    if query.is_empty() || limit == 0 {
        return Ok(Vec::new());
    }
    let pattern = format!("%{}%", escape_like(query));
    let clause = if include_superseded {
        ""
    } else {
        " AND superseded_by IS NULL"
    };
    let conn = open(path)?;
    let limit = i64::from(limit.min(500));
    let offset = i64::from(offset);

    let mut stmt = if session_id.is_some() {
        conn.prepare(&format!(
            "SELECT turn_id, session_id, seq, user_text, assistant_text, status, fail_reason,
                    started_at, ended_at, superseded_by, grounding_verdict, grounding_score, grounding_claims
             FROM turn
             WHERE session_id = ?1 AND status IN ('complete', 'cancelled', 'failed'){clause}
               AND (user_text LIKE ?2 ESCAPE '\\' OR assistant_text LIKE ?2 ESCAPE '\\'
                    OR tokens LIKE ?2 ESCAPE '\\')
             ORDER BY seq DESC LIMIT ?3 OFFSET ?4"
        ))
        .map_err(|err| format!("搜索历史失败：{err}"))?
    } else {
        conn.prepare(&format!(
            "SELECT turn_id, session_id, seq, user_text, assistant_text, status, fail_reason,
                    started_at, ended_at, superseded_by, grounding_verdict, grounding_score, grounding_claims
             FROM turn
             WHERE status IN ('complete', 'cancelled', 'failed'){clause}
               AND (user_text LIKE ?1 ESCAPE '\\' OR assistant_text LIKE ?1 ESCAPE '\\'
                    OR tokens LIKE ?1 ESCAPE '\\')
             ORDER BY seq DESC LIMIT ?2 OFFSET ?3"
        ))
        .map_err(|err| format!("搜索历史失败：{err}"))?
    };

    let rows = if let Some(session_id) = session_id {
        stmt.query_map(params![session_id, pattern, limit, offset], turn_from_row)
    } else {
        stmt.query_map(params![pattern, limit, offset], turn_from_row)
    }
    .map_err(|err| format!("搜索历史失败：{err}"))?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|err| format!("搜索历史失败：{err}"))
}

fn escape_like(text: &str) -> String {
    text.replace('\\', "\\\\")
        .replace('%', "\\%")
        .replace('_', "\\_")
}

fn turn_from_row(row: &rusqlite::Row<'_>) -> rusqlite::Result<TurnView> {
    Ok(TurnView {
        turn_id: row.get(0)?,
        session_id: row.get(1)?,
        seq: row.get(2)?,
        user_text: row.get(3)?,
        assistant_text: row.get(4)?,
        status: row.get(5)?,
        fail_reason: row.get(6)?,
        started_at: row.get(7)?,
        ended_at: row.get(8)?,
        superseded_by: row.get(9)?,
        grounding_verdict: row.get(10)?,
        grounding_score: row.get(11)?,
        grounding_claims: row.get(12)?,
    })
}

fn open(path: &Path) -> Result<Connection, String> {
    let conn = Connection::open(path)
        .map_err(|err| format!("打开历史库失败：{}（{err}）", path.display()))?;
    conn.busy_timeout(Duration::from_millis(5000))
        .map_err(|err| format!("历史库 busy_timeout 失败：{}（{err}）", path.display()))?;
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
            "echoes-history-test-{}-{stamp}.db",
            std::process::id()
        ))
    }

    fn seed(path: &Path) {
        let conn = Connection::open(path).expect("open");
        conn.execute_batch(
            "CREATE TABLE turn (
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
                grounding_verdict TEXT,
                grounding_score REAL,
                grounding_claims TEXT
            );
            INSERT INTO turn VALUES
              ('t1','s1',1,'我在学吉他','很好','我 在 学 吉他 很好','complete',NULL,1,2,NULL,'faithful',0.9,'[]'),
              ('t2','s1',2,'今天喝咖啡','好的','今天 喝 咖啡 好的','complete',NULL,3,4,NULL,'unfaithful',0.2,'[claim]'),
              ('t3','s1',3,'没写完','', '没 写完','pending',NULL,5,NULL,NULL,NULL,NULL,NULL),
              ('t4','s1',4,'旧话','旧答','旧 话 旧 答','complete',NULL,6,7,'t5',NULL,NULL,NULL);",
        )
        .expect("schema");
    }

    #[test]
    fn list_returns_visible_turns_newest_first() {
        let path = temp_db();
        seed(&path);
        let turns = list(&path, "s1", 50, 0, false).expect("list");
        assert_eq!(
            turns.iter().map(|turn| turn.seq).collect::<Vec<_>>(),
            vec![2, 1]
        );
        assert_eq!(turns[0].assistant_text.as_deref(), Some("好的"));
        // R5：质检结论随历史返回，UI 据此标记「无记忆支撑」
        assert_eq!(turns[0].grounding_verdict.as_deref(), Some("unfaithful"));
        assert_eq!(
            turns[0].grounding_claims.as_deref(),
            Some("[claim]")
        );
        std::fs::remove_file(path).ok();
    }

    #[test]
    fn get_returns_turn_or_none() {
        let path = temp_db();
        seed(&path);
        assert_eq!(get(&path, "t1").expect("get").map(|turn| turn.seq), Some(1));
        assert!(get(&path, "ghost").expect("get").is_none());
        std::fs::remove_file(path).ok();
    }

    #[test]
    fn search_matches_user_and_assistant_text() {
        let path = temp_db();
        seed(&path);
        assert_eq!(
            search(&path, "吉他", Some("s1"), 50, 0, false)
                .expect("search")
                .iter()
                .map(|turn| turn.turn_id.as_str())
                .collect::<Vec<_>>(),
            vec!["t1"]
        );
        assert_eq!(
            search(&path, "咖啡", None, 50, 0, false)
                .expect("search")
                .iter()
                .map(|turn| turn.turn_id.as_str())
                .collect::<Vec<_>>(),
            vec!["t2"]
        );
        assert!(search(&path, "", None, 50, 0, false)
            .expect("empty")
            .is_empty());
        std::fs::remove_file(path).ok();
    }

    #[test]
    fn include_superseded_returns_old_turns_with_link() {
        let path = temp_db();
        seed(&path);
        // 默认排除被取代的 t4
        assert!(
            list(&path, "s1", 50, 0, false)
                .expect("list")
                .iter()
                .all(|turn| turn.turn_id != "t4")
        );
        let all = list(&path, "s1", 50, 0, true).expect("list all");
        let old = all
            .iter()
            .find(|turn| turn.turn_id == "t4")
            .expect("完整历史应包含被取代项");
        assert_eq!(old.superseded_by.as_deref(), Some("t5"));
        std::fs::remove_file(path).ok();
    }
}

