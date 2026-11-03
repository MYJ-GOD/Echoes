//! 迁移失败的恢复面：读 `migration_failed.json` + 备份列表，并支持还原。
//!
//! 恢复动作只由用户显式触发；启动阶段 Python 迁移 runner 不会自动还原。

use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BackupView {
    pub name: String,
    pub path: String,
    pub modified_at: u64,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RecoveryStatus {
    pub failed: bool,
    pub message: Option<String>,
    pub db_path: String,
    pub backups: Vec<BackupView>,
}

pub fn status() -> RecoveryStatus {
    status_at(&root_dir())
}

pub fn restore(backup_path: &str) -> Result<(), String> {
    restore_at(&root_dir(), Path::new(backup_path))
}

fn root_dir() -> PathBuf {
    let db = crate::profile::db_path();
    db.parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .unwrap_or_else(|| db.parent().unwrap_or(Path::new(".")).to_path_buf())
}

fn status_at(root: &Path) -> RecoveryStatus {
    let db_path = root.join("db").join("echoes.db");
    let marker = root.join("migration_failed.json");
    let message = fs::read_to_string(&marker)
        .ok()
        .and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok())
        .and_then(|value| {
            value
                .get("error")
                .and_then(|error| error.as_str())
                .map(str::to_owned)
        });
    let failed = marker.is_file();

    let mut backups = Vec::new();
    if let Ok(entries) = fs::read_dir(root.join("backup")) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|ext| ext.to_str()) != Some("db") {
                continue;
            }
            let modified_at = entry
                .metadata()
                .and_then(|meta| meta.modified())
                .ok()
                .and_then(|time| time.duration_since(std::time::UNIX_EPOCH).ok())
                .map(|duration| duration.as_secs())
                .unwrap_or(0);
            backups.push(BackupView {
                name: path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .unwrap_or("backup.db")
                    .to_owned(),
                path: path.to_string_lossy().into_owned(),
                modified_at,
            });
        }
    }
    backups.sort_by(|left, right| right.modified_at.cmp(&left.modified_at));

    RecoveryStatus {
        failed,
        message,
        db_path: db_path.to_string_lossy().into_owned(),
        backups,
    }
}

fn restore_at(root: &Path, backup_path: &Path) -> Result<(), String> {
    let backup_dir = root.join("backup");
    let canonical_backup_dir = backup_dir
        .canonicalize()
        .map_err(|err| format!("备份目录不可用：{}（{err}）", backup_dir.display()))?;
    let canonical_backup = backup_path
        .canonicalize()
        .map_err(|err| format!("备份文件不可用：{}（{err}）", backup_path.display()))?;
    if !canonical_backup.starts_with(&canonical_backup_dir) {
        return Err("拒绝还原：备份路径不在 backup 目录内".into());
    }
    if canonical_backup.extension().and_then(|ext| ext.to_str()) != Some("db") {
        return Err("拒绝还原：只接受 .db 备份".into());
    }

    let db_path = root.join("db").join("echoes.db");
    if let Some(parent) = db_path.parent() {
        fs::create_dir_all(parent)
            .map_err(|err| format!("创建数据库目录失败：{}（{err}）", parent.display()))?;
    }
    fs::copy(&canonical_backup, &db_path)
        .map_err(|err| format!("还原数据库失败：{}（{err}）", db_path.display()))?;
    for suffix in ["-wal", "-shm"] {
        let sidecar = PathBuf::from(format!("{}{suffix}", db_path.display()));
        let _ = fs::remove_file(sidecar);
    }
    let _ = fs::remove_file(root.join("migration_failed.json"));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_root() -> PathBuf {
        let stamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        std::env::temp_dir().join(format!(
            "echoes-recovery-test-{}-{stamp}",
            std::process::id()
        ))
    }

    #[test]
    fn status_reports_marker_and_backups() {
        let root = temp_root();
        fs::create_dir_all(root.join("backup")).expect("backup dir");
        fs::write(
            root.join("migration_failed.json"),
            r#"{"error":"MIGRATION_FAILED: boom"}"#,
        )
        .expect("marker");
        fs::write(root.join("backup").join("v3.db"), b"db").expect("backup");
        let status = status_at(&root);
        assert!(status.failed);
        assert_eq!(status.message.as_deref(), Some("MIGRATION_FAILED: boom"));
        assert_eq!(status.backups.len(), 1);
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn restore_copies_backup_and_removes_marker() {
        let root = temp_root();
        fs::create_dir_all(root.join("db")).expect("db dir");
        fs::create_dir_all(root.join("backup")).expect("backup dir");
        fs::write(root.join("db").join("echoes.db"), b"broken").expect("db");
        fs::write(root.join("backup").join("v3.db"), b"good").expect("backup");
        fs::write(root.join("migration_failed.json"), b"{}").expect("marker");

        restore_at(&root, &root.join("backup").join("v3.db")).expect("restore");
        assert_eq!(
            fs::read(root.join("db").join("echoes.db")).expect("db"),
            b"good"
        );
        assert!(!root.join("migration_failed.json").exists());
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn restore_rejects_path_outside_backup_dir() {
        let root = temp_root();
        fs::create_dir_all(root.join("backup")).expect("backup dir");
        fs::write(root.join("outside.db"), b"x").expect("outside");
        assert!(restore_at(&root, &root.join("outside.db")).is_err());
        let _ = fs::remove_dir_all(root);
    }
}
