//! sidecar 子进程生命周期 + stdio JSON 行协议壳侧执行点（3.3/3.4）。
//!
//! 范围：spawn → `hello` 握手校验（protocol_version 大版本）→ 事件流转发（emit
//! 到前端）；stderr 转发并解析 WS 音频面端口（`ws://127.0.0.1:PORT`，3.4）。
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
const WS_PORT_MARKER: &str = "ws://127.0.0.1:";

/// stderr 逐行转发 + WS 端口提取。
///
/// Python 在 Windows 控制台的 stderr 编码是 GBK，必须按字节读再 lossy 解码；
/// 若用 `lines()`（要求 UTF-8）会在首条中文日志处中断，端口行永远读不到。
fn forward_stderr<R: BufRead>(mut reader: R, mut on_ws_port: Box<dyn FnMut(u16) + Send>) {
    let mut buf = Vec::new();
    loop {
        buf.clear();
        match reader.read_until(b'\n', &mut buf) {
            Ok(0) => break,
            Ok(_) => {}
            Err(_) => break,
        }
        let line = String::from_utf8_lossy(&buf);
        let line = line.trim_end();
        if line.is_empty() {
            continue;
        }
        log::debug!("sidecar stderr: {line}");
        if let Some(port) = parse_ws_port(line) {
            log::info!("sidecar WS 音频面端口: {port}");
            on_ws_port(port);
        }
    }
}

/// 从 sidecar stderr 行提取 `ws://127.0.0.1:PORT`（无正则依赖）。
fn parse_ws_port(line: &str) -> Option<u16> {
    let start = line.find(WS_PORT_MARKER)? + WS_PORT_MARKER.len();
    let digits: String = line[start..]
        .chars()
        .take_while(|c| c.is_ascii_digit())
        .collect();
    digits.parse().ok()
}

/// sidecar 子进程：stdin 写入端常驻，Drop 时杀进程（3.3 sidecar.rs 职责的最小面）。
pub struct Sidecar {
    child: Child,
    stdin: Mutex<ChildStdin>,
}

