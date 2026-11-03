//! Tauri 壳组合根：sidecar 生命周期、文本面、PTT 语音面（12.3 / §12 步骤 4）。
//!
//! 语音链路（3.4）：前端 getUserMedia 48k PCM16 → `ptt_*` 命令 → capture 重采样
//! 16k → WS 0x01 帧 → sidecar ASR；下行 0x02 帧 → rodio 播放（ADR-010）。
//! 三跳打断（3.4）：PTT 按下 → 关下行闸门 + flush 播放缓冲（≤100ms）→
//! `control(interrupt)`；sidecar 回 `turn_complete(CANCELLED)` 后开门。

mod audio;
mod capture;
mod data;
mod history;
mod memory;
mod profile;
mod recovery;
mod secrets;
mod session;
mod setup;
mod sidecar;
mod voices;
mod ws_audio;

use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};

use audio::AudioPlayer;
use capture::CaptureResampler;
use sidecar::Sidecar;
use tauri::{Emitter, Manager};
use ws_audio::{pcm16_le, OutputGate, WsAudioClient};

/// 壳独占持有的 sidecar 句柄（命令经 State 取用）。
/// 首启向导命令的共享状态：sidecar 目录在启动时解析一次。
struct SetupState {
  sidecar_dir: PathBuf,
}

struct SidecarState {
    sidecar: Arc<Mutex<Sidecar>>,
    active_session: Arc<Mutex<String>>,
    stop: Arc<AtomicBool>,
}

struct TrayReady(bool);

impl SidecarState {
    fn with_sidecar<T>(
        &self,
        action: impl FnOnce(&Sidecar) -> Result<T, String>,
    ) -> Result<T, String> {
        let guard = self
            .sidecar
            .lock()
            .map_err(|err| format!("sidecar 状态锁损坏: {err}"))?;
        action(&guard)
    }

    fn active_session_id(&self) -> Result<String, String> {
        let current = self
            .active_session
            .lock()
            .map_err(|err| format!("会话状态锁损坏: {err}"))?
            .clone();
        if !current.is_empty() {
            return Ok(current);
        }
        let latest = session::latest_id(&profile::db_path())?;
        *self
            .active_session
            .lock()
            .map_err(|err| format!("会话状态锁损坏: {err}"))? = latest.clone();
        Ok(latest)
    }

    fn set_active_session(&self, session_id: &str) -> Result<(), String> {
        if session_id.trim().is_empty() {
            return Err("session_id 不能为空".into());
        }
        *self
            .active_session
            .lock()
            .map_err(|err| format!("会话状态锁损坏: {err}"))? = session_id.to_string();
        Ok(())
    }
}

impl Drop for SidecarState {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Relaxed);
    }
}

/// 音频面状态：播放线程 + PTT 重采样器 + WS 上行端（端口解析后装配）+ 下行闸门。
struct AudioState {
    player: AudioPlayer,
    capture: Mutex<CaptureResampler>,
    ws: Mutex<Option<WsAudioClient>>,
    gate: OutputGate,
}

/// 前端文本输入 → sidecar `user_text`（12.3 首周「文本→LLM→文本」壳侧入口）。
#[tauri::command]
fn send_user_text(state: tauri::State<SidecarState>, text: String) -> Result<(), String> {
    let session_id = state.active_session_id()?;
    state.with_sidecar(|sidecar| sidecar.send_user_text(&session_id, &text))
}

/// R4 4.4：重说上一轮（sidecar 复用原文；新 turn 成功后旧 turn 被取代）。
#[tauri::command]
fn retry_turn(state: tauri::State<SidecarState>) -> Result<(), String> {
    let session_id = state.active_session_id()?;
    state.with_sidecar(|sidecar| sidecar.send_retry(&session_id, None))
}

/// R4 4.5：编辑上一条并重跑（append-only，旧 turn 被取代；空文本拒绝）。
#[tauri::command]
fn edit_last_turn(state: tauri::State<SidecarState>, text: String) -> Result<(), String> {
    let text = text.trim();
    if text.is_empty() {
        return Err("编辑内容不能为空".into());
    }
    let session_id = state.active_session_id()?;
    state.with_sidecar(|sidecar| sidecar.send_retry(&session_id, Some(text)))
}

/// 打断在途 turn（3.4 三跳第二跳）：关闸门 → 清播放缓冲 → `control(interrupt)`。
///
/// 顺序不可颠倒：先关闸门，打断前已在 WS 管道里的旧 turn 帧才不会漏进来；
/// 先清缓冲，用户感知的静音就 ≤100ms（不等 sidecar 确认）。
#[tauri::command]
fn interrupt_turn(
    audio: tauri::State<AudioState>,
    sidecar: tauri::State<SidecarState>,
) -> Result<(), String> {
    audio.gate.shut();
    audio.player.flush();
    let session_id = sidecar.active_session_id()?;
    sidecar.with_sidecar(|sidecar| sidecar.send_control(&session_id, "interrupt"))
}

/// 停止播放（3.5 动作矩阵）：只丢弃当前 turn，不进入采集 → `control(cancel_turn)`。
#[tauri::command]
fn cancel_turn(
    audio: tauri::State<AudioState>,
    sidecar: tauri::State<SidecarState>,
) -> Result<(), String> {
    audio.gate.shut();
    audio.player.flush();
    let session_id = sidecar.active_session_id()?;
    sidecar.with_sidecar(|sidecar| sidecar.send_control(&session_id, "cancel_turn"))
}

