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

/** 文本输入触发 turn（与 asr_final 等价，3.4/3.5）。 */
export function sendUserText(text: string): Promise<void> {
  return invoke("send_user_text", { text });
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

// ---- 首启向导（ADR-011/016）：壳跑 sidecar `--setup`，进度走独立事件面 ----

export const SETUP_EVENT = "setup://event";

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

/**
 * 类型对拍的「反向使用」：这几条断言保证前端构造的控制消息与生成类型一致
 * （壳侧真正发送走命令而非直接写 JSON 行，故只做编译期校验）。
 */
export type ShellControlAction = ControlMsg["action"];
export type UserTextPayload = Pick<UserTextMsg, "text">;
export type CloneStartPayload = Pick<CloneStartMsg, "sample_keys">;