impl Sidecar {
    /// dev 形态：`<仓库根>/sidecar/.venv/Scripts/python -m echoes_sidecar.main`
    /// （cwd=sidecar/，与终端运行形态一致；生产 split-binary 由 ADR-011 定稿后替换）。
    ///
    /// `args` 为引擎装配参数（真路/ mock 由组合根决定，12.3）；`on_ws_port` 在
    /// stderr 出现 WS 端口行时回调一次（`--ws auto` 时；便携形态见 lib.rs）。
    /// `envs` 追加子进程环境（测试用来把 `ECHOES_DATA_DIR` 指到临时目录，5.3；
    /// 生产传空切片——数据目录解析归组合根，不在壳侧硬编码）。
    pub fn spawn(
        sidecar_dir: &Path,
        args: &[String],
        envs: &[(&str, String)],
        sink: Box<dyn FnMut(ShellEvent) + Send>,
        on_ws_port: Box<dyn FnMut(u16) + Send>,
    ) -> Result<Self, String> {
        let python = sidecar_dir
            .parent()
            .expect("sidecar 必有父目录")
            .join(".venv")
            .join("Scripts")
            .join("python.exe");
        let mut command = Command::new(&python);
        command
            .args(["-m", "echoes_sidecar.main"])
            .args(args)
            .current_dir(sidecar_dir);
        for (key, value) in envs {
            command.env(key, value);
        }
        let mut child = command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("sidecar 启动失败 ({}): {e}", python.display()))?;

        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "sidecar stdout 管道不可用".to_string())?;
        let stderr = child
            .stderr
            .take()
            .ok_or_else(|| "sidecar stderr 管道不可用".to_string())?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "sidecar stdin 管道不可用".to_string())?;

        let mut sink = sink;
        std::thread::spawn(move || forward_events(BufReader::new(stdout), &mut sink));
        std::thread::spawn(move || forward_stderr(BufReader::new(stderr), on_ws_port));

        Ok(Self {
            child,
            stdin: Mutex::new(stdin),
        })
    }

    /// 壳→sidecar：文本输入（3.4 控制消息，与 asr_final 等价触发 turn）。
    pub fn send_user_text(&self, session_id: &str, text: &str) -> Result<(), String> {
        self.send_line(&serde_json::json!({
            "type": "user_text",
            "session_id": session_id,
            "text": text,
        }))
    }

    /// 壳→sidecar：打断在途 turn（3.4 三跳第二跳）。
    ///
    /// `interrupt` 与 `cancel_turn` 在 sidecar 侧收尾一致（`turn_complete(CANCELLED)`），
    /// 差异在壳：interrupt 之后立即开采集，cancel_turn 不采集（3.4 控制动词定案）。
    pub fn send_control(&self, session_id: &str, action: &str) -> Result<(), String> {
        self.send_line(&serde_json::json!({
            "type": "control",
            "action": action,
            "session_id": session_id,
        }))
    }

    /// 壳→sidecar：样本已通过 WS bit2 帧上送完毕，请开始克隆（3.4/4.6）。
    pub fn send_clone_start(
        &self,
        session_id: &str,
        sample_keys: &[String],
    ) -> Result<(), String> {
        self.send_line(&serde_json::json!({
            "type": "clone_start",
            "session_id": session_id,
            "sample_keys": sample_keys,
        }))
    }

    /// 壳→sidecar：用户取消克隆（3.4 clone_cancel → CloneError(CLONE_CANCELLED)）。
    pub fn send_clone_cancel(&self, session_id: &str) -> Result<(), String> {
        self.send_line(&serde_json::json!({
            "type": "clone_cancel",
            "session_id": session_id,
        }))
    }

    /// 单行 JSON 写 stdin（3.4：stdio 一行一条消息；写失败即壳与 sidecar 失联）。
    fn send_line(&self, value: &serde_json::Value) -> Result<(), String> {
        let mut stdin = self
            .stdin
            .lock()
            .map_err(|e| format!("stdin 锁损坏: {e}"))?;
        let payload = serde_json::to_string(value).map_err(|e| e.to_string())?;
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

    /// 每个端到端用例独立数据目录（5.3）：绝不让测试写进用户 %LOCALAPPDATA%，
    /// 也避免并行用例抢同一个 SQLite 文件。
    fn temp_data_dir(tag: &str) -> String {
        let dir = std::env::temp_dir().join(format!("echoes-test-{}-{tag}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        dir.to_string_lossy().into_owned()
    }

    /// mock 全链参数（无模型验收/开发形态，与 lib.rs 的 ECHOES_SIDECAR_MOCK 口径一致）。
    fn mock_args() -> Vec<String> {
        ["--llm", "mock", "--asr", "mock", "--tts", "mock"]
            .map(String::from)
            .to_vec()
    }

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
            &[],
            &[("ECHOES_DATA_DIR", temp_data_dir("turn"))],
            Box::new(move |event| {
                let _ = tx.send(event);
            }),
            Box::new(|_| {}),
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

    #[test]
    fn parse_ws_port_extracts_listen_line() {
        let line = "[sidecar] WS 音频面监听 ws://127.0.0.1:49692（壳侧连接即收帧）";
        assert_eq!(parse_ws_port(line), Some(49692));
        assert_eq!(parse_ws_port("no ws endpoint"), None);
        assert_eq!(parse_ws_port("ws://127.0.0.1:"), None);
    }

    /// §12 步骤 4 壳侧自动化形态：真进程 + WS 音频面（mock 引擎）→ 上行 PTT 帧 →
    /// asr_final → turn_complete(SUCCESS) → 下行 0x02 帧。播放设备不参与（回调收帧）。
    #[test]
    fn ptt_audio_end_to_end() {
        use crate::ws_audio::{pcm16_le, WsAudioClient};

        let (tx, rx) = mpsc::channel::<ShellEvent>();
        let (port_tx, port_rx) = mpsc::channel::<u16>();
        let args: Vec<String> = [
            "--llm", "mock", "--asr", "mock", "--tts", "mock", "--ws", "auto",
        ]
        .map(String::from)
        .to_vec();
        let _sidecar = Sidecar::spawn(
            &sidecar_dir(),
            &args,
            &[("ECHOES_DATA_DIR", temp_data_dir("ptt"))],
            Box::new(move |event| {
                let _ = tx.send(event);
            }),
            Box::new(move |port| {
                let _ = port_tx.send(port);
            }),
        )
        .expect("sidecar 启动");

        let hello = recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::Hello { .. })),
            Duration::from_secs(20),
        );
        assert!(matches!(
            hello,
            ShellEvent::Sidecar(SidecarEvent::Hello { .. })
        ));
        let port = port_rx
            .recv_timeout(Duration::from_secs(10))
            .expect("WS 端口回调");

        let (pcm_tx, pcm_rx) = mpsc::channel::<Vec<i16>>();
        let client = WsAudioClient::connect(
            port,
            crate::ws_audio::OutputGate::new(),
            move |pcm| {
                let _ = pcm_tx.send(pcm);
            },
        );
        // 400ms 16k mono（内容无关：mock ASR 恒定文本）+ is_final 空帧
        let pcm: Vec<i16> = (0..6400)
            .map(|n| ((n as f64 * 0.4).sin() * 4000.0) as i16)
            .collect();
        for chunk in pcm.chunks(1600) {
            client.send_input(pcm16_le(chunk), false);
        }
        client.send_input(Vec::new(), true);

        let asr = recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::AsrFinal { .. })),
            Duration::from_secs(20),
        );
        match asr {
            ShellEvent::Sidecar(SidecarEvent::AsrFinal { text, .. }) => {
                assert_eq!(text, "（mock）今天有点累，陪我聊聊");
            }
            other => panic!("应为 asr_final，实得 {other:?}"),
        }

        let done = recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::TurnComplete { .. })),
            Duration::from_secs(20),
        );
        match done {
            ShellEvent::Sidecar(SidecarEvent::TurnComplete { status, .. }) => {
                assert_eq!(status, "SUCCESS");
            }
            other => panic!("应为 turn_complete，实得 {other:?}"),
        }

        let downstream = pcm_rx
            .recv_timeout(Duration::from_secs(5))
            .expect("下行 0x02 音频帧");
        assert!(!downstream.is_empty());
    }

    /// 三跳打断（3.4）真进程形态：turn 生成中发 `control(interrupt)` →
    /// `turn_complete(status=CANCELLED)`，且往返远小于 mock 注入的片间时延
    /// （证明是"取消插队"而不是"等引擎吐完"）。
    #[test]
    fn interrupt_cancels_in_flight_turn() {
        const DELAY_MS: u64 = 1500;

        let (tx, rx) = mpsc::channel::<ShellEvent>();
        let sidecar = Sidecar::spawn(
            &sidecar_dir(),
            &mock_args(),
            &[
                ("ECHOES_DATA_DIR", temp_data_dir("interrupt")),
                // 13.3：mock 片间时延 = 打断窗口（不注入就抢不到在途 turn）
                ("ECHOES_MOCK_CHUNK_DELAY_MS", DELAY_MS.to_string()),
            ],
            Box::new(move |event| {
                let _ = tx.send(event);
            }),
            Box::new(|_| {}),
        )
        .expect("sidecar 启动");

        recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::Hello { .. })),
            Duration::from_secs(20),
        );

        sidecar.send_user_text("default", "测试打断").expect("user_text");
        // 首片到达 = turn 已在 generating；此刻 mock 正卡在片间时延里
        recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::AssistantText { .. })),
            Duration::from_secs(20),
        );

        let started = std::time::Instant::now();
        sidecar
            .send_control("default", "interrupt")
            .expect("control(interrupt)");

        let done = recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::TurnComplete { .. })),
            Duration::from_secs(20),
        );
        let elapsed = started.elapsed();

        match done {
            ShellEvent::Sidecar(SidecarEvent::TurnComplete { status, turn_seq, .. }) => {
                assert_eq!(status, "CANCELLED");
                assert_eq!(turn_seq, 1, "被打断的 turn 仍然占一个 turn_seq");
            }
            other => panic!("应为 turn_complete，实得 {other:?}"),
        }
        assert!(
            elapsed < Duration::from_millis(DELAY_MS),
            "打断应插队到片间时延之前（实测 {elapsed:?}）"
        );

        // 收尾后状态机回 ready（壳侧按钮解锁的唯一依据）
        let state = recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::State { state, .. }) if state == "ready"),
            Duration::from_secs(10),
        );
        assert!(matches!(state, ShellEvent::Sidecar(SidecarEvent::State { .. })));
    }

    /// 无在途 turn 时的 `control` 是可容忍的协议噪声：不得产生 turn_complete，
    /// 进程也不得因此失联（打断自释放依赖这一点）。
    #[test]
    fn control_without_in_flight_turn_is_ignored() {
        let (tx, rx) = mpsc::channel::<ShellEvent>();
        let sidecar = Sidecar::spawn(
            &sidecar_dir(),
            &mock_args(),
            &[("ECHOES_DATA_DIR", temp_data_dir("control-idle"))],
            Box::new(move |event| {
                let _ = tx.send(event);
            }),
            Box::new(|_| {}),
        )
        .expect("sidecar 启动");

        recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::Hello { .. })),
            Duration::from_secs(20),
        );
        sidecar
            .send_control("default", "cancel_turn")
            .expect("control(cancel_turn)");

        // 之后仍能正常跑完一轮 = 进程没被 protocol 噪声带歪
        sidecar.send_user_text("default", "还在吗").expect("user_text");
        let done = recv_matches(
            &rx,
            |e| matches!(e, ShellEvent::Sidecar(SidecarEvent::TurnComplete { .. })),
            Duration::from_secs(20),
        );
        match done {
            ShellEvent::Sidecar(SidecarEvent::TurnComplete { status, .. }) => {
                assert_eq!(status, "SUCCESS");
            }
            other => panic!("应为 turn_complete，实得 {other:?}"),
        }
    }
}
