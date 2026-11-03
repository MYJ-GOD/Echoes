/**
 * 壳侧 IPC 门面（3.4 / 13.2-1）：唯一允许 `invoke` / `listen` 的地方。
 *
 * **为什么要这一层**：`invoke("interrupt_turn")` 这种字符串调用在协议改名时是
 * 静默失败——TS 不报错、运行时才 500。把命令名与事件载荷收进类型后，改协议
 * 时编译期就会红。消息类型来自 `ipc_types.ts`（由 sidecar 模型生成，手改无效）。
 *
 * 约定：
 * - 命令名与 `src-tauri/src/lib.rs` 的 `generate_handler!` 清单一一对应；
 * - 事件通道固定 `sidecar://event`，载荷是 `ShellEventPayload`（未知 kind 忽略，
 *   3.4 兼容规则：新事件类型不该让旧前端崩）；
 */
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";

import type {
  CloneStartMsg,
  ControlMsg,
  ErrorCode,
  SidecarMessage,
  UserTextMsg,
} from "./ipc_types";

export type { SidecarMessage } from "./ipc_types";

/** 壳事件载荷（结对 `sidecar.rs::ShellEvent`，serde tag = kind）。 */
export type ShellEventPayload =
  | { kind: "sidecar"; event: SidecarMessage }
  /** 协议级故障（子进程没起来 / JSON 行解析失败 / 版本不匹配），不进状态机 */
  | { kind: "protocol"; code: ErrorCode | string; message: string; fatal: boolean };

/** 下行音频帧的路由点（耳返/播放另经 WS，不经这里）；仅事件面。 */
export const SIDECAR_EVENT = "sidecar://event";

/**
 * base URL 是否指向本机（ADR-016 §3 隐私矩阵：`openai` + 环回地址不出网，允许）。
 *
 * 判据与 sidecar `openai_compat.is_loopback`、壳侧 `profile.rs::is_loopback_base_url`
 * 同口径——三处不一致会出现「能存不能跑」或「能跑不让存」。
 */
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "0.0.0.0"]);

export function isLoopbackBaseUrl(raw: string | null | undefined): boolean {
  const text = (raw ?? "").trim();
  if (!text) return false;
  try {
    // IPv6 字面量的 hostname 带方括号（`[::1]`），去括号后再比
    const host = new URL(text).hostname.replace(/^\[(.+)\]$/, "$1").toLowerCase();
    return LOOPBACK_HOSTS.has(host);
  } catch {
    return false; // 解析不了按出网处理（保守）
  }
}

/**
 * 订阅 sidecar 事件。返回退订函数——组件卸载时必须调用，否则热重载会叠监听。
 * `handler` 只收到 `SidecarMessage`（protocol 故障走 `onProtocolFailure`）。
 */
export async function onSidecarEvent(
  handler: (msg: SidecarMessage) => void,
  onProtocolFailure?: (payload: { code: string; message: string }) => void
): Promise<UnlistenFn> {
  return listen<ShellEventPayload>(SIDECAR_EVENT, (event) => {
    const payload = event.payload;
    if (payload.kind === "protocol") {
      onProtocolFailure?.({ code: String(payload.code), message: payload.message });
      return;
    }
    // 未知 type 直接忽略（3.4 兼容规则），cast 有生成类型兜底
    handler(payload.event);
  });
}

/** 全局快捷键（Rust 侧 Alt+Space）→ 前端 PTT。 */
export const PTT_SHORTCUT_EVENT = "hotkey://ptt";
export const OPEN_SETTINGS_EVENT = "shell://open-settings";
/// 托盘「开始/停止说话」：单次切换，不带按下/松开语义。
export const TALK_TOGGLE_EVENT = "shell://talk-toggle";

export async function onPttShortcut(
  handler: (pressed: boolean) => void,
): Promise<UnlistenFn> {
  return listen<string>(PTT_SHORTCUT_EVENT, (event) => {
    handler(event.payload === "pressed");
  });
}

export async function onOpenSettings(
  handler: () => void,
): Promise<UnlistenFn> {
  return listen(OPEN_SETTINGS_EVENT, () => handler());
}

