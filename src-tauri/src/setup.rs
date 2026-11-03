//! 首启向导（ADR-011/016）：把 sidecar 的 `--setup` 一次性进程包成命令。
//!
//! **为什么不把下载写进壳**：运行时档案的断点续传、模型清单的多源/sha256、以及
//! 「装到哪个目录」都在 Python 侧；壳只负责起进程、转 JSON 行、把进度抛给前端。
//! 这样向导与 `runtime_manager.py` / `model_manager.py` 用的是同一套实现。
//!
//! **协议**：`--setup <action>` 的 stdout 每行一个 JSON（见 `setup_cli.py`）。
//! 壳逐行 `app.emit("setup://event", line)`，命令返回最后一行（result/error）。

use std::io::{BufRead, BufReader, Read};
use std::path::Path;
use std::process::{Command, Stdio};

use serde_json::Value;

use crate::sidecar;

/// 运行一次 setup 动作；`on_event` 收到每一行（含进度），返回值是最后一行。
pub fn run(
    sidecar_dir: &Path,
    args: &[String],
    mut on_event: impl FnMut(&Value),
) -> Result<Value, String> {
    let launch = sidecar::resolve_launch(sidecar_dir)?;
    let mut command = Command::new(&launch.program);
    command
        .args(&launch.args)
        .arg("--setup")
        .args(args)
        .current_dir(&launch.cwd)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = command
        .spawn()
        .map_err(|err| format!("向导进程启动失败（{}）：{err}", launch.program.display()))?;

    // stderr 单独抽干：下载库/异常栈会往这里写，不读就会把管道写满卡死。
    let stderr = child.stderr.take();
    let drain = std::thread::spawn(move || {
        let mut buffer = String::new();
        if let Some(mut handle) = stderr {
            let _ = handle.read_to_string(&mut buffer);
        }
        buffer
    });

    let mut last = Value::Null;
    if let Some(stdout) = child.stdout.take() {
        for line in BufReader::new(stdout).lines().map_while(Result::ok) {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            match serde_json::from_str::<Value>(trimmed) {
                Ok(value) => {
                    on_event(&value);
                    last = value;
                }
                Err(_) => {
                    // 非 JSON 行（第三方库的 print）只进日志，不打断向导
                    log::warn!("setup 非 JSON 输出: {trimmed}");
                }
            }
        }
    }

    let status = child.wait().map_err(|err| format!("等待向导进程失败：{err}"))?;
    let err_text = drain.join().unwrap_or_default();
    if !status.success() && last.get("type").and_then(Value::as_str) != Some("error") {
        return Err(format!(
            "向导进程退出码 {status}：{}",
            err_text.chars().take(400).collect::<String>()
        ));
    }
    if last.is_null() {
        return Err(format!(
            "向导进程没有输出：{}",
            err_text.chars().take(400).collect::<String>()
        ));
    }
    Ok(last)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn sidecar_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("manifest 必有父目录")
            .join("sidecar")
    }

    #[test]
    fn detect_runs_against_the_real_sidecar() {
        let mut lines = 0;
        let result = run(
            &sidecar_dir(),
            &["detect".to_string()],
            |value| {
                lines += 1;
                assert_eq!(value.get("type").and_then(Value::as_str), Some("detect"));
            },
        )
        .expect("detect 应成功");

        assert_eq!(lines, 1);
        let report = result.get("report").expect("report");
        // 前端契约是 camelCase（sidecar/setup.as_dict 负责转）
        assert!(report.get("recommendedProfile").is_some());
        assert!(report.get("missingModels").is_some());
    }

    #[test]
    fn unknown_action_returns_an_error_line() {
        // argparse 的 SystemExit(2)：壳要么拿到 error 行，要么拿到明确的 Err
        match run(
            &sidecar_dir(),
            &["definitely-not-an-action".to_string()],
            |_| {},
        ) {
            Ok(value) => assert_eq!(value.get("type"), Some(&Value::from("error"))),
            Err(message) => assert!(message.contains("退出码"), "{message}"),
        }
    }
}
