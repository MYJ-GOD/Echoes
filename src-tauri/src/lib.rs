mod sidecar;

use std::path::PathBuf;

use sidecar::Sidecar;
use tauri::{Emitter, Manager};

/// 壳独占持有的 sidecar 句柄（命令经 State 取用）。
struct SidecarState(Sidecar);

/// 前端文本输入 → sidecar `user_text`（12.3 首周「文本→LLM→文本」壳侧入口）。
#[tauri::command]
fn send_user_text(state: tauri::State<SidecarState>, text: String) -> Result<(), String> {
    state.0.send_user_text("default", &text)
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

      // 阶段 0 dev 形态：仓库根 sidecar/（.venv Python + mock 引擎）。
      let sidecar_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .map(|p| p.join("sidecar"))
        .expect("CARGO_MANIFEST_DIR 必有父目录");
      let emit_handle = app.handle().clone();
      let spawn_result =
        Sidecar::spawn(&sidecar_dir, Box::new(move |event| {
          let _ = emit_handle.emit(sidecar::SHELL_EVENT, event);
        }));
      match spawn_result {
        Ok(sidecar) => {
          app.manage(SidecarState(sidecar));
          log::info!("sidecar 已启动（dev 形态）");
        }
        Err(err) => {
          log::error!("{err}");
          let _ = app
            .handle()
            .emit(sidecar::SHELL_EVENT, sidecar::ShellEvent::Protocol {
              code: "PROTOCOL_MISMATCH".into(),
              message: err,
              fatal: true,
            });
        }
      }
      Ok(())
    })
    .invoke_handler(tauri::generate_handler![send_user_text])
    .run(tauri::generate_context!())
    .expect("error while building tauri application");
}