/** 托盘「开始/停止说话」：前端自己判断该开还是该停。 */
export async function onTalkToggle(
  handler: () => void,
): Promise<UnlistenFn> {
  return listen(TALK_TOGGLE_EVENT, () => handler());
}

/** R1d 开机自启（插件状态由 Rust 管）。 */
export function autostartGet(): Promise<boolean> {
  return invoke("autostart_get");
}

export function autostartSet(enabled: boolean): Promise<void> {
  return invoke("autostart_set", { enabled });
}

/** R5：关窗行为（true = 隐藏到托盘，false = 直接退出）。 */
export function closeToTrayGet(): Promise<boolean> {
  return invoke("close_to_tray_get");
}

export function closeToTraySet(enabled: boolean): Promise<void> {
  return invoke("close_to_tray_set", { enabled });
}

/** R5：全局 PTT 快捷键（Tauri accelerator 字符串）。 */
export function pttShortcutGet(): Promise<string> {
  return invoke("ptt_shortcut_get");
}

export function pttShortcutSet(accelerator: string): Promise<void> {
  return invoke("ptt_shortcut_set", { accelerator });
}

/** R5：系统通知（后台回复完成；body 由前端截断）。 */
export function appNotify(title: string, body: string): Promise<void> {
  return invoke("app_notify", { title, body });
}

/** R1d 悬浮 HUD（独立小窗，不占任务栏）。 */
export function showHud(): Promise<void> {
  return invoke("show_hud");
}

/** R5：从 HUD 展开主窗口（并收起 HUD）。 */
export function showMainWindow(): Promise<void> {
  return invoke("show_main_window");
}

/** R5：打开独立设置窗口（已存在则聚焦）。 */
export function openSettingsWindow(): Promise<void> {
  return invoke("open_settings_window");
}

export function hideHud(): Promise<void> {
  return invoke("hide_hud");
}

/** R1e 输出设备（cpal 枚举结果）。`id` 与 `name` 同值——cpal 没有稳定 id。 */
export interface OutputDevice {
  id: string;
  name: string;
  isDefault: boolean;
}

export function listOutputDevices(): Promise<OutputDevice[]> {
  return invoke("audio_output_devices");
}

/** `null` = 系统默认输出设备。 */
export function setOutputDevice(device: string | null): Promise<void> {
  return invoke("audio_set_output_device", { device });
}

export function setVolume(volume: number): Promise<void> {
  return invoke("audio_set_volume", { volume });
}

/** 试听音：验证选定输出设备与音量真的生效（判据 2）。 */
export function playTestTone(): Promise<void> {
  return invoke("audio_test_tone");
}

/** 文本输入触发 turn（与 asr_final 等价，3.4/3.5）。 */
export function sendUserText(text: string): Promise<void> {
  return invoke("send_user_text", { text });
}

/** R4 4.4：重说上一轮（sidecar 复用原文，新 turn 取代旧 turn）。 */
export function retryTurn(): Promise<void> {
  return invoke("retry_turn");
}

/** R4 4.5：编辑上一条并重跑（旧 turn 被取代，历史保留）。 */
export function editLastTurn(text: string): Promise<void> {
  return invoke("edit_last_turn", { text });
}

/** 打断在途 turn 并立即回采集（三跳首跳：壳侧先静音，不等 sidecar 确认）。 */
export function interruptTurn(): Promise<void> {
  return invoke("interrupt_turn");
}

/** 只丢弃在途 turn、不回采集（用户点「停止」）。 */
export function cancelTurn(): Promise<void> {
  return invoke("cancel_turn");
}

/** PTT 按下：清播放缓冲 + 开采集。 */
export function pttStart(): Promise<void> {
  return invoke("ptt_start");
}

/** PTT 帧上送（16k mono PCM16；壳侧统一重采样）。 */
export function pttPush(samples: Int16Array | number[]): Promise<void> {
  return invoke("ptt_push", { samples });
}

/** PTT 松开：发终帧并触发 ASR。 */
export function pttStop(): Promise<void> {
  return invoke("ptt_stop");
}

