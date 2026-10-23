//! Tauri 壳组合根：sidecar 生命周期、文本面、PTT 语音面（12.3 / §12 步骤 4）。
//!
//! 语音链路（3.4）：前端 getUserMedia 48k PCM16 → `ptt_*` 命令 → capture 重采样
//! 16k → WS 0x01 帧 → sidecar ASR；下行 0x02 帧 → rodio 播放（ADR-010）。
//! PTT 按下先 flush 本地播放（壳侧打断首跳；三跳完整协议在阶段 0 第四周）。

mod audio;
mod capture;
mod sidecar;
mod ws_audio;

use std::path::PathBuf;
use std::sync::Mutex;

use audio::AudioPlayer;
use capture::CaptureResampler;
use sidecar::Sidecar;
use tauri::{Emitter, Manager};
use ws_audio::{pcm16_le, WsAudioClient};

/// 壳独占持有的 sidecar 句柄（命令经 State 取用）。
struct SidecarState(Sidecar);

/// 音频面状态：播放线程 + PTT 重采样器 + WS 上行端（端口解析后装配）。
struct AudioState {
    player: AudioPlayer,
    capture: Mutex<CaptureResampler>,
    ws: Mutex<Option<WsAudioClient>>,
}

/// 前端文本输入 → sidecar `user_text`（12.3 首周「文本→LLM→文本」壳侧入口）。
#[tauri::command]
fn send_user_text(state: tauri::State<SidecarState>, text: String) -> Result<(), String> {
    state.0.send_user_text("default", &text)
}

/// PTT 按下：中断本地在途播放（打断首跳）+ 重置重采样器。
#[tauri::command]
fn ptt_start(state: tauri::State<AudioState>) -> Result<(), String> {
    state.player.flush();
    state
        .capture
        .lock()
        .map_err(|e| format!("采集锁损坏: {e}"))?
        .reset();
    Ok(())
}

/// PTT 采集分片（48k mono PCM16）→ FIR 重采样 16k → WS 0x01 帧。
#[tauri::command]
fn ptt_push(state: tauri::State<AudioState>, samples: Vec<i16>) -> Result<(), String> {
    let pcm16k = state
        .capture
        .lock()
        .map_err(|e| format!("采集锁损坏: {e}"))?
        .push(&samples);
    if pcm16k.is_empty() {
        return Ok(());
    }
    let ws = state.ws.lock().map_err(|e| format!("音频通道锁损坏: {e}"))?;
    let Some(client) = ws.as_ref() else {
        return Err("音频通道未就绪（WS 尚未连接）".into());
    };
    client.send_input(pcm16_le(&pcm16k), false);
    Ok(())
}

/// PTT 松开：空 is_final 帧收束整段（sidecar `next_utterance` 语义）。
#[tauri::command]
fn ptt_stop(state: tauri::State<AudioState>) -> Result<(), String> {
    state
        .capture
        .lock()
        .map_err(|e| format!("采集锁损坏: {e}"))?
        .reset();
    if let Some(client) = state
        .ws
        .lock()
        .map_err(|e| format!("音频通道锁损坏: {e}"))?
        .as_ref()
    {
        client.send_input(Vec::new(), true);
    }
    Ok(())
}

/// 克隆录音开始：复位重采样器（克隆与播放无关，不动播放缓冲）。
#[tauri::command]
fn clone_record_start(state: tauri::State<AudioState>) -> Result<(), String> {
    state
        .capture
        .lock()
        .map_err(|e| format!("采集锁损坏: {e}"))?
        .reset();
    Ok(())
}

/// 克隆样本分片（48k mono PCM16）→ FIR 重采样 16k → WS 0x01 帧，flags 带 bit2。
#[tauri::command]
fn clone_push(state: tauri::State<AudioState>, samples: Vec<i16>) -> Result<(), String> {
    let pcm16k = state
        .capture
        .lock()
        .map_err(|e| format!("采集锁损坏: {e}"))?
        .push(&samples);
    if pcm16k.is_empty() {
        return Ok(());
    }
    let ws = state.ws.lock().map_err(|e| format!("音频通道锁损坏: {e}"))?;
    let Some(client) = ws.as_ref() else {
        return Err("音频通道未就绪（WS 尚未连接）".into());
    };
    client.send_clone_sample(pcm16_le(&pcm16k), false);
    Ok(())
}