/// PTT 按下：中断本地在途播放（打断首跳）+ 重置重采样器。
#[tauri::command]
fn ptt_start(
    state: tauri::State<AudioState>,
    sidecar: tauri::State<SidecarState>,
) -> Result<(), String> {
    let session_id = sidecar.active_session_id()?;
    let _ = sidecar.with_sidecar(|sidecar| sidecar.send_control(&session_id, "open_session"));
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

/// R1e 1e.3：系统输出设备枚举（cpal；rodio 只开 playback，没有枚举 API）。
#[tauri::command]
fn audio_output_devices() -> Result<Vec<audio::OutputDevice>, String> {
    audio::list_output_devices()
}

/// R1e 1e.4：切换输出设备（`None` = 系统默认）。换设备会重建输出流。
#[tauri::command]
fn audio_set_output_device(state: tauri::State<AudioState>, device: Option<String>) -> Result<(), String> {
    state.player.set_device(device);
    Ok(())
}

/// R1e 1e.6：播放音量（0..=1，Rust 侧再钳制一次）。
#[tauri::command]
fn audio_set_volume(state: tauri::State<AudioState>, volume: f32) -> Result<(), String> {
    state.player.set_volume(volume);
    Ok(())
}

/// R1e 1e.6：试听音（走当前选定设备与音量）。
#[tauri::command]
fn audio_test_tone(state: tauri::State<AudioState>) -> Result<(), String> {
    state.player.play_test_tone();
    Ok(())
}

/// 人设卡（3.4 拉取语义）：setting 覆盖优先，缺省回落 persona 表。
#[tauri::command]
fn get_persona() -> Result<profile::PersonaView, String> {
    profile::read_persona(&profile::db_path())
}

#[tauri::command]
fn save_persona(persona: profile::PersonaView) -> Result<(), String> {
    profile::write_persona(&profile::db_path(), &persona)
}

#[tauri::command]
fn get_settings() -> Result<profile::SettingsView, String> {
    let mut settings = profile::read_settings(&profile::db_path())?;
    settings.has_key = secrets::has_key();
    settings.has_tts_key = secrets::has_key_for(&secrets::engine_account("tts", "openai"));
    settings.has_asr_key = secrets::has_key_for(&secrets::engine_account("asr", "openai"));
    Ok(settings)
}

#[tauri::command]
fn save_settings(settings: profile::SettingsView) -> Result<(), String> {
    profile::write_settings(&profile::db_path(), &settings)
}

/// 保存云端 LLM 的 API key（ADR-016：Windows 凭据管理器，明文不入库、不回传）。
#[tauri::command]
fn save_llm_key(key: String) -> Result<(), String> {
    secrets::save(&key)
}

#[tauri::command]
fn clear_llm_key() -> Result<(), String> {
    secrets::clear()
}

/// R2a 2.13：分链 key（chain = asr / tts）。provider 目前只支持 openai 兼容端点。
fn engine_account_checked(chain: &str, provider: &str) -> Result<String, String> {
    if !matches!(chain, "asr" | "tts") {
        return Err(format!("未知引擎链 {chain:?}（仅 asr / tts）"));
    }
    if provider != "openai" {
        return Err(format!(
            "provider {provider:?} 不支持 API key（目前仅 openai 兼容端点）"
        ));
    }
    Ok(secrets::engine_account(chain, provider))
}

#[tauri::command]
fn save_engine_key(chain: String, provider: String, key: String) -> Result<(), String> {
    let account = engine_account_checked(&chain, &provider)?;
    secrets::save_for(&account, &key)
}

#[tauri::command]
fn clear_engine_key(chain: String, provider: String) -> Result<(), String> {
    let account = engine_account_checked(&chain, &provider)?;
    secrets::clear_for(&account)
}

#[tauri::command]
fn has_engine_key(chain: String, provider: String) -> Result<bool, String> {
    let account = engine_account_checked(&chain, &provider)?;
    Ok(secrets::has_key_for(&account))
}

/// 首启向导完成（ADR-016）：与「保存设置」分开，避免保存时又弹回向导。
#[tauri::command]
fn complete_setup() -> Result<(), String> {
    profile::write_first_run_done(&profile::db_path(), true)
}

#[tauri::command]
fn reset_setup() -> Result<(), String> {
    profile::write_first_run_done(&profile::db_path(), false)
}

/// 迁移失败恢复面：读 marker + 备份列表。
#[tauri::command]
fn recovery_status() -> recovery::RecoveryStatus {
    recovery::status()
}

/// 用户显式还原备份；还原后需要重启应用。
#[tauri::command]
fn recovery_restore(backup_path: String) -> Result<(), String> {
    recovery::restore(&backup_path)
}

/// R5 导出：默认落 `<data>/exports/`，前端展示路径与规模。
#[tauri::command]
async fn data_export(
    state: tauri::State<'_, SetupState>,
    path: Option<String>,
) -> Result<data::ExportResult, String> {
    let dir = state.sidecar_dir.clone();
    let target = path.map(PathBuf::from);
    tauri::async_runtime::spawn_blocking(move || data::export(&dir, target.as_deref()))
        .await
        .map_err(|err| format!("导出线程失败：{err}"))?
}

/// R5 导入：合并语义（同 id 保留现有），需要重启生效。
#[tauri::command]
async fn data_import(
    state: tauri::State<'_, SetupState>,
    path: String,
) -> Result<data::ImportResult, String> {
    let dir = state.sidecar_dir.clone();
    let source = PathBuf::from(path);
    tauri::async_runtime::spawn_blocking(move || data::import(&dir, &source))
        .await
        .map_err(|err| format!("导入线程失败：{err}"))?
}

/// R5 手动备份（VACUUM INTO）；返回备份文件绝对路径。
#[tauri::command]
fn data_backup() -> Result<String, String> {
    data::backup(&profile::root_dir())
}

/// R5 彻底删除：停 sidecar → 删个人数据目录 → 清云端 key；需要重启应用。
#[tauri::command]
fn data_wipe(
    state: tauri::State<'_, SidecarState>,
    confirm: String,
) -> Result<data::WipeResult, String> {
    if confirm.trim() != data::WIPE_CONFIRM {
        return Err(format!("请原样输入「{}」确认", data::WIPE_CONFIRM));
    }
    // 先挡住 watchdog 重启，再结束进程：Windows 上被打开的 .db 删不掉
    state.stop.store(true, Ordering::Relaxed);
    if let Ok(mut process) = state.sidecar.lock() {
        let _ = process.kill_and_wait();
    }
    let removed = data::wipe(&profile::root_dir())?;
    let cleared_keys = data::clear_cloud_keys();
    Ok(data::WipeResult {
        removed,
        cleared_keys,
    })
}

/// R5 诊断包：脱敏环境快照（不含原文/记忆内容/key）。
#[tauri::command]
fn data_diagnostics() -> Result<serde_json::Value, String> {
    data::write_diagnostics(&profile::root_dir())
}

/// R5 模型管理：清单里每个模型的安装状态与磁盘占用。
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct LocalModelView {
    id: String,
    display_name: String,
    kind: String,
    installed: bool,
    detail: String,
    path: String,
    expected_mb: f64,
    bytes: u64,
}

#[tauri::command]
async fn models_info(
    state: tauri::State<'_, SetupState>,
) -> Result<Vec<LocalModelView>, String> {
    let dir = state.sidecar_dir.clone();
    let value = tauri::async_runtime::spawn_blocking(move || {
        setup::run(&dir, &["models-info".to_string()], |_| {})
    })
    .await
    .map_err(|err| format!("模型线程失败：{err}"))??;
    if value.get("type").and_then(serde_json::Value::as_str) == Some("error") {
        return Err(value
            .get("message")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("读取模型状态失败")
            .to_string());
    }
    let models = value
        .get("models")
        .cloned()
        .unwrap_or_else(|| serde_json::Value::Array(Vec::new()));
    serde_json::from_value(models).map_err(|err| format!("模型状态不可解析：{err}"))
}

/// R5 模型管理：删除本地权重（Ollama 模型由 Ollama 自己管）。
#[tauri::command]
async fn models_remove(
    state: tauri::State<'_, SetupState>,
    ids: Vec<String>,
) -> Result<serde_json::Value, String> {
    if ids.is_empty() {
        return Err("没有指定要删除的模型".into());
    }
    let dir = state.sidecar_dir.clone();
    let value = tauri::async_runtime::spawn_blocking(move || {
        setup::run(
            &dir,
            &["models-remove".to_string(), "--ids".to_string(), ids.join(",")],
            |_| {},
        )
    })
    .await
    .map_err(|err| format!("模型线程失败：{err}"))??;
    if value.get("type").and_then(serde_json::Value::as_str) == Some("error") {
        return Err(value
            .get("message")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("删除模型失败")
            .to_string());
    }
    Ok(value)
}

/// R1c 会话列表。
#[tauri::command]
fn session_list(include_archived: Option<bool>) -> Result<Vec<session::SessionView>, String> {
    session::list(
        &profile::db_path(),
        include_archived.unwrap_or(false),
    )
}

/// R1c 新建会话。
#[tauri::command]
fn session_create(title: Option<String>) -> Result<session::SessionView, String> {
    session::create(&profile::db_path(), title)
}

#[tauri::command]
fn session_rename(session_id: String, title: String) -> Result<(), String> {
    session::rename(&profile::db_path(), &session_id, &title)
}

#[tauri::command]
fn session_archive(session_id: String) -> Result<(), String> {
    session::archive(&profile::db_path(), &session_id)
}

#[tauri::command]
fn session_delete(session_id: String) -> Result<(), String> {
    session::delete(&profile::db_path(), &session_id)
}

/// R1c：切换活跃会话（sidecar 收到 control(open_session) 后重建 Session）。
#[tauri::command]
fn session_open(
    sidecar: tauri::State<SidecarState>,
    session_id: String,
) -> Result<(), String> {
    sidecar.set_active_session(&session_id)?;
    sidecar.with_sidecar(|sidecar| sidecar.send_control(&session_id, "open_session"))
}

/// 首启向导：硬件/依赖探测（返回 report JSON）。
#[tauri::command]
async fn setup_detect(state: tauri::State<'_, SetupState>) -> Result<serde_json::Value, String> {
    let dir = state.sidecar_dir.clone();
    tauri::async_runtime::spawn_blocking(move || {
        setup::run(&dir, &["detect".to_string()], |_| {})
    })
    .await
    .map_err(|err| format!("向导线程失败：{err}"))?
}

/// R2a 2.6：拉取 LLM 模型目录（Ollama `/api/tags` 或云端 `GET /v1/models`）。
#[tauri::command]
async fn setup_models(
    state: tauri::State<'_, SetupState>,
    provider: String,
    base_url: Option<String>,
) -> Result<serde_json::Value, String> {
    if !matches!(provider.as_str(), "ollama" | "openai") {
        return Err(format!("provider {provider:?} 没有模型目录"));
    }
    let mut args = vec![
        "list-models".to_string(),
        "--provider".to_string(),
        provider,
    ];
    if let Some(url) = base_url {
        let url = url.trim();
        if !url.is_empty() {
            args.push("--base-url".to_string());
            args.push(url.to_string());
        }
    }
    let dir = state.sidecar_dir.clone();
    tauri::async_runtime::spawn_blocking(move || setup::run(&dir, &args, |_| {}))
        .await
        .map_err(|err| format!("向导线程失败：{err}"))?
}

/// R3b：记忆写接口——一次性 sidecar 进程里重新嵌入后落库。
async fn run_memory_write(
    state: tauri::State<'_, SetupState>,
    args: Vec<String>,
) -> Result<serde_json::Value, String> {
    let mut full = vec!["memory-write".to_string()];
    full.extend(args);
    let dir = state.sidecar_dir.clone();
    let value = tauri::async_runtime::spawn_blocking(move || setup::run(&dir, &full, |_| {}))
        .await
        .map_err(|err| format!("工作线程失败：{err}"))??;
    if value.get("type").and_then(|item| item.as_str()) == Some("error") {
        return Err(value
            .get("message")
            .and_then(|item| item.as_str())
            .unwrap_or("记忆写入失败")
            .to_string());
    }
    Ok(value)
}

#[tauri::command]
async fn memory_add(
    state: tauri::State<'_, SetupState>,
    fact: String,
    category: String,
) -> Result<serde_json::Value, String> {
    run_memory_write(
        state,
        vec![
            "--op".into(),
            "add".into(),
            "--fact".into(),
            fact,
            "--category".into(),
            category,
        ],
    )
    .await
}

#[tauri::command]
async fn memory_update(
    state: tauri::State<'_, SetupState>,
    fact_id: String,
    fact: String,
    category: String,
) -> Result<serde_json::Value, String> {
    run_memory_write(
        state,
        vec![
            "--op".into(),
            "update".into(),
            "--fact-id".into(),
            fact_id,
            "--fact".into(),
            fact,
            "--category".into(),
            category,
        ],
    )
    .await
}

/// R5 记忆批量导入：文本落临时文件，交给一次性 `--setup memory-write --op bulk`。
#[tauri::command]
async fn memory_import(
    state: tauri::State<'_, SetupState>,
    text: String,
) -> Result<serde_json::Value, String> {
    if text.trim().is_empty() {
        return Err("批量导入内容为空".into());
    }
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|value| value.as_nanos())
        .unwrap_or(0);
    let file = profile::root_dir()
        .join("tmp")
        .join(format!("memory-bulk-{}-{stamp}.txt", std::process::id()));
    if let Some(parent) = file.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|err| format!("创建临时目录失败：{}（{err}）", parent.display()))?;
    }
    std::fs::write(&file, text)
        .map_err(|err| format!("写临时文件失败：{}（{err}）", file.display()))?;
    let result = run_memory_write(
        state,
        vec![
            "--op".into(),
            "bulk".into(),
            "--file".into(),
            file.to_string_lossy().into_owned(),
        ],
    )
    .await;
    // 记忆内容属于个人数据：临时文件用完立刻删（失败也不影响导入结果）
    let _ = std::fs::remove_file(&file);
    result
}