/** 克隆录音开始（bit2 帧分流，与 PTT 互不污染）。 */
export function cloneRecordStart(): Promise<void> {
  return invoke("clone_record_start");
}

export function clonePush(samples: Int16Array | number[]): Promise<void> {
  return invoke("clone_push", { samples });
}

/** 克隆录音结束 → `clone_start`（sidecar 侧才真正开始克隆）。 */
export function cloneRecordStop(): Promise<void> {
  return invoke("clone_record_stop");
}

/** 取消克隆（协作取消：阶段边界生效，4.5）。 */
export function cloneCancel(): Promise<void> {
  return invoke("clone_cancel");
}

/** 人设卡（3.4 拉取语义：壳写 SQLite，sidecar 每轮读取）。 */
export interface PersonaView {
  name: string;
  systemPrompt: string;
}

export interface SettingsView {
  /** mock=无模型契约链；ollama=本地；openai=OpenAI 兼容端点（云端或本地，ADR-016） */
  provider: "mock" | "ollama" | "openai";
  model: string;
  privacyMode: boolean;
  /** OpenAI 兼容端点，填到 /v1 为止；仅 provider=openai 使用 */
  baseUrl: string;
  /** 只读：凭据管理器是否已存 key（写入时忽略） */
  hasKey: boolean;
  /** 只读：首启向导是否已完成（写入时忽略） */
  firstRunDone: boolean;
  /** R2a：语音合成链（mock / cosyvoice2 / openai） */
  ttsProvider: "mock" | "cosyvoice2" | "openai";
  /** 云端 TTS 模型（本地链忽略） */
  ttsModel: string;
  /** 云端 TTS 的 OpenAI 兼容端点 */
  ttsBaseUrl: string;
  /** 只读：凭据管理器里是否已有 TTS key */
  hasTtsKey: boolean;
  /** R2a：语音识别链（mock / whisper / openai） */
  asrProvider: "mock" | "whisper" | "openai";
  /** whisper 档位（tiny/base/small）或云端模型名 */
  asrModel: string;
  /** 云端 ASR 的 OpenAI 兼容端点 */
  asrBaseUrl: string;
  /** 只读：凭据管理器里是否已有 ASR key */
  hasAsrKey: boolean;
  /** 云端逐链同意（2.11）：公网端点保存前必须为真 */
  llmCloudConsent: boolean;
  asrCloudConsent: boolean;
  ttsCloudConsent: boolean;
}

export function getPersona(): Promise<PersonaView> {
  return invoke("get_persona");
}

export function savePersona(persona: PersonaView): Promise<void> {
  return invoke("save_persona", { persona });
}

export function getSettings(): Promise<SettingsView> {
  return invoke("get_settings");
}

export function saveSettings(settings: SettingsView): Promise<void> {
  return invoke("save_settings", { settings });
}

/** 保存云端 LLM 的 API key（Windows 凭据管理器；明文不回传、不入库）。 */
export function saveLlmKey(key: string): Promise<void> {
  return invoke("save_llm_key", { key });
}

export function clearLlmKey(): Promise<void> {
  return invoke("clear_llm_key");
}

/** R2a 2.13：分链 key（chain = asr / tts，provider 目前仅 openai）。 */
export function saveEngineKey(
  chain: "asr" | "tts",
  provider: "openai",
  key: string,
): Promise<void> {
  return invoke("save_engine_key", { chain, provider, key });
}

export function clearEngineKey(
  chain: "asr" | "tts",
  provider: "openai",
): Promise<void> {
  return invoke("clear_engine_key", { chain, provider });
}

export function hasEngineKey(
  chain: "asr" | "tts",
  provider: "openai",
): Promise<boolean> {
  return invoke("has_engine_key", { chain, provider });
}

// ---- 首启向导（ADR-011/016）：壳跑 sidecar `--setup`，进度走独立事件面 ----

export const SETUP_EVENT = "setup://event";

/** R2a 2.6：模型目录候选（contextWindow 目前仅预留，云端接口不返回）。 */
export interface LlmModelOption {
  id: string;
  owner: string | null;
  contextWindow: number | null;
}

