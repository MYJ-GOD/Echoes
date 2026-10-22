//! sidecar 子进程生命周期 + stdio JSON 行协议壳侧执行点（3.3/3.4）。
//!
//! 首周范围（12.3）：spawn → `hello` 握手校验（protocol_version 大版本）→
//! `user_text` 下行 / 事件流转发（emit 到前端）；WS 音频通道后续周接入。
//! 事件模型对齐 sidecar 冻结契约 v1.4.1（13.2-1 单一来源 `echoes_sidecar/ipc/schema.py`），
//! serde 默认忽略未知字段 = 3.4 兼容规则的壳侧执行点；未知消息行忽略不崩。

use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::Mutex;

use serde::{Deserialize, Serialize};

/// hello.engines 条目（3.4 v1.4 分级就绪）。
#[derive(Debug, Deserialize, Serialize, Clone)]
pub struct EngineSlot {
    pub name: String,
    pub ready: bool,
}

/// sidecar→壳事件（v1.4.1 子集；t 观测字段透传，前端不感知单位）。
#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(tag = "type")]
#[serde(rename_all = "snake_case")]
pub enum SidecarEvent {
    Hello {
        #[serde(rename = "sidecar_version")]
        sidecar_version: String,
        protocol_version: String,
        engines: Vec<EngineSlot>,
    },
    State {
        session_id: Option<String>,
        state: String,
        t: i64,
    },
    AsrPartial {
        session_id: String,
        text: String,
        t: i64,
    },
    AsrFinal {
        session_id: String,
        text: String,
        #[serde(rename = "is_final")]
        is_final: bool,
        t: i64,
    },
    /// v1.4.1 追加：回复文本=截至当前全量，流式递增，收尾由 turn_complete 界定。
    AssistantText {
        session_id: String,
        text: String,
        t: i64,
    },
    TurnComplete {
        session_id: String,
        #[serde(rename = "turn_seq")]
        turn_seq: i64,
        status: String,
    },
    Error {
        session_id: Option<String>,
        code: String,
        message: String,
        fatal: bool,
        t: i64,
    },
}

/// 前端可见的壳侧事件（含壳自身产生的协议错误）。
#[derive(Debug, Serialize, Clone)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum ShellEvent {
    /// sidecar 消息原样转发（3.4 事件子集）。
    Sidecar(SidecarEvent),
    /// 壳侧协议失败：大版本不匹配（PROTOCOL_MISMATCH）等。
    Protocol {
        code: String,
        message: String,
        fatal: bool,
    },
}