#[tauri::command]
async fn memory_merge(    state: tauri::State<'_, SetupState>,
    ids: Vec<String>,
    fact: String,
    category: String,
) -> Result<serde_json::Value, String> {
    if ids.len() < 2 {
        return Err("合并至少需要两条记忆".into());
    }
    run_memory_write(
        state,
        vec![
            "--op".into(),
            "merge".into(),
            "--ids".into(),
            ids.join(","),
            "--fact".into(),
            fact,
            "--category".into(),
            category,
        ],
    )
    .await
}

/// 首启向导：下载运行时或模型；进度经 `setup://event` 推给前端。
#[tauri::command]
async fn setup_install(
    app: tauri::AppHandle,
    state: tauri::State<'_, SetupState>,
    action: String,
    profile: Option<String>,
    ids: Vec<String>,
) -> Result<serde_json::Value, String> {
    let mut args = vec![action.clone()];
    match action.as_str() {
        "install-runtime" => {
            if let Some(profile) = profile {
                args.push("--profile".to_string());
                args.push(profile);
            }
        }
        "install-models" => {
            if !ids.is_empty() {
                args.push("--ids".to_string());
                args.push(ids.join(","));
            }
        }
        other => return Err(format!("未知向导动作 {other}")),
    }

    let dir = state.sidecar_dir.clone();
    let handle = app.clone();
    tauri::async_runtime::spawn_blocking(move || {
        setup::run(&dir, &args, |line| {
            if let Err(err) = handle.emit("setup://event", line.clone()) {
                log::warn!("setup 事件发送失败: {err}");
            }
        })
    })
    .await
    .map_err(|err| format!("向导线程失败：{err}"))?
}