export interface SetupReport {
  platform: string;
  python: string;
  frozen: boolean;
  cpu: string;
  ramGb: number | null;
  gpu: { name: string; vramGb: number } | null;
  diskFreeGb: number;
  diskPath: string;
  ollama: { url: string; reachable: boolean; models: string[] };
  runtimeProfiles: string[];
  activeProfile: string | null;
  devVenv: boolean;
  models: Record<string, boolean>;
  recommendedProfile: string;
  needsRuntime: boolean;
  missingModels: string[];
  downloadMb: number;
  runtimeArchiveReady: boolean;
  notes: string[];
}

export type SetupEvent =
  | { type: "detect"; report: SetupReport }
  | { type: "models"; provider: string; models: LlmModelOption[] }
  | { type: "progress"; step: string; item: string; pct: number }
  | {
      type: "result";
      step: string;
      ok: boolean;
      detail?: Record<string, string>;
      report?: SetupReport;
    }
  | { type: "error"; step: string; code: string; message: string };

/** 订阅向导进度（下载 pct）。返回退订函数。 */
export async function onSetupEvent(
  handler: (event: SetupEvent) => void
): Promise<UnlistenFn> {
  return listen<SetupEvent>(SETUP_EVENT, (event) => handler(event.payload));
}

export function setupDetect(): Promise<SetupEvent> {
  return invoke("setup_detect");
}

/** R2a 2.6：LLM 模型目录（Ollama `/api/tags` 或云端 `GET /v1/models`）。 */
export async function listLlmModels(
  provider: "ollama" | "openai",
  baseUrl?: string
): Promise<LlmModelOption[]> {
  const payload = await invoke<{
    type: string;
    models?: LlmModelOption[];
    message?: string;
  }>("setup_models", { provider, baseUrl: baseUrl ?? null });
  if (payload.type === "error") {
    throw new Error(payload.message ?? "拉取模型目录失败");
  }
  return payload.models ?? [];
}

/** 下载运行时或模型；进度经 `onSetupEvent` 推送。 */
export function setupInstall(
  action: "install-runtime" | "install-models",
  options: { profile?: string; ids?: string[] } = {}
): Promise<SetupEvent> {
  return invoke("setup_install", {
    action,
    profile: options.profile ?? null,
    ids: options.ids ?? [],
  });
}

export function completeSetup(): Promise<void> {
  return invoke("complete_setup");
}

/** 让首启向导重新出现（设置抽屉里的「重新运行首启」）。 */
export function resetSetup(): Promise<void> {
  return invoke("reset_setup");
}

/** R1a 迁移失败恢复面（只读 marker + 备份；还原由用户显式触发）。 */
export interface RecoveryBackup {
  name: string;
  path: string;
  modifiedAt: number;
}

export interface RecoveryStatus {
  failed: boolean;
  message: string | null;
  dbPath: string;
  backups: RecoveryBackup[];
}

export function recoveryStatus(): Promise<RecoveryStatus> {
  return invoke("recovery_status");
}

export function recoveryRestore(backupPath: string): Promise<void> {
  return invoke("recovery_restore", { backupPath });
}

// ---- R5 数据与诊断 ----

export interface DataExportResult {
  path: string;
  sessions: number;
  turns: number;
  memories: number;
  chunks: number;
  bytes: number;
}

export interface DataImportResult {
  sessions: number;
  turns: number;
  memories: number;
  chunks: number;
}

/** 导出业务数据（不含设置/凭据）；`path` 省略时落 `<data>/exports/`。 */
export function dataExport(path?: string): Promise<DataExportResult> {
  return invoke("data_export", { path: path ?? null });
}

/** 合并导入导出包：同 id 保留现有记录，需要重启应用生效。 */
export function dataImport(path: string): Promise<DataImportResult> {
  return invoke("data_import", { path });
}

/** 手动备份（VACUUM INTO），返回备份文件路径。 */
export function dataBackup(): Promise<string> {
  return invoke("data_backup");
}