/// 克隆录音结束：空 final 样本帧收束 → `clone_start`（3.4/4.6）。
///
/// 样本内容只走 WS 帧；`sample_keys` 是壳侧对账用的标签（4.6 契约字段）。
#[tauri::command]
fn clone_record_stop(
    state: tauri::State<AudioState>,
    sidecar: tauri::State<SidecarState>,
) -> Result<(), String> {
    state
        .capture
        .lock()
        .map_err(|e| format!("采集锁损坏: {e}"))?
        .reset();
    if let Some(client) = state
        .ws
        .lock()
        .map_err(|e| format!("音频通道锁损坏: {e}"))?
        .as_ref()
    {
        client.send_clone_sample(Vec::new(), true);
    }
    sidecar
        .0
        .send_clone_start("default", &["clone-sample".to_string()])
}

/// 取消克隆（3.4 clone_cancel）：sidecar 在阶段边界生效并把音色落 failed。
#[tauri::command]
fn clone_cancel(sidecar: tauri::State<SidecarState>) -> Result<(), String> {
    sidecar.0.send_clone_cancel("default")
}

/// 引擎装配口径：默认真路（whisper + CosyVoice2 + Ollama）；`ECHOES_SIDECAR_MOCK=1`
/// 强制 mock 全链（无模型验收/开发）。`--ws auto`：壳侧 WS 音频面（3.4）。
fn sidecar_args() -> Vec<String> {
    let args: &[&str] = if std::env::var_os("ECHOES_SIDECAR_MOCK").is_some() {
        &[
            "--llm", "mock", "--asr", "mock", "--tts", "mock", "--ws", "auto",
        ]
    } else {
        &[
            "--llm",
            "ollama",
            "--no-think",
            "--asr",
            "whisper",
            "--tts",
            "cosyvoice2",
            "--ws",
            "auto",
        ]
    };
    args.iter().map(|s| s.to_string()).collect()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }

      // 音频面先装配：端口回调里要 clone AudioPlayer 给 WS 下行帧。
      app.manage(AudioState {
        player: AudioPlayer::start(),
        capture: Mutex::new(CaptureResampler::new()),
        ws: Mutex::new(None),
      });

      // 阶段 0 dev 形态：仓库根 sidecar/（.venv Python）。
      let sidecar_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(|p| p.join("sidecar"))
        .expect("CARGO_MANIFEST_DIR 必有父目录");
      let args = sidecar_args();
      log::info!("sidecar 参数: {args:?}");

      let emit_handle = app.handle().clone();
      let port_handle = app.handle().clone();
      let spawn_result = Sidecar::spawn(
        &sidecar_dir,
        &args,
        &[],
        Box::new(move |event| {
          let _ = emit_handle.emit(sidecar::SHELL_EVENT, event);
        }),
        Box::new(move |port| {
          let player = port_handle.state::<AudioState>().player.clone();
          let client = WsAudioClient::connect(port, move |pcm| player.push_pcm16(&pcm));
          match port_handle.state::<AudioState>().ws.lock() {
            Ok(mut slot) => *slot = Some(client),
            Err(err) => log::error!("音频通道状态锁损坏: {err}"),
          }
        }),
      );
      match spawn_result {
        Ok(sidecar) => {
          app.manage(SidecarState(sidecar));
          log::info!("sidecar 已启动（dev 形态）");
        }
        Err(err) => {
          log::error!("{err}");
          // 壳自身错误（非冻结码表）——前端按 message 渲染；code 仅作定位用
          let _ = app
            .handle()
            .emit(sidecar::SHELL_EVENT, sidecar::ShellEvent::Protocol {
              code: "SIDECAR_LAUNCH_FAILED".into(),
              message: err,
              fatal: true,
            });
        }
      }
      Ok(())
    })
    .invoke_handler(tauri::generate_handler![
      send_user_text,
      ptt_start,
      ptt_push,
      ptt_stop,
      clone_record_start,
      clone_push,
      clone_record_stop,
      clone_cancel
    ])
    .run(tauri::generate_context!())
    .expect("error while building tauri application");
}