/// 音色槽位（ADR-008）：列表 + 切换；写 session.voice_id，sidecar 下一轮拉取。
#[tauri::command]
fn list_voices() -> Result<Vec<voices::VoiceView>, String> {
    voices::list_voices(&profile::db_path())
}

#[tauri::command]
fn select_voice(voice_id: String) -> Result<(), String> {
    voices::select_voice(&profile::db_path(), &voice_id)
}

/// R5：音色治理——改名 / 删除（被会话绑定则拒绝）。
#[tauri::command]
fn voice_rename(voice_id: String, display_name: String) -> Result<(), String> {
    voices::rename_voice(&profile::db_path(), &voice_id, &display_name)
}

#[tauri::command]
fn voice_delete(voice_id: String) -> Result<(), String> {
    voices::delete_voice(&profile::db_path(), &voice_id)
}

/// R1a 历史读接口：turn 列表（新→旧）。
#[tauri::command]
fn history_list(
    session_id: String,
    limit: Option<u32>,
    offset: Option<u32>,
    include_superseded: Option<bool>,
) -> Result<Vec<history::TurnView>, String> {
    history::list(
        &profile::db_path(),
        &session_id,
        limit.unwrap_or(50),
        offset.unwrap_or(0),
        include_superseded.unwrap_or(false),
    )
}

/// R1a 历史读接口：单条 turn。
#[tauri::command]
fn history_get(turn_id: String) -> Result<Option<history::TurnView>, String> {
    history::get(&profile::db_path(), &turn_id)
}

/// R1a 历史读接口：全文搜索（LIKE 兜底；sidecar 的 FTS 检索仍独立）。
#[tauri::command]
fn history_search(
    query: String,
    session_id: Option<String>,
    limit: Option<u32>,
    offset: Option<u32>,
    include_superseded: Option<bool>,
) -> Result<Vec<history::TurnView>, String> {
    history::search(
        &profile::db_path(),
        &query,
        session_id.as_deref(),
        limit.unwrap_or(20),
        offset.unwrap_or(0),
        include_superseded.unwrap_or(false),
    )
}

/// R3a 3.7：记忆列表（只读面；编辑/合并归 sidecar）。
#[tauri::command]
fn memory_list(
    profile_id: Option<String>,
    limit: Option<u32>,
) -> Result<Vec<memory::MemoryView>, String> {
    memory::list(
        &profile::db_path(),
        profile_id.as_deref().unwrap_or("default"),
        limit.unwrap_or(200),
    )
}