/** 彻底删除个人数据；`confirm` 必须等于后端约定的确认语。 */
export function dataWipe(
  confirm: string
): Promise<{ removed: string[]; clearedKeys: string[] }> {
  return invoke("data_wipe", { confirm });
}

/** 诊断包（脱敏；不含对话原文与 key），返回文件路径与字节数。 */
export function dataDiagnostics(): Promise<{ path: string; bytes: number }> {
  return invoke("data_diagnostics");
}

export interface LocalModelInfo {
  id: string;
  displayName: string;
  kind: string;
  installed: boolean;
  detail: string;
  path: string;
  expectedMb: number;
  bytes: number;
}

export function modelsInfo(): Promise<LocalModelInfo[]> {
  return invoke("models_info");
}

export function modelsRemove(
  ids: string[]
): Promise<{ removed: string[]; freedBytes: number }> {
  return invoke("models_remove", { ids });
}

// ---- 窗口控制（自绘标题栏，decorations:false） ----

/**
 * 浏览器里跑 `npm run dev` 时没有 Tauri 运行时：窗口控制静默失效，
 * 而不是抛 unhandled rejection 把自绘标题栏炸掉。
 */
export function isTauriRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function minimizeWindow(): Promise<void> {
  if (!isTauriRuntime()) return;
  await getCurrentWindow().minimize();
}

/** 返回切换后的最大化状态（标题栏图标要用）。 */
export async function toggleMaximizeWindow(): Promise<boolean> {
  if (!isTauriRuntime()) return false;
  const win = getCurrentWindow();
  await win.toggleMaximize();
  return win.isMaximized();
}

export async function closeWindow(): Promise<void> {
  if (!isTauriRuntime()) return;
  await getCurrentWindow().close();
}

export async function isWindowMaximized(): Promise<boolean> {
  if (!isTauriRuntime()) return false;
  return getCurrentWindow().isMaximized();
}

/** 窗口尺寸/最大化变化（标题栏图标同步用）。 */
export async function onWindowResized(
  handler: () => void
): Promise<UnlistenFn> {
  if (!isTauriRuntime()) return () => {};
  return getCurrentWindow().onResized(() => handler());
}

/** 音色槽位（ADR-008）：内置 + 克隆列表；selected 由服务端标记。 */
export interface VoiceView {
  id: string;
  displayName: string;
  status: "ready" | "training" | "failed" | string;
  qualityScore: number | null;
  createdAt: number;
  selected: boolean;
}

export function listVoices(): Promise<VoiceView[]> {
  return invoke("list_voices");
}

export function selectVoice(voiceId: string): Promise<void> {
  return invoke("select_voice", { voiceId });
}

/** R5：音色治理（改名 / 删除；删除前必须解绑会话）。 */
export function renameVoice(voiceId: string, displayName: string): Promise<void> {
  return invoke("voice_rename", { voiceId, displayName });
}

export function deleteVoice(voiceId: string): Promise<void> {
  return invoke("voice_delete", { voiceId });
}

/** R1a 历史读接口（Rust 只读；写入仍由 sidecar TurnRepo 负责）。 */
export interface TurnView {
  turnId: string;
  sessionId: string;
  seq: number;
  userText: string;
  assistantText: string | null;
  status: "complete" | "cancelled" | "failed" | string;
  failReason: string | null;
  startedAt: number;
  endedAt: number | null;
  /** R4 4.4：被哪条新 turn 取代；NULL = 当前可见 */
  supersededBy: string | null;
  /** R4 4.3：异步质检（NULL = 未质检） */
  groundingVerdict: "faithful" | "unfaithful" | null;
  groundingScore: number | null;
  /** 未被记忆支撑的说法（JSON 数组文本） */
  groundingClaims: string | null;
}

export function historyList(
  sessionId: string,
  limit = 50,
  offset = 0,
  includeSuperseded = false
): Promise<TurnView[]> {
  return invoke("history_list", {
    sessionId,
    limit,
    offset,
    includeSuperseded,
  });
}

export function historyGet(turnId: string): Promise<TurnView | null> {
  return invoke("history_get", { turnId });
}

