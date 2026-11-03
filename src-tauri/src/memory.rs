//! R3a 记忆管理读/删接口（3.7）：事实列表 + 来源回溯 + 删除。
//!
//! **只做读与软删**：编辑/合并/手动添加都要重新生成 bge 向量，那套模型在 sidecar
//! 里，归 R3b 的「记忆写接口」；壳侧硬写一条没有向量的记忆，检索永远看不到，
//! 只会制造「存了但不生效」的假象。
//!
//! **删除为什么不动 `memory_vec`**：vec0 是 sqlite-vec 虚表，壳的只读连接没有
//! 加载扩展（`voices.rs`/`history.rs` 同款口径）。软删后检索的 JOIN 已过滤
//! `deleted = 1`，事实立刻不可召回；向量由 sidecar 启动清洗统一清（见
//! `MemoryRepo.purge_deleted_vectors`），避免在壳里再造一个扩展加载面。

use std::collections::{HashMap, HashSet};
use std::path::Path;
use std::time::Duration;

use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MemoryView {
    pub id: String,
    pub fact: String,
    pub category: String,
    pub created_at: f64,
    pub last_seen_at: f64,
    pub source_session_id: Option<String>,
    pub source_session_title: Option<String>,
    pub source_turn_seq: Option<i64>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MemoryUsage {
    pub turn_id: String,
    pub session_id: String,
    pub session_title: Option<String>,
    pub seq: i64,
    pub user_text: String,
    pub used_at: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MemoryGraphNode {
    pub id: String,
    pub fact: String,
    pub category: String,
    pub last_seen_at: f64,
    pub degree: u32,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MemoryGraphEdge {
    pub source: String,
    pub target: String,
    /// `co-used`：同一轮回复同时引用过两条记忆；`same-session`：同一次会话提取。
    pub kind: String,
    pub weight: f64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MemoryGraph {
    pub nodes: Vec<MemoryGraphNode>,
    pub edges: Vec<MemoryGraphEdge>,
}

/// 当前有效记忆（未删、未被取代），按最近提到排序。
pub fn list(
    path: &Path,
    profile_id: &str,
    limit: u32,
) -> Result<Vec<MemoryView>, String> {
    if limit == 0 {
        return Ok(Vec::new());
    }
    let conn = open(path)?;
    let mut stmt = conn
        .prepare(
            "SELECT m.id, m.fact, m.category, m.created_at, m.last_seen_at,
                    m.source_session_id, s.title, t.seq
             FROM memory_fact m
             LEFT JOIN session s ON s.id = m.source_session_id
             LEFT JOIN turn t ON t.session_id = m.source_session_id
                              AND t.seq = m.source_turn
             WHERE m.profile_id = ?1 AND m.deleted = 0 AND m.superseded_by IS NULL
             ORDER BY m.last_seen_at DESC LIMIT ?2",
        )
        .map_err(|err| format!("读取记忆失败：{err}"))?;
    let rows = stmt
        .query_map(params![profile_id, i64::from(limit.min(1000))], |row| {
            Ok(MemoryView {
                id: row.get(0)?,
                fact: row.get(1)?,
                category: row.get(2)?,
                created_at: row.get(3)?,
                last_seen_at: row.get(4)?,
                source_session_id: row.get(5)?,
                source_session_title: row.get(6)?,
                source_turn_seq: row.get(7)?,
            })
        })
        .map_err(|err| format!("读取记忆失败：{err}"))?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|err| format!("读取记忆失败：{err}"))
}

/// 反查「这条记忆被哪些回复用过」（`turn_memory_ref`，R3a 3.8）。
pub fn usage(path: &Path, fact_id: &str, limit: u32) -> Result<Vec<MemoryUsage>, String> {
    if fact_id.trim().is_empty() || limit == 0 {
        return Ok(Vec::new());
    }
    let conn = open(path)?;
    let mut stmt = conn
        .prepare(
            "SELECT r.turn_id, t.session_id, s.title, t.seq, t.user_text, t.started_at
             FROM turn_memory_ref r
             JOIN turn t ON t.turn_id = r.turn_id
             LEFT JOIN session s ON s.id = t.session_id
             WHERE r.fact_id = ?1
             ORDER BY t.started_at DESC LIMIT ?2",
        )
        .map_err(|err| format!("读取记忆来源失败：{err}"))?;
    let rows = stmt
        .query_map(params![fact_id, i64::from(limit.min(200))], |row| {
            Ok(MemoryUsage {
                turn_id: row.get(0)?,
                session_id: row.get(1)?,
                session_title: row.get(2)?,
                seq: row.get(3)?,
                user_text: row.get(4)?,
                used_at: row.get(5)?,
            })
        })
        .map_err(|err| format!("读取记忆来源失败：{err}"))?;
    rows.collect::<Result<Vec<_>, _>>()
        .map_err(|err| format!("读取记忆来源失败：{err}"))
}

/// 关系图谱：节点是当前有效记忆，边有两种来源。
///
/// - `co-used`：同一轮回复同时注入过两条记忆（`turn_memory_ref` 自连接），
///   是真实使用产生的语义关联；
/// - `same-session`：同一次会话里提取的事实，按 `created_at` 相邻连成链，
///   避免把一次长会话连成完全图。
pub fn graph(path: &Path, profile_id: &str, limit: u32) -> Result<MemoryGraph, String> {
    if limit == 0 {
        return Ok(MemoryGraph {
            nodes: Vec::new(),
            edges: Vec::new(),
        });
    }
    let conn = open(path)?;
    let cap = i64::from(limit.min(500));

    let mut nodes = {
        let mut stmt = conn
            .prepare(
                "SELECT id, fact, category, last_seen_at
                 FROM memory_fact
                 WHERE profile_id = ?1 AND deleted = 0 AND superseded_by IS NULL
                 ORDER BY last_seen_at DESC LIMIT ?2",
            )
            .map_err(|err| format!("读取记忆图谱失败：{err}"))?;
        stmt.query_map(params![profile_id, cap], |row| {
            Ok(MemoryGraphNode {
                id: row.get(0)?,
                fact: row.get(1)?,
                category: row.get(2)?,
                last_seen_at: row.get(3)?,
                degree: 0,
            })
        })
        .map_err(|err| format!("读取记忆图谱失败：{err}"))?
        .collect::<Result<Vec<_>, _>>()
        .map_err(|err| format!("读取记忆图谱失败：{err}"))?
    };

    if nodes.len() < 2 {
        return Ok(MemoryGraph {
            nodes,
            edges: Vec::new(),
        });
    }

    let ids: HashSet<String> = nodes.iter().map(|node| node.id.clone()).collect();
    let mut edges: Vec<MemoryGraphEdge> = Vec::new();

    {
        let mut stmt = conn
            .prepare(
                "SELECT a.fact_id, b.fact_id, COUNT(*) AS shared
                 FROM turn_memory_ref a
                 JOIN turn_memory_ref b
                   ON b.turn_id = a.turn_id AND a.fact_id < b.fact_id
                 JOIN memory_fact fa ON fa.id = a.fact_id
                 JOIN memory_fact fb ON fb.id = b.fact_id
                 WHERE fa.profile_id = ?1 AND fa.deleted = 0
                   AND fa.superseded_by IS NULL
                   AND fb.profile_id = ?1 AND fb.deleted = 0
                   AND fb.superseded_by IS NULL
                 GROUP BY a.fact_id, b.fact_id
                 ORDER BY shared DESC LIMIT 4000",
            )
            .map_err(|err| format!("读取记忆图谱失败：{err}"))?;
        let rows = stmt
            .query_map(params![profile_id], |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, i64>(2)?,
                ))
            })
            .map_err(|err| format!("读取记忆图谱失败：{err}"))?;
        for row in rows {
            let (source, target, shared) =
                row.map_err(|err| format!("读取记忆图谱失败：{err}"))?;
            if ids.contains(&source) && ids.contains(&target) {
                edges.push(MemoryGraphEdge {
                    source,
                    target,
                    kind: "co-used".into(),
                    weight: shared as f64,
                });
            }
        }
    }

    let mut sessions: HashMap<String, Vec<String>> = HashMap::new();
    {
        let mut stmt = conn
            .prepare(
                "SELECT id, source_session_id
                 FROM memory_fact
                 WHERE profile_id = ?1 AND deleted = 0 AND superseded_by IS NULL
                   AND source_session_id IS NOT NULL
                 ORDER BY source_session_id, created_at",
            )
            .map_err(|err| format!("读取记忆图谱失败：{err}"))?;
        let rows = stmt
            .query_map(params![profile_id], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
            })
            .map_err(|err| format!("读取记忆图谱失败：{err}"))?;
        for row in rows {
            let (fact_id, session_id) = row.map_err(|err| format!("读取记忆图谱失败：{err}"))?;
            if ids.contains(&fact_id) {
                sessions.entry(session_id).or_default().push(fact_id);
            }
        }
    }

    let mut seen: HashSet<(String, String)> = edges
        .iter()
        .map(|edge| canonical_pair(&edge.source, &edge.target))
        .collect();
    for group in sessions.values() {
        for pair in group.windows(2) {
            let key = canonical_pair(&pair[0], &pair[1]);
            if seen.insert(key) {
                edges.push(MemoryGraphEdge {
                    source: pair[0].clone(),
                    target: pair[1].clone(),
                    kind: "same-session".into(),
                    weight: 0.5,
                });
            }
        }
    }

    let mut degrees: HashMap<&str, u32> = HashMap::new();
    for edge in &edges {
        *degrees.entry(edge.source.as_str()).or_insert(0) += 1;
        *degrees.entry(edge.target.as_str()).or_insert(0) += 1;
    }
    for node in &mut nodes {
        node.degree = degrees.get(node.id.as_str()).copied().unwrap_or(0);
    }

    Ok(MemoryGraph { nodes, edges })
}