/// R3a 3.8：这条记忆被哪些回复用过（来源回溯）。
#[tauri::command]
fn memory_usage(fact_id: String, limit: Option<u32>) -> Result<Vec<memory::MemoryUsage>, String> {
    memory::usage(&profile::db_path(), &fact_id, limit.unwrap_or(50))
}

/// 记忆关系图谱：共被引用 / 同会话的事实连边。
#[tauri::command]
fn memory_graph(
    profile_id: Option<String>,
    limit: Option<u32>,
) -> Result<memory::MemoryGraph, String> {
    memory::graph(
        &profile::db_path(),
        profile_id.as_deref().unwrap_or("default"),
        limit.unwrap_or(300),
    )
}

/// R3a 3.7：软删一条记忆（向量由 sidecar 启动清洗）。
#[tauri::command]
fn memory_delete(fact_id: String) -> Result<(), String> {
    memory::delete(&profile::db_path(), &fact_id)
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
    let session_id = sidecar.active_session_id()?;
    sidecar.with_sidecar(|proc| {
        proc.send_clone_start(&session_id, &["clone-sample".to_string()])
    })
}

/// 取消克隆（3.4 clone_cancel）：sidecar 在阶段边界生效并把音色落 failed。
#[tauri::command]
fn clone_cancel(sidecar: tauri::State<SidecarState>) -> Result<(), String> {
    let session_id = sidecar.active_session_id()?;
    sidecar.with_sidecar(|proc| proc.send_clone_cancel(&session_id))
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

/// 首启向导的 sidecar 目录（dev 用仓库、安装包用 resource）。
fn locate_sidecar_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    if cfg!(debug_assertions) {
        return PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .map(|root| root.join("sidecar"))
            .ok_or_else(|| "CARGO_MANIFEST_DIR 必有父目录".to_string());
    }
    app.path()
        .resource_dir()
        .map(|dir| dir.join("sidecar"))
        .map_err(|err| format!("资源目录解析失败：{err}"))
}