/// stdout 逐行解析：JSON 行 → `SidecarEvent` → sink；解析失败按 3.4 忽略。
/// 泛型流 + 回调分离 = 集成测试可在无 tauri 运行时下全链路驱动（tests 模块）。
fn forward_events<R: BufRead>(mut reader: R, sink: &mut dyn FnMut(ShellEvent)) {
    let mut line = String::new();
    loop {
        line.clear();
        match reader.read_line(&mut line) {
            Ok(0) => break, // EOF：sidecar 退出（3.4 正常收尾）
            Ok(_) => {}
            Err(_) => break,
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        match serde_json::from_str::<SidecarEvent>(trimmed) {
            Ok(event) => {
                if let SidecarEvent::Hello { protocol_version, .. } = &event {
                    if protocol_version.split('.').next() != Some(PROTOCOL_MAJOR) {
                        sink(ShellEvent::Protocol {
                            code: "PROTOCOL_MISMATCH".into(),
                            message: format!(
                                "sidecar protocol `{protocol_version}` != shell `{PROTOCOL_MAJOR}.x`"
                            ),
                            fatal: true,
                        });
                        break;
                    }
                }
                sink(ShellEvent::Sidecar(event));
            }
            Err(err) => {
                // 3.4：未知消息/未知字段必须忽略不崩（解析失败仅记录）。
                log::warn!("sidecar 未知行已忽略: {err}");
            }
        }
    }
}

pub const SHELL_EVENT: &str = "sidecar://event";
const PROTOCOL_MAJOR: &str = "1";

/// sidecar 子进程：stdin 写入端常驻，Drop 时杀进程（3.3 sidecar.rs 职责的最小面）。
pub struct Sidecar {
    child: Child,
    stdin: Mutex<ChildStdin>,
}

impl Sidecar {
    /// dev 形态：`<仓库根>/sidecar/.venv/Scripts/python -m echoes_sidecar.main`
    /// （cwd=sidecar/，与终端运行形态一致；生产 split-binary 由 ADR-011 定稿后替换）。
    pub fn spawn(
        sidecar_dir: &Path,
        sink: Box<dyn FnMut(ShellEvent) + Send>,
    ) -> Result<Self, String> {
        let python = sidecar_dir
            .parent()
            .expect("sidecar 必有父目录")
            .join(".venv")
            .join("Scripts")
            .join("python.exe");
        let mut child = Command::new(&python)
            .args(["-m", "echoes_sidecar.main"])
            .current_dir(sidecar_dir)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("sidecar 启动失败 ({}): {e}", python.display()))?;

        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "sidecar stdout 管道不可用".to_string())?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "sidecar stdin 管道不可用".to_string())?;

        let mut sink = sink;
        std::thread::spawn(move || forward_events(BufReader::new(stdout), &mut sink));

        Ok(Self {
            child,
            stdin: Mutex::new(stdin),
        })
    }

    /// 壳→sidecar：文本输入（3.4 控制消息，与 asr_final 等价触发 turn）。
    pub fn send_user_text(&self, session_id: &str, text: &str) -> Result<(), String> {
        let line = serde_json::json!({
            "type": "user_text",
            "session_id": session_id,
            "text": text,
        });
        let mut stdin = self
            .stdin
            .lock()
            .map_err(|e| format!("stdin 锁损坏: {e}"))?;
        let payload = serde_json::to_string(&line).map_err(|e| e.to_string())?;
        writeln!(stdin, "{payload}").map_err(|e| format!("stdin 写入失败: {e}"))?;
        stdin.flush().map_err(|e| format!("stdin flush 失败: {e}"))
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;
    use std::sync::mpsc;
    use std::time::Duration;

    fn sidecar_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("manifest 必有父目录")
            .join("sidecar")
    }

    /// 12.3 首周验收（自动化形态）：spawn → hello(1.0) → user_text →
    /// assistant_text（递增全量）→ turn_complete(SUCCESS) 全链路。
    #[test]
    fn mock_turn_end_to_end() {
        let (tx, rx) = mpsc::channel::<ShellEvent>();
        let sidecar = Sidecar::spawn(
            &sidecar_dir(),
            Box::new(move |event| {
                let _ = tx.send(event);
            }),
        )
        .expect("sidecar 启动");

        // hello 握手 + 版本校验
        let hello =
            recv_matches(&rx, |e| matches!(e, ShellEvent::Sidecar(..)), Duration::from_secs(20));
        match hello {
            ShellEvent::Sidecar(SidecarEvent::Hello { protocol_version, .. }) => {
                assert_eq!(protocol_version, "1.0");
            }
            other => panic!("首事件应为 hello，实得 {other:?}"),
        }

        sidecar.send_user_text("default", "测试").expect("user_text");

        // 回复文本：至少一片、全量语义（后片包含前片）
        let mut seen_increasing: Option<String> = None;
        loop {
            let ev =
                recv_matches(&rx, |e| matches!(e, ShellEvent::Sidecar(..)), Duration::from_secs(20));
            if let ShellEvent::Sidecar(SidecarEvent::AssistantText { text, .. }) = ev {
                let is_final_piece = text.contains("了");
                match &seen_increasing {
                    Some(prev) => assert!(text.contains(prev.as_str()), "递增语义破坏：{prev:?} ⊄ {text:?}"),
                    None => assert!(text.contains("mock"), "mock 回复文本异常：{text:?}"),
                }
                seen_increasing = Some(text);
                if is_final_piece {
                    break;
                }
            }
        }

        // 收尾：turn_complete(SUCCESS) 旁路 state 等帧直取 correctness
        let done = recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::TurnComplete { .. })),
            Duration::from_secs(20),
        );
        match done {
            ShellEvent::Sidecar(SidecarEvent::TurnComplete { status, .. }) => {
                assert_eq!(status, "SUCCESS");
            }
            other => panic!("尾事件应为 turn_complete，实得 {other:?}"),
        }
    }

    fn recv_matches(rx: &mpsc::Receiver<ShellEvent>, f: fn(&ShellEvent) -> bool, timeout: Duration) -> ShellEvent {
        let deadline = std::time::Instant::now() + timeout;
        loop {
            let remaining = deadline.saturating_duration_since(std::time::Instant::now());
            let ev = rx
                .recv_timeout(remaining)
                .expect("事件流超时：sidecar 未按契约产出");
            if f(&ev) {
                return ev;
            }
        }
    }
}