fn canonical_pair(left: &str, right: &str) -> (String, String) {
    if left <= right {
        (left.to_string(), right.to_string())
    } else {
        (right.to_string(), left.to_string())
    }
}

/// 软删一条记忆（检索面立即不可见；向量由 sidecar 启动清洗）。
pub fn delete(path: &Path, fact_id: &str) -> Result<(), String> {
    if fact_id.trim().is_empty() {
        return Err("fact_id 不能为空".into());
    }
    let conn = open(path)?;
    let changed = conn
        .execute(
            "UPDATE memory_fact SET deleted = 1 WHERE id = ?1 AND deleted = 0",
            params![fact_id],
        )
        .map_err(|err| format!("删除记忆失败：{err}"))?;
    if changed == 0 {
        return Err("记忆不存在或已删除".into());
    }
    Ok(())
}

fn open(path: &Path) -> Result<Connection, String> {
    let conn = Connection::open(path)
        .map_err(|err| format!("打开记忆库失败（{}）：{err}", path.display()))?;
    conn.busy_timeout(Duration::from_millis(5000))
        .map_err(|err| format!("记忆库 busy_timeout 失败（{}）：{err}", path.display()))?;
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
            "echoes-memory-test-{}-{stamp}.db",
            std::process::id()
        ))
    }

    fn seed(path: &Path) {
        let conn = Connection::open(path).expect("open");
        conn.execute_batch(
            "CREATE TABLE memory_fact (
                id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, fact TEXT NOT NULL,
                category TEXT NOT NULL, source_session_id TEXT, source_turn INTEGER,
                created_at REAL NOT NULL, last_seen_at REAL NOT NULL,
                superseded_by TEXT, deleted INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE session (
                id TEXT PRIMARY KEY, title TEXT
            );
            CREATE TABLE turn (
                turn_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, seq INTEGER NOT NULL,
                user_text TEXT NOT NULL, started_at REAL NOT NULL
            );
            CREATE TABLE turn_memory_ref (
                turn_id TEXT NOT NULL, fact_id TEXT NOT NULL, weight REAL,
                PRIMARY KEY (turn_id, fact_id)
            );
            INSERT INTO session VALUES ('s1', '读书');
            INSERT INTO turn VALUES ('t1','s1',4,'上次说的书叫什么',100);
            INSERT INTO memory_fact VALUES
              ('f1','default','用户喜欢猫','preference','s1',4,10,30,NULL,0),
              ('f2','default','用户住在杭州','identity',NULL,NULL,11,20,NULL,0),
              ('f3','default','旧事实','other',NULL,NULL,12,12,'f1',0),
              ('f4','default','已删除','other',NULL,NULL,13,13,NULL,1);
            INSERT INTO turn_memory_ref VALUES ('t1','f1',NULL);",
        )
        .expect("schema");
    }

    #[test]
    fn list_returns_active_memories_with_source() {
        let path = temp_db();
        seed(&path);
        let memories = list(&path, "default", 50).expect("list");
        assert_eq!(
            memories.iter().map(|item| item.id.as_str()).collect::<Vec<_>>(),
            vec!["f1", "f2"]
        );
        assert_eq!(memories[0].source_session_title.as_deref(), Some("读书"));
        assert_eq!(memories[0].source_turn_seq, Some(4));
        assert!(memories[1].source_session_id.is_none());
        std::fs::remove_file(path).ok();
    }

    #[test]
    fn usage_returns_turns_that_injected_the_fact() {
        let path = temp_db();
        seed(&path);
        let hits = usage(&path, "f1", 50).expect("usage");
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].turn_id, "t1");
        assert_eq!(hits[0].seq, 4);
        assert_eq!(hits[0].session_title.as_deref(), Some("读书"));
        assert!(usage(&path, "f2", 50).expect("usage").is_empty());
        std::fs::remove_file(path).ok();
    }

    #[test]
    fn delete_is_soft_and_idempotent_guard() {
        let path = temp_db();
        seed(&path);
        delete(&path, "f1").expect("delete");
        assert!(delete(&path, "f1").is_err(), "重复删除应报错");
        let memories = list(&path, "default", 50).expect("list");
        assert_eq!(memories.len(), 1);
        assert_eq!(memories[0].id, "f2");
        std::fs::remove_file(path).ok();
    }

    #[test]
    fn graph_links_memories_co_used_in_same_turn() {
        let path = temp_db();
        seed(&path);
        let conn = Connection::open(&path).expect("open");
        conn.execute_batch(
            "INSERT INTO turn VALUES ('t2','s1',5,'你还记得吗',101);
             INSERT INTO turn_memory_ref VALUES ('t2','f1',NULL);
             INSERT INTO turn_memory_ref VALUES ('t2','f2',NULL);",
        )
        .expect("seed graph");
        drop(conn);

        let graph = graph(&path, "default", 50).expect("graph");
        assert_eq!(graph.nodes.len(), 2, "只包含有效记忆");
        assert_eq!(graph.edges.len(), 1);
        let edge = &graph.edges[0];
        assert_eq!(edge.kind, "co-used");
        assert_eq!(edge.weight, 1.0);
        assert_eq!(edge.source, "f1");
        assert_eq!(edge.target, "f2");
        let f1 = graph
            .nodes
            .iter()
            .find(|node| node.id == "f1")
            .expect("f1");
        assert_eq!(f1.degree, 1);
        std::fs::remove_file(path).ok();
    }

    #[test]
    fn graph_chains_memories_from_same_session() {
        let path = temp_db();
        seed(&path);
        let conn = Connection::open(&path).expect("open");
        conn.execute_batch(
            "INSERT INTO memory_fact VALUES
               ('f5','default','用户喜欢爵士','preference','s1',5,14,14,NULL,0),
               ('f6','default','用户住在城西','identity','s1',6,15,15,NULL,0);",
        )
        .expect("seed session");
        drop(conn);

        let graph = graph(&path, "default", 50).expect("graph");
        assert_eq!(graph.nodes.len(), 4);
        assert_eq!(graph.edges.len(), 2, "同会话按时间相邻连成链");
        assert!(graph.edges.iter().all(|edge| edge.kind == "same-session"));
        std::fs::remove_file(path).ok();
    }
}