fn show_main(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

/// 托盘「开始/停止说话」：翻转开关并同步菜单文案，再让前端切换采集。
///
/// 不复用 `hotkey://ptt` 的按下/松开：那是"按住"语义，开关模式下两个事件会被
/// 折叠成一次，导致菜单里永远停不下来。
fn toggle_talk_switch(app: &tauri::AppHandle) {
    let state = app.state::<TalkSwitch>();
    let next = !state.active.load(Ordering::Relaxed);
    state.active.store(next, Ordering::Relaxed);
    if let Ok(item) = state.item.lock()
        && let Some(item) = item.as_ref()
    {
        let _ = item.set_text(if next { "停止说话" } else { "开始说话" });
    }
    let _ = app.emit("shell://talk-toggle", ());
}

fn create_hud(app: &tauri::AppHandle) -> Result<(), String> {
    if app.get_webview_window("hud").is_some() {
        return Ok(());
    }
    let mut builder = tauri::WebviewWindowBuilder::new(
        app,
        "hud",
        tauri::WebviewUrl::App("index.html#/hud".into()),
    )
    .title("Echoes HUD")
    .inner_size(380.0, 120.0)
    .resizable(false)
    .decorations(false)
    .shadow(false)
    .transparent(true)
    .always_on_top(true)
    .skip_taskbar(true)
    .focused(false)
    .visible(false);
    // 屏幕顶部居中：不传 position 时窗口出现在系统随手位置，可能压住内容或跑出屏。
    if let Some((x, y)) = hud_origin(app) {
        builder = builder.position(x, y);
    }
    let window = builder
        .build()
        .map_err(|err| format!("创建 HUD 窗口失败：{err}"))?;
    // 1d.6：`focused(false)` 不保证「永不抢焦点」——PTT 期间 HUD 弹出若抢焦点，
    // 用户正在打字的窗口会掉焦点。Windows 上补 WS_EX_NOACTIVATE 才是硬保证。
    #[cfg(windows)]
    if let Err(err) = make_hud_noactivate(&window) {
        log::warn!("HUD 设置 WS_EX_NOACTIVATE 失败（可能抢焦点）: {err}");
    }
    Ok(())
}

/// HUD 逻辑坐标：主屏顶部居中（宽 380，距顶 72）。
fn hud_origin(app: &tauri::AppHandle) -> Option<(f64, f64)> {
    let monitor = app.primary_monitor().ok().flatten()?;
    let scale = monitor.scale_factor();
    let width = monitor.size().width as f64 / scale;
    let position = monitor.position();
    let left = position.x as f64 / scale;
    Some((left + (width - 380.0) / 2.0, position.y as f64 / scale + 72.0))
}

/// 给 HUD 加 `WS_EX_NOACTIVATE`：点击/显示都不激活窗口，也不进 Alt+Tab。
#[cfg(windows)]
fn make_hud_noactivate(window: &tauri::WebviewWindow) -> Result<(), String> {
    use windows::Win32::UI::WindowsAndMessaging::{
        GWL_EXSTYLE, GetWindowLongPtrW, SetWindowLongPtrW, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW,
    };

    let hwnd = window.hwnd().map_err(|err| err.to_string())?;
    unsafe {
        let style = GetWindowLongPtrW(hwnd, GWL_EXSTYLE);
        let next = style | (WS_EX_NOACTIVATE.0 | WS_EX_TOOLWINDOW.0) as isize;
        if next != style {
            SetWindowLongPtrW(hwnd, GWL_EXSTYLE, next);
        }
    }
    Ok(())
}

/// R5 1c.5：独立设置窗口。复用主页面（`#/settings` 走 hash 路由只渲染设置面板），
/// 不做第二套设置界面，避免两处维护。
///
/// 与 HUD 一样在 `setup` 里预创建（隐藏），而不是等用户点「设置」时再建：
/// 运行期（命令回调里）现建 WebView2 窗口实测会拿到一个停在 `about:blank` 的
/// 白窗口——导航请求不提交，等于白屏。启动阶段建窗这条路 HUD 已经跑通，故沿用。
fn create_settings(app: &tauri::AppHandle) -> Result<(), String> {
    if app.get_webview_window("settings").is_some() {
        return Ok(());
    }
    tauri::WebviewWindowBuilder::new(
        app,
        "settings",
        tauri::WebviewUrl::App("index.html#/settings".into()),
    )
    .title("Echoes 设置")
    .inner_size(820.0, 800.0)
    .min_inner_size(700.0, 620.0)
    .resizable(true)
    // 与主窗口一致：自绘标题栏（品牌 + 最小化/关闭），不让系统白条打断视觉。
    .decorations(false)
    .shadow(true)
    .always_on_top(false)
    .center()
    .visible(false)
    .build()
    .map_err(|err| format!("创建设置窗口失败：{err}"))?;
    Ok(())
}

#[tauri::command]
fn open_settings_window(app: tauri::AppHandle) -> Result<(), String> {
    create_settings(&app)?;
    let window = app
        .get_webview_window("settings")
        .ok_or_else(|| "设置窗口不存在".to_string())?;
    let _ = window.unminimize();
    window.show().map_err(|err| err.to_string())?;
    let _ = window.set_focus();
    Ok(())
}

/// R5：HUD 展开 → 主窗口（并收起 HUD）。
#[tauri::command]
fn show_main_window(app: tauri::AppHandle) {
    show_main(&app);
    let _ = hide_hud(app);
}

#[tauri::command]
fn show_hud(app: tauri::AppHandle) -> Result<(), String> {    create_hud(&app)?;
    if let Some(window) = app.get_webview_window("hud") {
        window.show().map_err(|err| err.to_string())?;
        let _ = window.set_always_on_top(true);
    }
    Ok(())
}

#[tauri::command]
fn hide_hud(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("hud") {
        window.hide().map_err(|err| err.to_string())?;
    }
    Ok(())
}

/// 托盘「开始/停止说话」的开关状态（1d.1）。菜单点击无法"按住"，所以用显式开关：
/// 点「开始说话」= 前端 PTT 按下，再点「停止说话」= 松开。快捷键 Alt+Space 仍是按住语义。
struct TalkSwitch {
    active: AtomicBool,
    item: Mutex<Option<tauri::menu::MenuItem<tauri::Wry>>>,
}

/// R1d：托盘菜单（显示 / 开始说话 / 设置 / 退出）。
fn build_tray(app: &mut tauri::App) -> tauri::Result<()> {
    use tauri::menu::{MenuBuilder, MenuItemBuilder};
    use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};

    let show = MenuItemBuilder::with_id("show", "显示主窗口").build(app)?;
    let talk = MenuItemBuilder::with_id("talk", "开始说话").build(app)?;
    let settings = MenuItemBuilder::with_id("settings", "设置").build(app)?;
    let quit = MenuItemBuilder::with_id("quit", "退出 Echoes").build(app)?;
    let menu = MenuBuilder::new(app)
        .items(&[&show, &talk, &settings, &quit])
        .build()?;
    app.manage(TalkSwitch {
        active: AtomicBool::new(false),
        item: Mutex::new(Some(talk.clone())),
    });

    let mut builder = TrayIconBuilder::new()
        .tooltip("Echoes")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => show_main(app),
            "talk" => toggle_talk_switch(app),
            "settings" => {
                show_main(app);
                let _ = app.emit("shell://open-settings", ());
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    Ok(())
}

#[tauri::command]
fn autostart_get(app: tauri::AppHandle) -> Result<bool, String> {
    use tauri_plugin_autostart::ManagerExt;
    app.autolaunch().is_enabled().map_err(|err| err.to_string())
}

#[tauri::command]
fn autostart_set(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    use tauri_plugin_autostart::ManagerExt;
    let manager = app.autolaunch();
    if enabled {
        manager.enable().map_err(|err| err.to_string())
    } else {
        manager.disable().map_err(|err| err.to_string())
    }
}

/// R5：关窗行为（默认最小化到托盘）。
#[tauri::command]
fn close_to_tray_get() -> Result<bool, String> {
    Ok(profile::read_close_to_tray(&profile::db_path()))
}

#[tauri::command]
fn close_to_tray_set(enabled: bool) -> Result<(), String> {
    profile::write_close_to_tray(&profile::db_path(), enabled)
}

/// R5：全局 PTT 快捷键（Tauri accelerator，如 `Alt+Space` / `Ctrl+Shift+E`）。
#[tauri::command]
fn ptt_shortcut_get() -> Result<String, String> {
    Ok(profile::read_ptt_shortcut(&profile::db_path())
        .unwrap_or_else(|| "Alt+Space".to_string()))
}

/// 先注册新键，成功后再落库；失败时恢复旧键，避免用户「改坏了没声音」。
#[tauri::command]
fn ptt_shortcut_set(app: tauri::AppHandle, accelerator: String) -> Result<(), String> {
    let next = accelerator.trim();
    if next.is_empty() {
        return Err("快捷键不能为空".into());
    }
    let mut previous = profile::read_ptt_shortcut(&profile::db_path())
        .unwrap_or_else(|| "Alt+Space".to_string());
    if previous == next {
        // 新键与旧键相同：注册失败时回滚到默认键仍比「没有快捷键」好
        previous = "Alt+Space".to_string();
    }
    if let Err(err) = register_ptt_shortcut(&app, next) {
        // 新键注册失败（被占用/格式错）：把旧键装回去，不能让用户失去说话键
        let _ = register_ptt_shortcut(&app, &previous);
        return Err(err);
    }
    if let Err(err) = profile::write_ptt_shortcut(&profile::db_path(), next) {
        // 落库失败：把旧键装回去，避免本次会话与下次启动不一致
        let _ = register_ptt_shortcut(&app, &previous);
        return Err(err);
    }
    Ok(())
}

#[cfg(desktop)]
fn register_ptt_shortcut(app: &tauri::AppHandle, accelerator: &str) -> Result<(), String> {
    use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

    let shortcut: Shortcut = accelerator
        .parse()
        .map_err(|err| format!("快捷键格式无效（{accelerator}）：{err}"))?;
    let manager = app.global_shortcut();
    manager
        .unregister_all()
        .map_err(|err| format!("清除旧快捷键失败：{err}"))?;
    manager
        .register(shortcut)
        .map_err(|err| format!("注册快捷键失败（可能被其他软件占用）：{err}"))
}

#[cfg(not(desktop))]
fn register_ptt_shortcut(_app: &tauri::AppHandle, _accelerator: &str) -> Result<(), String> {
    Ok(())
}

/// R5：系统通知（后台回复完成时由前端调用）。body 由前端截断，壳不读对话原文。
#[tauri::command]
fn app_notify(app: tauri::AppHandle, title: String, body: String) -> Result<(), String> {
    use tauri_plugin_notification::NotificationExt;
    let manager = app.notification();
    // Windows 不需要运行时授权；macOS/Linux 首次会弹系统授权，失败也不阻断
    let _ = manager.request_permission();
    manager
        .builder()
        .title(title)
        .body(body)
        .show()
        .map_err(|err| format!("发送通知失败：{err}"))
}

fn spawn_sidecar(
    sidecar_dir: &std::path::Path,
    args: &[String],
    emit_handle: tauri::AppHandle,
    gate: OutputGate,
    port_handle: tauri::AppHandle,
    active_session: Arc<Mutex<String>>,
) -> Result<Sidecar, String> {
    let gate_for_events = gate.clone();
    let active_for_events = Arc::clone(&active_session);
    Sidecar::spawn(
        sidecar_dir,
        args,
        &[],
        Box::new(move |event| {
            let turn_ended = match &event {
                sidecar::ShellEvent::Sidecar(sidecar::SidecarEvent::TurnComplete { .. })
                | sidecar::ShellEvent::Sidecar(sidecar::SidecarEvent::Error { .. }) => true,
                sidecar::ShellEvent::Sidecar(sidecar::SidecarEvent::State { state, .. }) => {
                    state == "ready" || state == "generating"
                }
                sidecar::ShellEvent::Protocol { .. } => true,
                _ => false,
            };
            if turn_ended {
                gate_for_events.open();
            }
            if let sidecar::ShellEvent::Sidecar(sidecar::SidecarEvent::State {
                session_id: Some(session_id),
                ..
            }) = &event
            {
                if let Ok(mut slot) = active_for_events.lock() {
                    *slot = session_id.clone();
                }
            }
            let _ = emit_handle.emit(sidecar::SHELL_EVENT, event);
        }),
        Box::new(move |port| {
            let player = port_handle.state::<AudioState>().player.clone();
            let gate = port_handle.state::<AudioState>().gate.clone();
            let client = WsAudioClient::connect(port, gate, move |pcm| player.push_pcm16(&pcm));
            match port_handle.state::<AudioState>().ws.lock() {
                Ok(mut slot) => *slot = Some(client),
                Err(err) => log::error!("音频通道状态锁损坏: {err}"),
            }
        }),
    )
}

/// R1d：sidecar 退出后指数退避重启；最多 5 次，避免崩溃循环烧 CPU。
fn start_sidecar_watchdog(
    sidecar_dir: PathBuf,
    args: Vec<String>,
    emit_handle: tauri::AppHandle,
    gate: OutputGate,
    port_handle: tauri::AppHandle,
    active_session: Arc<Mutex<String>>,
    sidecar: Arc<Mutex<Sidecar>>,
    stop: Arc<AtomicBool>,
) {
    std::thread::spawn(move || {
        let mut restarts = 0u32;
        loop {
            if stop.load(Ordering::Relaxed) {
                return;
            }
            std::thread::sleep(std::time::Duration::from_secs(1));
            if stop.load(Ordering::Relaxed) {
                return;
            }
            let exited = match sidecar.lock() {
                Ok(mut process) => process.try_wait().ok().flatten().is_some(),
                Err(_) => false,
            };
            if !exited {
                continue;
            }
            restarts += 1;
            if restarts > 5 {
                log::error!("sidecar 连续重启超过 5 次，停止 watchdog");
                return;
            }
            let delay = 1u64 << (restarts - 1).min(4);
            log::warn!("sidecar 已退出，{}s 后第 {} 次重启", delay, restarts);
            std::thread::sleep(std::time::Duration::from_secs(delay));
            if stop.load(Ordering::Relaxed) {
                return;
            }
            match spawn_sidecar(
                &sidecar_dir,
                &args,
                emit_handle.clone(),
                gate.clone(),
                port_handle.clone(),
                Arc::clone(&active_session),
            ) {
                Ok(process) => {
                    let session_id = active_session
                        .lock()
                        .map(|value| value.clone())
                        .unwrap_or_default();
                    if !session_id.is_empty() {
                        let _ = process.send_control(&session_id, "open_session");
                    }
                    match sidecar.lock() {
                        Ok(mut slot) => *slot = process,
                        Err(err) => {
                            log::error!("替换 sidecar 失败: {err}");
                            return;
                        }
                    }
                    log::info!("sidecar 已重启");
                }
                Err(err) => log::error!("sidecar 重启失败: {err}"),
            }
        }
    });
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
      if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
      }
    }))
    .plugin(tauri_plugin_autostart::Builder::new().build())
    // R5：后台回复完成的可选系统通知（由前端按设置调用 `app_notify`）
    .plugin(tauri_plugin_notification::init())
    // 1e.5：WebView2 的 mic 权限必须显式放行，否则 getUserMedia 静默失败。
    // 其余权限保持 Default（由 WebView2 默认策略处理），不扩大攻击面。
    .on_permission_request(|_webview, kind| match kind {
      tauri::webview::PermissionKind::Microphone => tauri::webview::PermissionResponse::Allow,
      _ => tauri::webview::PermissionResponse::Default,
    })
    .on_window_event(|window, event| {
      // R5 1c.5：设置窗口预创建后只隐藏，关闭即销毁会导致下次现建（白屏）。
      if window.label() == "settings" {
        if let tauri::WindowEvent::CloseRequested { api, .. } = event {
          api.prevent_close();
          let _ = window.hide();
        }
        return;
      }
      // R1d：HUD 关闭只隐藏；主窗口关闭默认驻留托盘。
      if window.label() == "hud" {
        if let tauri::WindowEvent::CloseRequested { api, .. } = event {
          api.prevent_close();
          let _ = window.hide();
        }
        return;
      }
      if window.label() != "main" {
        return;
      }
      let tray_ready = window
        .app_handle()
        .try_state::<TrayReady>()
        .map(|state| state.0)
        .unwrap_or(false);
      if !tray_ready {
        return;
      }
      if let tauri::WindowEvent::CloseRequested { api, .. } = event {
        // R5：设置里可以改回「关闭即退出」；默认驻留托盘
        if profile::read_close_to_tray(&profile::db_path()) {
          api.prevent_close();
          let _ = window.hide();
        } else {
          window.app_handle().exit(0);
        }
      }
    })
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }

      // R1d + R5：全局快捷键（默认 Alt+Space，可在设置里改）→ 前端 PTT 按下/松开。
      // 注册失败（例如被其他软件占用）不阻断应用启动；设置页会显示错误。
      #[cfg(desktop)]
      {
        use tauri::Emitter;
        use tauri_plugin_global_shortcut::{Builder, ShortcutState};

        let plugin = Builder::new()
          .with_handler(|app, _shortcut, event| {
            let state = if event.state == ShortcutState::Pressed {
              "pressed"
            } else {
              "released"
            };
            let _ = app.emit("hotkey://ptt", state);
          })
          .build();
        if let Err(err) = app.handle().plugin(plugin) {
          log::error!("全局快捷键插件注册失败: {err}");
        } else {
          let accel = profile::read_ptt_shortcut(&profile::db_path())
            .unwrap_or_else(|| "Alt+Space".to_string());
          if let Err(err) = register_ptt_shortcut(app.handle(), &accel) {
            log::error!("全局快捷键注册失败（{accel}）: {err}");
          }
        }
      }

      match build_tray(app) {
        Ok(()) => {
          app.manage(TrayReady(true));
        }
        Err(err) => {
          log::error!("托盘创建失败（关窗将直接退出）: {err}");
          app.manage(TrayReady(false));
        }
      }
      if let Err(err) = create_hud(app.handle()) {
        log::error!("HUD 预创建失败（首次显示时重试）: {err}");
      }
      // 设置窗口同样预创建（隐藏）：运行期现建会拿到停在 about:blank 的白窗口。
      if let Err(err) = create_settings(app.handle()) {
        log::error!("设置窗口预创建失败（打开时重试）: {err}");
      }

      // 音频面先装配：端口回调里要 clone AudioPlayer 给 WS 下行帧。
      let gate = OutputGate::new();
      app.manage(AudioState {
        player: AudioPlayer::start(),
        capture: Mutex::new(CaptureResampler::new()),
        ws: Mutex::new(None),
        gate: gate.clone(),
      });

      // 阶段 0 dev 形态：仓库根 sidecar/（.venv Python）。
      // dev：仓库 sidecar/.venv；安装包：Tauri resource 下的 sidecar/（ADR-011）。
      let sidecar_dir = locate_sidecar_dir(app.handle())?;
      app.manage(SetupState {
        sidecar_dir: sidecar_dir.clone(),
      });
      log::info!("sidecar 目录: {}", sidecar_dir.display());
      let args = sidecar_args();
      log::info!("sidecar 参数: {args:?}");

      let emit_handle = app.handle().clone();
      let port_handle = app.handle().clone();
      let active_session = Arc::new(Mutex::new(
        session::latest_id(&profile::db_path()).unwrap_or_default(),
      ));
      let spawn_result = spawn_sidecar(
        &sidecar_dir,
        &args,
        emit_handle.clone(),
        gate.clone(),
        port_handle.clone(),
        Arc::clone(&active_session),
      );
      match spawn_result {
        Ok(sidecar) => {
          let sidecar = Arc::new(Mutex::new(sidecar));
          let stop = Arc::new(AtomicBool::new(false));
          app.manage(SidecarState {
            sidecar: Arc::clone(&sidecar),
            active_session: Arc::clone(&active_session),
            stop: Arc::clone(&stop),
          });
          start_sidecar_watchdog(
            sidecar_dir.clone(),
            args.clone(),
            emit_handle,
            gate,
            port_handle,
            active_session,
            sidecar,
            stop,
          );
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
      retry_turn,
      edit_last_turn,
      ptt_start,
      ptt_push,
      ptt_stop,
      get_persona,
      save_persona,
      get_settings,
      save_settings,
      save_llm_key,
      clear_llm_key,
      save_engine_key,
      clear_engine_key,
      has_engine_key,
      complete_setup,
      reset_setup,
      recovery_status,
      recovery_restore,
      data_export,
      data_import,
      data_backup,
      data_wipe,
      data_diagnostics,
      models_info,
      models_remove,
      session_list,
      session_create,
      session_rename,
      session_archive,
      session_delete,
      session_open,
      autostart_get,
      autostart_set,
      close_to_tray_get,
      close_to_tray_set,
      app_notify,
      ptt_shortcut_get,
      ptt_shortcut_set,
      show_hud,
      show_main_window,
      open_settings_window,
      hide_hud,
      audio_output_devices,
      audio_set_output_device,
      audio_set_volume,
      audio_test_tone,
      setup_detect,
      setup_models,
      setup_install,
      list_voices,
      select_voice,
      voice_rename,
      voice_delete,
      history_list,
      history_get,
      history_search,
      memory_list,
      memory_usage,
      memory_graph,
      memory_delete,
      memory_add,
      memory_update,
      memory_import,
      memory_merge,
      interrupt_turn,
      cancel_turn,
      clone_record_start,
      clone_push,
      clone_record_stop,
      clone_cancel
    ])
    .run(tauri::generate_context!())
    .expect("error while building tauri application");
}