export function historySearch(
  query: string,
  sessionId?: string,
  limit = 20,
  offset = 0,
  includeSuperseded = false
): Promise<TurnView[]> {
  return invoke("history_search", {
    query,
    sessionId: sessionId ?? null,
    limit,
    offset,
    includeSuperseded,
  });
}

/** R1c 会话生命周期。 */
export interface SessionView {
  id: string;
  title: string | null;
  startedAt: number;
  lastActiveAt: number;
  archivedAt: number | null;
}

export function sessionList(includeArchived = false): Promise<SessionView[]> {
  return invoke("session_list", { includeArchived });
}

export function sessionCreate(title?: string): Promise<SessionView> {
  return invoke("session_create", { title: title ?? null });
}

export function sessionRename(sessionId: string, title: string): Promise<void> {
  return invoke("session_rename", { sessionId, title });
}

export function sessionArchive(sessionId: string): Promise<void> {
  return invoke("session_archive", { sessionId });
}

export function sessionDelete(sessionId: string): Promise<void> {
  return invoke("session_delete", { sessionId });
}

export function sessionOpen(sessionId: string): Promise<void> {
  return invoke("session_open", { sessionId });
}

/** R3a 3.7：记忆管理读/删（编辑/合并要重新嵌入，归 sidecar）。 */
export interface MemoryView {
  id: string;
  fact: string;
  category: "preference" | "event" | "identity" | "other";
  createdAt: number;
  lastSeenAt: number;
  sourceSessionId: string | null;
  sourceSessionTitle: string | null;
  sourceTurnSeq: number | null;
}

/** R3a 3.8：这条记忆被哪些回复用过。 */
export interface MemoryUsage {
  turnId: string;
  sessionId: string;
  sessionTitle: string | null;
  seq: number;
  userText: string;
  usedAt: number;
}

/** 记忆关系图谱：co-used 为同一轮共被引用，same-session 为同会话提取。 */
export interface MemoryGraphNode {
  id: string;
  fact: string;
  category: "preference" | "event" | "identity" | "other";
  lastSeenAt: number;
  degree: number;
}

export interface MemoryGraphEdge {
  source: string;
  target: string;
  kind: "co-used" | "same-session";
  weight: number;
}

export interface MemoryGraph {
  nodes: MemoryGraphNode[];
  edges: MemoryGraphEdge[];
}

export function listMemories(limit = 200): Promise<MemoryView[]> {
  return invoke("memory_list", { profileId: null, limit });
}

export function memoryGraph(limit = 300): Promise<MemoryGraph> {
  return invoke("memory_graph", { profileId: null, limit });
}

export function memoryUsage(factId: string): Promise<MemoryUsage[]> {
  return invoke("memory_usage", { factId, limit: 50 });
}

export function deleteMemory(factId: string): Promise<void> {
  return invoke("memory_delete", { factId });
}

/** R3b：写接口走一次性 sidecar 进程（重新嵌入后落库）。 */
export function addMemory(fact: string, category: string): Promise<void> {
  return invoke("memory_add", { fact, category });
}

export function updateMemory(
  factId: string,
  fact: string,
  category: string,
): Promise<void> {
  return invoke("memory_update", { factId, fact, category });
}

export function mergeMemories(
  ids: string[],
  fact: string,
  category: string,
): Promise<void> {
  return invoke("memory_merge", { ids, fact, category });
}

/** R5 批量导入：每行一条，可写 `事实|类别`；与现有事实同文的跳过。 */
export function importMemories(
  text: string
): Promise<{ op: string; added: number; skipped: number; ids: string[] }> {
  return invoke("memory_import", { text });
}

/**
 * 类型对拍的「反向使用」：这几条断言保证前端构造的控制消息与生成类型一致
 * （壳侧真正发送走命令而非直接写 JSON 行，故只做编译期校验）。
 */
export type ShellControlAction = ControlMsg["action"];
export type UserTextPayload = Pick<UserTextMsg, "text">;
export type CloneStartPayload = Pick<CloneStartMsg, "sample_keys">;
