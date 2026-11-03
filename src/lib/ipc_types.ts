/**
 * 本文件由 `node scripts/gen-ipc-types.mjs` 生成，**不要手改**。
 * 唯一来源：sidecar/echoes_sidecar/ipc/schema.py（3.4 冻结协议，13.2-1）。
 * 手改会在 `npm run ipc:check` 与 CI schema-drift 里判红并给出再生成命令。
 */

export const PROTOCOL_VERSION = "1.0" as const;

/** 3.4.1 错误码表（前端按 code 渲染文案/重试策略） */
export type ErrorCode =
  | "SAMPLE_TOO_SHORT"
  | "SAMPLE_TOO_NOISY"
  | "CLONE_QUALITY_LOW"
  | "CLONE_ENGINE_FAILED"
  | "CLONE_CANCELLED"
  | "MODEL_NOT_LOADED"
  | "VOICE_NOT_AVAILABLE"
  | "MIC_NOT_AVAILABLE"
  | "LLM_PROVIDER_UNAVAILABLE"
  | "LLM_KEY_MISSING"
  | "ASR_ENGINE_ERROR"
  | "TTS_ENGINE_ERROR"
  | "STORAGE_ERROR"
  | "HISTORY_WRITE_FAILED"
  | "PROTOCOL_MISMATCH"
  | "INTERNAL_ERROR";

/** HelloMsg（sidecar → 壳） */
export interface HelloMsg {
  type: "hello";
  sidecar_version: string;
  protocol_version: "1.0";
  t: number;
  engines: EngineState[];
}

/** AsrPartialMsg（sidecar → 壳） */
export interface AsrPartialMsg {
  type: "asr_partial";
  session_id: string;
  text: string;
  t: number;
}

/** AsrFinalMsg（sidecar → 壳） */
export interface AsrFinalMsg {
  type: "asr_final";
  session_id: string;
  text: string;
  is_final: boolean;
  t: number;
}

/** AssistantTextMsg（sidecar → 壳） */
export interface AssistantTextMsg {
  type: "assistant_text";
  session_id: string;
  text: string;
  t: number;
}

/** TurnCompleteMsg（sidecar → 壳） */
export interface TurnCompleteMsg {
  type: "turn_complete";
  session_id: string;
  turn_seq: number;
  status: "SUCCESS" | "CANCELLED" | "FAILED";
  timings: Timings;
}

/** CloneProgressMsg（sidecar → 壳） */
export interface CloneProgressMsg {
  type: "clone_progress";
  session_id: string;
  phase: "recording" | "training" | "checking";
  pct: number;
  t: number;
}

/** ErrorMsg（sidecar → 壳） */
export interface ErrorMsg {
  type: "error";
  session_id?: string;
  code: ErrorCode;
  message: string;
  fatal: boolean;
  t: number;
}

/** StateMsg（sidecar → 壳） */
export interface StateMsg {
  type: "state";
  session_id?: string;
  state: "booting" | "ready" | "generating" | "speaking" | "error";
  t: number;
}

/** ControlMsg（shell → sidecar） */
export interface ControlMsg {
  type: "control";
  action: "interrupt" | "cancel_turn" | "open_session";
  session_id: string;
  turn_seq?: number;
}

/** UserTextMsg（shell → sidecar） */
export interface UserTextMsg {
  type: "user_text";
  session_id: string;
  text: string;
}

/** RetryMsg（shell → sidecar） */
export interface RetryMsg {
  type: "retry";
  session_id: string;
  text?: string;
}

/** CloneStartMsg（shell → sidecar） */
export interface CloneStartMsg {
  type: "clone_start";
  session_id: string;
  sample_keys: string[];
}

/** CloneCancelMsg（shell → sidecar） */
export interface CloneCancelMsg {
  type: "clone_cancel";
  session_id: string;
}

/** EngineState（嵌套结构体） */
export interface EngineState {
  name: string;
  ready: boolean;
  provider?: string;
  model?: string;
}

/** Timings（嵌套结构体） */
export interface Timings {
  total_ms: number;
  llm_first_token_ms?: number;
  tts_first_audio_ms?: number;
}

/** sidecar → 壳：事件与状态（3.4） */
export type SidecarMessage =
  | HelloMsg
  | AsrPartialMsg
  | AsrFinalMsg
  | AssistantTextMsg
  | TurnCompleteMsg
  | CloneProgressMsg
  | ErrorMsg
  | StateMsg;

/** 壳 → sidecar：控制面（3.4 v1.4 四类） */
export type ShellMessage =
  | ControlMsg
  | UserTextMsg
  | RetryMsg
  | CloneStartMsg
  | CloneCancelMsg;

export type SidecarMessageType = SidecarMessage["type"];
export type ShellMessageType = ShellMessage["type"];
