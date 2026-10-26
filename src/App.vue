<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import type { UnlistenFn } from "@tauri-apps/api/event";

import * as ipc from "./lib/ipc";
import type { SidecarMessage } from "./lib/ipc";
import FirstRun from "./FirstRun.vue";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  /** 被打断的 assistant 气泡（3.4 三跳：turn_complete(status=CANCELLED)） */
  interrupted?: boolean;
  /** 协议/引擎错误：渲染成提示条，不伪装成她的一句话 */
  kind?: "error";
}

// 侧车帧类型来自 `lib/ipc_types.ts`（由 sidecar 的 pydantic 模型生成，13.2-1）：
// 协议改名会在这里编译期报错，而不是运行时静默失败。

// 阶段 0 第一周：文本→LLM→文本 经 StdioTransport 打通；
// 麦克风（PTT）与音频播放为壳侧采集验证（风险 10），后续接入。
const messages = ref<ChatMessage[]>([]);
const input = ref("");
const busy = ref(false);
const engineState = ref("connecting");
// hello.engines 分级就绪（3.4 v1.4）：ASR 未就绪前 PTT 不可用。
const asrReady = ref(false);
// assistant 流式气泡边界：true=最后一条 assistant 气泡在途（assistant_text 全量替换渲染），
// 收尾由 turn_complete（或 error）复位 —— v1.4.1 语义。
const streaming = ref(false);
let unlisten: UnlistenFn | null = null;

// ---- 展示层状态（不改协议；sidecar 仍是唯一状态源） ----
const historyEl = ref<HTMLElement | null>(null);
// 用户往上翻看旧消息时不要抢滚动；回到底部附近才继续跟。
const pinned = ref(true);

function onThreadScroll(): void {
  const el = historyEl.value;
  if (!el) return;
  pinned.value = el.scrollHeight - el.scrollTop - el.clientHeight < 64;
}

const stateLabel = computed(() => {
  switch (engineState.value) {
    case "ready":
      return "就绪";
    case "booting":
      return "引擎启动中";
    case "generating":
      return "正在想";
    case "speaking":
      return "正在说";
    case "error":
      return "连接异常";
    case "connecting":
      return "连接中";
    default:
      return engineState.value;
  }
});
const stateTone = computed(() => {
  if (engineState.value === "error") return "error";
  if (engineState.value === "ready") return "ready";
  if (engineState.value === "generating" || engineState.value === "speaking") {
    return "active";
  }
  return "waiting";
});
const pttHint = computed(() => {
  if (!asrReady.value) return "语音引擎就绪后可用";
  if (engineState.value === "generating" || engineState.value === "speaking") {
    return "按下会打断当前回复";
  }
  if (engineState.value !== "ready") return "等待引擎就绪";
  return "按住说话 · 松开发送";
});
const pttTitle = computed(() => {
  if (!asrReady.value) return "语音引擎就绪后可用";
  if (busy.value) return "按住说话（会打断当前回复）";
  return "按住说话（松开结束）";
});

// ---- 克隆音色（§12 步骤 5）：progress 驱动 UI，失败只报错不回退（2.5） ----
const clonePhase = ref<null | "recording" | "training" | "checking">(null);
const clonePct = ref(0);
const cloneError = ref("");
const hasClonedVoice = ref(false);
const CLONE_MIN_SECONDS = 3;
const CLONE_MAX_SECONDS = 6;
const clonePhaseLabel = computed(() => {
  switch (clonePhase.value) {
    case "recording":
      return "录音中";
    case "training":
      return "克隆中";
    case "checking":
      return "校验中";
    default:
      return "";
  }
});

// ---- 人设卡 / Settings（3.4 拉取语义：壳写 SQLite，sidecar 每轮读取） ----
const showSettings = ref(false);
const personaDraft = ref<ipc.PersonaView>({ name: "", systemPrompt: "" });
const settingsDraft = ref<ipc.SettingsView>({
  provider: "ollama",
  model: "qwen3:8b",
  privacyMode: true,
  baseUrl: "",
  hasKey: false,
  firstRunDone: false,
});
// 首启向导：设置还没读到时保持关闭，读到 firstRunDone=false 才弹
const firstRun = ref(false);
// 云端 key 只提交、不回显：输入框永远从空开始（ADR-016）
const llmKeyDraft = ref("");
const keyStatus = ref("");
const voices = ref<ipc.VoiceView[]>([]);
const voicesStatus = ref("");
const profileStatus = ref("");
let profileRetry: number | null = null;
let profileAttempts = 0;

const companionName = computed(() => personaDraft.value.name.trim() || "Echoes");
const selectedVoiceName = computed(
  () => voices.value.find((voice) => voice.selected)?.displayName ?? "内置音色",
);

// 新消息与流式增量都跟到底：写信的人不该手动追页。
watch(
  () => [messages.value.length, messages.value[messages.value.length - 1]?.text],
  async () => {
    if (!pinned.value) return;
    await nextTick();
    const el = historyEl.value;
    if (el) el.scrollTop = el.scrollHeight;
  },
);

async function loadProfile(): Promise<void> {
  try {
    const [persona, settings] = await Promise.all([
      ipc.getPersona(),
      ipc.getSettings(),
    ]);
    personaDraft.value = persona;
    settingsDraft.value = settings;
    firstRun.value = !settings.firstRunDone;
    profileStatus.value = "";
    profileAttempts = 0;
  } catch (err) {
    profileAttempts += 1;
    profileStatus.value =
      profileAttempts >= 5 ? `⚠ ${String(err)}` : "等待 sidecar 初始化…";
    if (profileAttempts < 5) {
      profileRetry = window.setTimeout(() => {
        profileRetry = null;
        void loadProfile();
      }, 1500);
    }
  }
}

async function savePersona(): Promise<void> {
  try {
    await ipc.savePersona(personaDraft.value);
    profileStatus.value = "人设已保存（下一轮对话生效）";
  } catch (err) {
    profileStatus.value = `⚠ ${String(err)}`;
  }
}

async function saveSettings(): Promise<void> {
  try {
    await ipc.saveSettings(settingsDraft.value);
    profileStatus.value = "设置已保存（下一轮对话生效）";
  } catch (err) {
    profileStatus.value = `⚠ ${String(err)}`;
  }
}

/** 切到云端时自动关隐私模式：16.1 下两者互斥，留着只会每轮报错。 */
function onProviderChange(): void {
  if (settingsDraft.value.provider === "openai") {
    settingsDraft.value.privacyMode = false;
  }
}

async function saveKey(): Promise<void> {
  const key = llmKeyDraft.value.trim();
  if (!key) return;
  try {
    await ipc.saveLlmKey(key);
    llmKeyDraft.value = "";
    settingsDraft.value.hasKey = true;
    keyStatus.value = "已保存到 Windows 凭据管理器";
  } catch (err) {
    keyStatus.value = `⚠ ${String(err)}`;
  }
}

async function clearKey(): Promise<void> {
  try {
    await ipc.clearLlmKey();
    settingsDraft.value.hasKey = false;
    keyStatus.value = "已清除";
  } catch (err) {
    keyStatus.value = `⚠ ${String(err)}`;
  }
}

async function loadVoices(): Promise<void> {
  try {
    voices.value = await ipc.listVoices();
    hasClonedVoice.value = voices.value.some(
      (voice) => voice.id !== "builtin:default" && voice.status === "ready",
    );
    voicesStatus.value = "";
  } catch (err) {
    voicesStatus.value = `⚠ ${String(err)}`;
  }
}

async function chooseVoice(voiceId: string): Promise<void> {
  try {
    await ipc.selectVoice(voiceId);
    await loadVoices();
    profileStatus.value = "音色已切换（下一轮对话生效）";
  } catch (err) {
    profileStatus.value = `⚠ ${String(err)}`;
  }
}

function voiceLabel(voice: ipc.VoiceView): string {
  const score =
    voice.qualityScore === null
      ? ""
      : ` · 相似度 ${Math.round(voice.qualityScore * 100)}%`;
  if (voice.status === "ready") {
    return (voice.id === "builtin:default" ? "内置" : "已就绪") + score;
  }
  if (voice.status === "training") {
    return "克隆中";
  }
  return voice.qualityScore === null ? "失败" : `失败${score}`;
}

function protocolDown(code: string, message: string): void {
  engineState.value = "error";
  messages.value.push({
    role: "assistant",
    kind: "error",
    text: `${code}：${message}`,
  });
}

onMounted(async () => {
  unlisten = await ipc.onSidecarEvent(handleFrame, (failure) => {
    protocolDown(failure.code, failure.message);
  });
  void loadProfile();
  void loadVoices();
});

onUnmounted(() => {
  unlisten?.();
  if (profileRetry !== null) {
    window.clearTimeout(profileRetry);
    profileRetry = null;
  }
});

function handleFrame(frame: SidecarMessage): void {
  switch (frame.type) {
    case "hello":
      asrReady.value = frame.engines.some((e) => e.name === "asr" && e.ready);
      break;
    case "state": {
      // 3.5：state 归 sidecar 所有，壳只是渲染者——busy 以状态机为准，
      // 不再靠本地标志推断（打断/失败都要能可靠解锁）
      const next = String(frame.state);
      engineState.value = next;
      if (next === "ready") {
        busy.value = false;
        streaming.value = false;
      } else if (next === "generating" || next === "speaking") {
        busy.value = true;
      }
      break;
    }
    case "asr_final":
      // 语音面输入：sidecar 随后立即进入 turn（asr_final 与 user_text 等价）。
      messages.value.push({ role: "user", text: frame.text });
      pinned.value = true; // 自己说的话一定跟到底
      busy.value = true;
      micStatus.value = "麦克风就绪";
      break;
    case "assistant_text": {
      const text = frame.text;
      const last = messages.value[messages.value.length - 1];
      if (streaming.value && last?.role === "assistant") {
        last.text = text; // text=截至当前全量，直接替换
      } else {
        messages.value.push({ role: "assistant", text });
        streaming.value = true;
      }
      break;
    }
    case "turn_complete": {
      const status = frame.status;
      const last = messages.value[messages.value.length - 1];
      if (status === "CANCELLED" && last?.role === "assistant") {
        last.interrupted = true; // 被打断的半句留痕，而不是悄悄丢掉
      }
      streaming.value = false;
      busy.value = false;
      break;
    }
    case "clone_progress":
      // recording → training → checking（4.5）：progress 缺失即「假死」，所以这里必须驱动 UI
      clonePhase.value =
        frame.phase === "recording" || frame.phase === "training" || frame.phase === "checking"
          ? frame.phase
          : "training";
      clonePct.value = Number(frame.pct) || 0;
      if (clonePhase.value === "checking" && clonePct.value >= 100) {
        hasClonedVoice.value = true;
        clonePhase.value = null;
        clonePct.value = 100;
        void loadVoices();
      }
      break;
    case "error":
      messages.value.push({
        role: "assistant",
        kind: "error",
        text: `${frame.code}：${frame.message}`,
      });
      streaming.value = false;
      busy.value = false;
      if (frame.code.startsWith("CLONE") || frame.code.startsWith("SAMPLE")) {
        // 克隆失败：清进度、保留错误文案，音色在 sidecar 侧已落 failed（2.5 不回退）
        cloneError.value = `${frame.code}：${frame.message}`;
        clonePhase.value = null;
        clonePct.value = 0;
      }
      break;
    default:
      break;
  }
}

// 壳侧麦克风自检（文档 12.3 首周 · 风险 10 最小验证面）：
// 拿轨道即声明权限/设备可见；真正采集在下方 PTT（48k → Rust 重采样 16k → WS）。
const micStatus = ref("");

// 既有文案带 ✅/⚠/🎙 前缀；界面用色块表达语气，这里只取正文。
const micNotice = computed(() => micStatus.value.replace(/^[✅⚠🎙]\s*/u, "").trim());
const micTone = computed(() => (micStatus.value.startsWith("⚠") ? "warn" : ""));

async function micProbe(): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) {
    micStatus.value = "⚠ MIC_NOT_AVAILABLE：WebView 无 getUserMedia";
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const track = stream.getAudioTracks()[0];
    const settings = track.getSettings();
    micStatus.value = `✅ ${track.label.slice(0, 36)} @ ${settings.sampleRate ?? "?"}Hz`;
    stream.getTracks().forEach((t) => t.stop());
  } catch (err) {
    const name = (err as DOMException).name;
    micStatus.value =
      name === "NotFoundError"
        ? "⚠ MIC_NOT_AVAILABLE：未检测到麦克风"
        : `⚠ ${name}：${(err as Error).message}`;
  }
}

// ---- 按住说话（§12 步骤 4）：getUserMedia 48k PCM16 分片 → Rust 重采样 16k → WS ----
const PTT_CHUNK = 4800; // 100ms @48k
const captureHeld = ref(false);
const listening = ref(false);
const cloneSeconds = ref(0);
/** 3.5 动作矩阵：generating/speaking 期 PTT 可用，按下即打断（不是禁用）。 */
const pttEnabled = computed(
  () =>
    asrReady.value &&
    clonePhase.value === null &&
    (engineState.value === "ready" ||
      engineState.value === "generating" ||
      engineState.value === "speaking"),
);

// 3.5 用户动作矩阵：克隆入口只在 ready 可用，且不与 turn / 在途克隆并发
const cloneEnabled = computed(
  () =>
    !busy.value &&
    engineState.value === "ready" &&
    clonePhase.value === null &&
    !captureHeld.value,
);
type CaptureMode = "ptt" | "clone";
// 必须是 ref：模板要按模式区分按钮文案/样式
const captureMode = ref<CaptureMode>("ptt");

// 按住期间不能把按钮置灰：disabled 元素收不到 mouseup，会一直录到上限。
const pttHoldDisabled = computed(() => !captureHeld.value && !pttEnabled.value);
const cloneHoldDisabled = computed(() => !captureHeld.value && !cloneEnabled.value);

let micStream: MediaStream | null = null;
let micCtx: AudioContext | null = null;
let micSource: MediaStreamAudioSourceNode | null = null;
let micProcessor: ScriptProcessorNode | null = null;
let micMute: GainNode | null = null;
let pendingSamples: number[] = [];
// 串行化分片上行：Tauri IPC 保序，但 Promise 链保证「尾片 → is_final」严格在后。
let sendChain: Promise<unknown> = Promise.resolve();

function enqueueChunk(samples: number[]): void {
  // PTT 与克隆共用一条采集链，只在下行命令上分流（克隆帧带 bit2，3.4）
  sendChain = sendChain
    .then(() => (captureMode.value === "clone" ? ipc.clonePush(samples) : ipc.pttPush(samples)))
    .catch((err) => {
      micStatus.value = `⚠ 音频发送失败：${String(err)}`;
    });
}

function cleanupMic(): void {
  if (micProcessor) {
    micProcessor.onaudioprocess = null;
    micProcessor.disconnect();
  }
  micSource?.disconnect();
  micMute?.disconnect();
  micStream?.getTracks().forEach((track) => track.stop());
  if (micCtx && micCtx.state !== "closed") {
    void micCtx.close();
  }
  micProcessor = null;
  micSource = null;
  micMute = null;
  micStream = null;
  micCtx = null;
  pendingSamples = [];
  listening.value = false;
}

function micErrorMessage(err: unknown): string {
  const name = (err as DOMException).name;
  if (name === "NotFoundError") return "MIC_NOT_AVAILABLE：未检测到麦克风";
  if (name === "NotAllowedError") return "MIC_NOT_AVAILABLE：麦克风权限被拒绝";
  return `${name}：${(err as Error).message}`;
}

let cloneTimer: number | null = null;

function stopCloneTimer(): void {
  if (cloneTimer !== null) {
    window.clearInterval(cloneTimer);
    cloneTimer = null;
  }
}

/** 采集入口：PTT 与克隆共用 48k→16k→WS 链路，只在命令与帧 flags 上分流。 */
async function startCapture(mode: CaptureMode): Promise<void> {
  const allowed = mode === "clone" ? cloneEnabled.value : pttEnabled.value;
  if (!allowed || captureHeld.value) return;
  captureHeld.value = true;
  captureMode.value = mode;
  if (mode === "clone") {
    cloneError.value = "";
    clonePhase.value = "recording";
    clonePct.value = 0;
    cloneSeconds.value = 0;
  } else if (busy.value) {
    // 三跳首跳：按下即关闸门 + 清播放缓冲 + 通知 sidecar 取消（≤100ms 内静音，
    // 不等 sidecar 确认）。必须先于 getUserMedia——权限/设备协商可能要几百毫秒。
    void ipc.interruptTurn().catch((err) => {
      micStatus.value = `⚠ 打断失败：${String(err)}`;
    });
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    if (!captureHeld.value) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    // PTT 先 flush 在途播放（打断首跳）；克隆与播放无关，只复位重采样器
    await (mode === "clone" ? ipc.cloneRecordStart() : ipc.pttStart());
    if (!captureHeld.value) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }

    const ctx = new AudioContext({ sampleRate: 48000 });
    if (Math.round(ctx.sampleRate) !== 48000) {
      const actual = ctx.sampleRate;
      await ctx.close();
      stream.getTracks().forEach((track) => track.stop());
      throw new Error(`采集采样率非 48k（${actual}Hz）`);
    }
    await ctx.resume();
    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    pendingSamples = [];
    processor.onaudioprocess = (event) => {
      const data = event.inputBuffer.getChannelData(0);
      for (let i = 0; i < data.length; i++) {
        const value = Math.max(-1, Math.min(1, data[i]));
        pendingSamples.push(Math.round(value < 0 ? value * 0x8000 : value * 0x7fff));
      }
      while (pendingSamples.length >= PTT_CHUNK) {
        enqueueChunk(pendingSamples.splice(0, PTT_CHUNK));
      }
    };
    source.connect(processor);
    // ScriptProcessor 需挂到 destination 才会被驱动；零增益避免麦克风回放啸叫。
    const mute = ctx.createGain();
    mute.gain.value = 0;
    processor.connect(mute);
    mute.connect(ctx.destination);

    micStream = stream;
    micCtx = ctx;
    micSource = source;
    micProcessor = processor;
    micMute = mute;
    listening.value = true;
    micStatus.value = mode === "clone" ? "🎙 录音中…（3–6 秒）" : "🎙 录音中…";

    if (mode === "clone") {
      // 超上限自动收尾：一直按着录出 30 秒样本对克隆没有帮助，只增加等待
      cloneTimer = window.setInterval(() => {
        cloneSeconds.value += 1;
        if (cloneSeconds.value >= CLONE_MAX_SECONDS) {
          void stopCapture();
        }
      }, 1000);
    }
  } catch (err) {
    captureHeld.value = false;
    captureMode.value = "ptt";
    stopCloneTimer();
    cleanupMic();
    micStatus.value = `⚠ ${micErrorMessage(err)}`;
    if (mode === "clone") {
      clonePhase.value = null;
      cloneError.value = micErrorMessage(err);
    }
  }
}

async function stopCapture(): Promise<void> {
  if (!captureHeld.value) return;
  captureHeld.value = false;
  const mode = captureMode.value;
  stopCloneTimer();
  if (!micStream) return; // getUserMedia 尚未返回：startCapture 会自行清理
  const rest = pendingSamples;
  pendingSamples = [];
  cleanupMic();
  try {
    await sendChain;
    if (rest.length > 0) {
      await (mode === "clone" ? ipc.clonePush(rest) : ipc.pttPush(rest));
    }
    if (mode === "clone") {
      await ipc.cloneRecordStop();
      cloneSeconds.value = 0;
      micStatus.value = "样本已收到，正在生成音色…";
    } else {
      await ipc.pttStop();
      micStatus.value = "识别中…";
    }
  } catch (err) {
    micStatus.value = `⚠ ${String(err)}`;
    if (mode === "clone") {
      clonePhase.value = null;
      cloneError.value = String(err);
    }
  }
}

function pttStart(): void {
  void startCapture("ptt");
}

function pttStop(): void {
  if (captureMode.value === "ptt") void stopCapture();
}

function cloneStart(): void {
  void startCapture("clone");
}

function cloneStop(): void {
  if (captureMode.value === "clone") void stopCapture();
}

function cancelClone(): void {
  void ipc.cloneCancel().catch((err) => {
    cloneError.value = String(err);
  });
}

function onSetupDone(): void {
  firstRun.value = false;
  // 向导可能刚写入了 provider/model/key：重新拉一次设置与音色
  void loadProfile();
  void loadVoices();
}

async function rerunSetup(): Promise<void> {
  try {
    await ipc.resetSetup();
    firstRun.value = true;
    showSettings.value = false;
  } catch (err) {
    profileStatus.value = `⚠ ${String(err)}`;
  }
}

function onWindowBlur(): void {
  void stopCapture();
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && showSettings.value) {
    showSettings.value = false;
  }
}

onMounted(() => {
  window.addEventListener("blur", onWindowBlur);
  window.addEventListener("keydown", onKeydown);
});

onUnmounted(() => {
  window.removeEventListener("blur", onWindowBlur);
  window.removeEventListener("keydown", onKeydown);
  captureHeld.value = false;
  stopCloneTimer();
  cleanupMic();
});

/** 停止播放（3.5 动作矩阵）：丢弃当前 turn 但不进入采集 → `control(cancel_turn)`。 */
function stopTurn(): void {
  void ipc.cancelTurn().catch((err) => {
    micStatus.value = `⚠ 停止失败：${String(err)}`;
  });
}

async function send(): Promise<void> {
  const text = input.value.trim();
  if (!text) return;
  if (busy.value) {
    // 3.5：文本输入 = 打断并发起新 turn（旧 turn 收尾为 CANCELLED）
    void ipc.interruptTurn().catch(() => {});
  }
  messages.value.push({ role: "user", text });
  input.value = "";
  pinned.value = true;
  busy.value = true;
  try {
    await ipc.sendUserText(text);
  } catch (err) {
    messages.value.push({
      role: "assistant",
      kind: "error",
      text: `发送失败：${String(err)}`,
    });
    streaming.value = false;
    busy.value = false;
  }
}
</script>

<template>
  <div class="app">
    <FirstRun v-if="firstRun" @done="onSetupDone" />
    <header class="letterhead">
      <div class="lh-id">
        <p class="wordmark">Echoes</p>
        <p class="lh-name">
          <span class="name">{{ companionName }}</span>
          <span class="state" :data-tone="stateTone">
            <span class="dot" aria-hidden="true"></span>{{ stateLabel }}
          </span>
        </p>
      </div>
      <div class="lh-actions">
        <button
          type="button"
          class="chip"
          :title="`当前音色：${selectedVoiceName}`"
          @click="showSettings = true"
        >
          {{ selectedVoiceName }}
        </button>
        <button v-if="busy" type="button" class="quiet" @click="stopTurn">
          停止
        </button>
        <button
          type="button"
          class="icon"
          aria-label="设置"
          title="设置（Esc 关闭）"
          @click="showSettings = true"
        >
          <svg
            width="17"
            height="17"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            aria-hidden="true"
          >
            <path d="M4 7h9M18 7h2M4 17h3M12 17h8" />
            <circle cx="15.5" cy="7" r="2.2" />
            <circle cx="9.5" cy="17" r="2.2" />
          </svg>
        </button>
      </div>
    </header>

    <ol ref="historyEl" class="thread" @scroll.passive="onThreadScroll">
      <li v-if="messages.length === 0" class="empty">
        <p class="empty-title">还没有开始。</p>
        <p class="empty-sub">按住下面的圆钮说第一句话，或者直接写字。</p>
      </li>

      <li
        v-for="(m, i) in messages"
        :key="i"
        class="msg"
        :class="m.kind === 'error' ? 'notice-row' : m.role"
      >
        <template v-if="m.kind === 'error'">
          <p class="notice">{{ m.text }}</p>
        </template>

        <template v-else-if="m.role === 'assistant'">
          <p class="said">
            {{ m.text }}<span
              v-if="streaming && i === messages.length - 1"
              class="caret"
              aria-hidden="true"
            ></span>
          </p>
          <p v-if="m.interrupted" class="cut">已打断</p>
        </template>

        <template v-else>
          <p class="mine">{{ m.text }}</p>
        </template>
      </li>
    </ol>

    <div v-if="clonePhase !== null || cloneError" class="clone-strip" role="status">
      <template v-if="clonePhase">
        <span class="strip-label">{{ clonePhaseLabel }}</span>
        <div class="meter">
          <span class="meter-fill" :style="{ width: `${clonePct}%` }"></span>
        </div>
        <span class="strip-pct">{{ Math.round(clonePct) }}%</span>
        <button type="button" class="quiet" @click="cancelClone">取消</button>
      </template>
      <p v-if="cloneError" class="strip-error">{{ cloneError }}</p>
    </div>

    <footer class="composer">
      <form class="write" @submit.prevent="send">
        <input
          v-model="input"
          type="text"
          placeholder="写点什么…"
          aria-label="文字消息"
          autocomplete="off"
        />
        <button type="submit" class="send" :disabled="input.trim() === ''">
          发送
        </button>
      </form>

      <div class="speak">
        <span
          class="ring"
          :class="{ live: listening, busy: busy && !listening }"
          aria-hidden="true"
        ></span>
        <button
          type="button"
          class="ptt"
          :class="{ live: listening, busy: busy && !listening }"
          :disabled="pttHoldDisabled"
          :title="pttTitle"
          @mousedown.prevent="pttStart"
          @mouseup="pttStop"
          @mouseleave="pttStop"
          @touchstart.prevent="pttStart"
          @touchend.prevent="pttStop"
          @touchcancel="pttStop"
          @keydown.space.prevent="pttStart"
          @keyup.space.prevent="pttStop"
          @blur="pttStop"
        >
          <span>{{ listening ? "松开" : busy ? "打断" : "按住" }}</span>
          <span>{{ listening ? "结束" : "说话" }}</span>
        </button>
      </div>

      <p class="hint">{{ listening ? "正在听 · 松开发送" : pttHint }}</p>
      <p v-if="micTone === 'warn'" class="mic-note" data-tone="warn">
        {{ micNotice }}
      </p>
    </footer>

    <transition name="fade">
      <div v-if="showSettings" class="scrim" @click="showSettings = false"></div>
    </transition>

    <transition name="slide">
      <aside
        v-if="showSettings"
        class="sheet"
        role="dialog"
        aria-modal="true"
        aria-label="声音与人格设置"
      >
        <header class="sheet-head">
          <div>
            <p class="eyebrow">设置</p>
            <h2>声音与人格</h2>
          </div>
          <button
            type="button"
            class="icon"
            aria-label="关闭设置"
            @click="showSettings = false"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.7"
              stroke-linecap="round"
              aria-hidden="true"
            >
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
        </header>

        <p v-if="profileStatus" class="sheet-status">{{ profileStatus }}</p>

        <section class="block">
          <h3>人设</h3>
          <label class="field">
            <span>名字</span>
            <input
              v-model="personaDraft.name"
              type="text"
              maxlength="50"
              placeholder="Echoes"
            />
          </label>
          <label class="field">
            <span>系统提示词</span>
            <textarea
              v-model="personaDraft.systemPrompt"
              rows="5"
              maxlength="4000"
              placeholder="她是谁、怎么说话、记得什么…"
            ></textarea>
          </label>
          <button type="button" class="primary" @click="savePersona">
            保存人设
          </button>
        </section>

        <section class="block">
          <h3>引擎</h3>
          <label class="field">
            <span>LLM 后端</span>
            <select v-model="settingsDraft.provider" @change="onProviderChange">
              <option value="ollama">本地 Ollama</option>
              <option value="openai">云端 / 兼容端点（API key）</option>
              <option value="mock">无模型（仅测试）</option>
            </select>
          </label>
          <div class="two">
            <label class="field">
              <span>模型</span>
              <input
                v-model="settingsDraft.model"
                type="text"
                maxlength="100"
                placeholder="qwen3:8b / deepseek-chat"
              />
            </label>
            <label v-if="settingsDraft.provider === 'openai'" class="field">
              <span>Base URL</span>
              <input
                v-model="settingsDraft.baseUrl"
                type="text"
                maxlength="300"
                placeholder="https://api.deepseek.com/v1"
              />
            </label>
          </div>

          <template v-if="settingsDraft.provider === 'openai'">
            <div class="field">
              <span>API key</span>
              <div class="key-row">
                <input
                  v-model="llmKeyDraft"
                  type="password"
                  autocomplete="off"
                  :placeholder="
                    settingsDraft.hasKey ? '已保存（留空则不修改）' : 'sk-…'
                  "
                />
                <button
                  type="button"
                  class="ghost"
                  :disabled="llmKeyDraft.trim() === ''"
                  @click="saveKey"
                >
                  保存
                </button>
                <button
                  type="button"
                  class="quiet"
                  :disabled="!settingsDraft.hasKey"
                  @click="clearKey"
                >
                  清除
                </button>
              </div>
            </div>
            <p v-if="keyStatus" class="note">{{ keyStatus }}</p>
            <p class="note">
              key 存 Windows 凭据管理器，不进数据库、不回显；Base URL 填到
              <code>/v1</code> 为止。
            </p>
          </template>

          <label class="check">
            <input v-model="settingsDraft.privacyMode" type="checkbox" />
            <span>隐私模式：禁止任何云端出网</span>
          </label>
          <p
            v-if="settingsDraft.provider === 'openai' && settingsDraft.privacyMode"
            class="note"
            data-tone="warn"
          >
            云端 LLM 与隐私模式互斥：保存前请关闭隐私模式。
          </p>
          <p class="note">保存后下一轮生效；人设会覆盖默认人设。</p>
          <button type="button" class="primary" @click="saveSettings">
            保存设置
          </button>
        </section>

        <section class="block">
          <div class="block-head">
            <h3>音色</h3>
            <button type="button" class="quiet" @click="loadVoices">刷新</button>
          </div>
          <p v-if="voicesStatus" class="sheet-status">{{ voicesStatus }}</p>
          <ul class="voices">
            <li v-for="voice in voices" :key="voice.id">
              <label class="voice" :class="{ on: voice.selected }">
                <input
                  type="radio"
                  name="voice"
                  :checked="voice.selected"
                  :disabled="voice.status !== 'ready' || busy || clonePhase !== null"
                  @change="chooseVoice(voice.id)"
                />
                <span class="voice-name">{{ voice.displayName }}</span>
                <span class="voice-meta">{{ voiceLabel(voice) }}</span>
              </label>
            </li>
            <li v-if="voices.length === 0" class="note">还没有可用音色。</li>
          </ul>
          <button
            type="button"
            class="record"
            :class="{ live: listening && captureMode === 'clone' }"
            :disabled="cloneHoldDisabled"
            @mousedown.prevent="cloneStart"
            @mouseup="cloneStop"
            @mouseleave="cloneStop"
            @touchstart.prevent="cloneStart"
            @touchend.prevent="cloneStop"
            @touchcancel="cloneStop"
            @keydown.space.prevent="cloneStart"
            @keyup.space.prevent="cloneStop"
            @blur="cloneStop"
          >
            {{
              listening && captureMode === "clone"
                ? `录音中 ${cloneSeconds}s · 松开发送`
                : hasClonedVoice
                  ? "重新克隆我的音色（按住 3–6 秒）"
                  : "克隆我的音色（按住 3–6 秒）"
            }}
          </button>
          <p v-if="cloneError" class="strip-error">{{ cloneError }}</p>
          <p class="note">
            用本机麦克风录 3–6 秒；样本与音色只留在本机，低于相似度阈值会被拒绝。
          </p>
        </section>

        <section class="block">
          <h3>设备</h3>
          <button type="button" class="ghost" @click="micProbe">麦克风自检</button>
          <p v-if="micNotice" class="note" :data-tone="micTone">{{ micNotice }}</p>
          <button type="button" class="quiet" @click="rerunSetup">重新运行首启向导</button>
        </section>
      </aside>
    </transition>
  </div>
</template>

<style>
*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  color-scheme: light;
  --paper: #f6f1e8;
  --paper-hi: #fbf8f1;
  --paper-lo: #efe7da;
  --ink: #23201b;
  --ink-2: #5c554a;
  --ink-3: #746c60;
  --rule: #e3d9c8;
  --rule-strong: #cfc1a9;
  --accent: #95512f;
  --accent-soft: rgba(149, 81, 47, 0.1);
  --danger: #9e3b2e;
  --ok: #5a6e52;
  --font-ui:
    "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system,
    "Microsoft YaHei UI", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  --font-voice:
    "Iowan Old Style", "Palatino Linotype", "Source Han Serif SC",
    "Noto Serif CJK SC", "Songti SC", "SimSun", Georgia, serif;
  --font-mono: "Cascadia Mono", Consolas, ui-monospace, "SF Mono", monospace;
}

html,
body,
#app {
  height: 100%;
}

body {
  font-family: var(--font-ui);
  font-size: 14px;
  line-height: 1.5;
  color: var(--ink);
  background: var(--paper);
  overflow: hidden;
  -webkit-font-smoothing: antialiased;
}

button,
input,
textarea,
select {
  font: inherit;
  color: inherit;
}

button {
  background: none;
  border: none;
  cursor: pointer;
}

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 3px;
}

.app {
  height: 100%;
  display: flex;
  flex-direction: column;
  max-width: 680px;
  margin: 0 auto;
  border-left: 1px solid var(--rule);
  border-right: 1px solid var(--rule);
  background: radial-gradient(
    120% 80% at 50% 0%,
    var(--paper-hi) 0%,
    var(--paper) 62%
  );
}

/* ---- 信笺页眉 ---- */
.letterhead {
  flex: none;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 26px 14px;
  border-bottom: 1px solid var(--rule);
}

.wordmark {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  color: var(--ink-3);
}

.lh-name {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-top: 4px;
}

.name {
  font-family: var(--font-voice);
  font-size: 23px;
  font-weight: 400;
  line-height: 1.2;
  letter-spacing: 0.01em;
}

.state {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-3);
}

.state[data-tone="ready"] {
  color: var(--ok);
}

.state[data-tone="active"] {
  color: var(--accent);
}

.state[data-tone="error"] {
  color: var(--danger);
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex: none;
}

.state[data-tone="active"] .dot {
  animation: pulse 1.8s ease-in-out infinite;
}

.lh-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-top: 2px;
}

.chip {
  max-width: 168px;
  padding: 5px 11px;
  border: 1px solid var(--rule);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.5);
  font-size: 12px;
  color: var(--ink-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition:
    border-color 0.18s ease,
    color 0.18s ease;
}

.chip:hover {
  border-color: var(--rule-strong);
  color: var(--ink);
}

.icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  color: var(--ink-2);
  transition:
    background 0.18s ease,
    color 0.18s ease;
}

.icon:hover {
  background: var(--paper-lo);
  color: var(--ink);
}

.quiet {
  padding: 4px 7px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--ink-3);
  transition:
    color 0.18s ease,
    background 0.18s ease;
}

.quiet:hover {
  color: var(--accent);
  background: var(--accent-soft);
}

/* ---- 信纸正文 ---- */
.thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding: 26px 26px 10px;
}

.thread::-webkit-scrollbar {
  width: 8px;
}

.thread::-webkit-scrollbar-thumb {
  background: var(--rule);
  border-radius: 4px;
}

.thread::-webkit-scrollbar-thumb:hover {
  background: var(--rule-strong);
}

.empty {
  margin: auto 0;
}

.empty-title {
  font-family: var(--font-voice);
  font-size: 19px;
  color: var(--ink-2);
}

.empty-sub {
  margin-top: 6px;
  max-width: 26em;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-3);
}

.msg {
  display: flex;
  flex-direction: column;
}

.said {
  padding-left: 14px;
  border-left: 1px solid var(--rule-strong);
  font-family: var(--font-voice);
  font-size: 16.5px;
  line-height: 1.85;
  color: var(--ink);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.msg.user {
  align-self: flex-end;
  max-width: 78%;
}

.mine {
  padding: 8px 12px;
  border: 1px solid var(--rule);
  border-radius: 12px 12px 3px 12px;
  background: var(--paper-lo);
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink-2);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.cut {
  margin-top: 6px;
  padding-left: 14px;
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.1em;
  color: var(--ink-3);
}

.caret {
  display: inline-block;
  width: 1px;
  height: 1.05em;
  margin-left: 2px;
  vertical-align: -0.15em;
  background: var(--accent);
  animation: blink 1s steps(2, start) infinite;
}

.notice-row {
  padding: 8px 12px;
  border-left: 2px solid var(--danger);
  border-radius: 0 8px 8px 0;
  background: rgba(158, 59, 46, 0.05);
}

.notice {
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--danger);
  overflow-wrap: anywhere;
}

/* ---- 克隆进度（跨抽屉常驻） ---- */
.clone-strip {
  flex: none;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 8px 26px;
  border-top: 1px solid var(--rule);
  font-size: 12px;
  color: var(--ink-2);
}

.strip-label {
  color: var(--accent);
}

.meter {
  flex: 1;
  min-width: 80px;
  height: 3px;
  border-radius: 2px;
  background: var(--paper-lo);
  overflow: hidden;
}

.meter-fill {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 0.3s ease;
}

.strip-pct {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-3);
}

.strip-error {
  flex-basis: 100%;
  font-size: 12px;
  line-height: 1.6;
  color: var(--danger);
  overflow-wrap: anywhere;
}

/* ---- 落款与说话钮 ---- */
.composer {
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 14px 26px 18px;
  border-top: 1px solid var(--rule);
  background: linear-gradient(var(--paper-hi), var(--paper));
}

.write {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 5px;
  border-bottom: 1px solid var(--rule-strong);
  transition: border-color 0.18s ease;
}

.write:focus-within {
  border-bottom-color: var(--accent);
}

.write input {
  flex: 1;
  min-width: 0;
  padding: 4px 0;
  border: none;
  background: none;
  font-size: 14px;
}

.write input:focus {
  outline: none;
}

.write input::placeholder {
  color: var(--ink-3);
}

.send {
  flex: none;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--accent);
  transition:
    background 0.18s ease,
    opacity 0.18s ease;
}

.send:hover:not(:disabled) {
  background: var(--accent-soft);
}

.send:disabled {
  color: var(--ink-3);
  opacity: 0.55;
  cursor: default;
}

.speak {
  position: relative;
  display: grid;
  place-items: center;
  width: 108px;
  height: 108px;
  margin-top: 2px;
}

.ring {
  position: absolute;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  border: 1px solid var(--rule);
  pointer-events: none;
}

.ring.live {
  border-color: transparent;
  border-top-color: var(--accent);
  border-right-color: rgba(149, 81, 47, 0.3);
  box-shadow: 0 0 0 8px rgba(149, 81, 47, 0.05);
  animation: sweep 2.4s linear infinite;
}

.ring.busy {
  animation: breathe 3.2s ease-in-out infinite;
}

.ptt {
  position: relative;
  z-index: 1;
  display: grid;
  place-content: center;
  gap: 1px;
  width: 84px;
  height: 84px;
  border: 1px solid var(--rule-strong);
  border-radius: 50%;
  background: var(--paper-hi);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 6px 16px rgba(35, 32, 27, 0.06);
  font-family: var(--font-voice);
  font-size: 15px;
  line-height: 1.25;
  letter-spacing: 0.08em;
  color: var(--ink);
  user-select: none;
  -webkit-user-select: none;
  touch-action: none;
  transition:
    transform 0.15s ease,
    background 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease,
    box-shadow 0.2s ease;
}

.ptt:hover:not(:disabled) {
  border-color: var(--accent);
}

.ptt:active:not(:disabled) {
  transform: scale(0.975);
}

.ptt.busy {
  font-size: 14px;
}

.ptt.live {
  border-color: var(--accent);
  background: var(--accent);
  color: var(--paper-hi);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.18),
    0 8px 22px rgba(149, 81, 47, 0.28);
}

.ptt:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.hint {
  min-height: 16px;
  font-size: 12px;
  color: var(--ink-3);
  text-align: center;
}

.mic-note {
  max-width: 100%;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--ink-3);
  text-align: center;
  overflow-wrap: anywhere;
}

.mic-note[data-tone="warn"] {
  color: var(--danger);
}

/* ---- 右侧抽屉 ---- */
.scrim {
  position: fixed;
  inset: 0;
  z-index: 20;
  background: rgba(35, 32, 27, 0.18);
}

.sheet {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  z-index: 21;
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: min(400px, 92vw);
  padding: 18px 20px 28px;
  overflow-y: auto;
  background: var(--paper-hi);
  border-left: 1px solid var(--rule-strong);
  box-shadow: -12px 0 32px rgba(35, 32, 27, 0.08);
}

.sheet::-webkit-scrollbar {
  width: 8px;
}

.sheet::-webkit-scrollbar-thumb {
  background: var(--rule);
  border-radius: 4px;
}

.sheet-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.eyebrow {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--ink-3);
}

.sheet h2 {
  margin-top: 2px;
  font-family: var(--font-voice);
  font-size: 21px;
  font-weight: 400;
}

.block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 16px;
  border-top: 1px solid var(--rule);
}

.block h3 {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--ink-2);
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
  color: var(--ink-2);
}

.field input,
.field textarea,
.field select {
  padding: 8px 10px;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: #fffdf9;
  font-size: 13.5px;
  color: var(--ink);
  transition:
    border-color 0.16s ease,
    box-shadow 0.16s ease;
}

.field input:focus,
.field textarea:focus,
.field select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.field textarea {
  min-height: 84px;
  line-height: 1.6;
  resize: vertical;
}

.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--ink-2);
  cursor: pointer;
}

.check input {
  width: 14px;
  height: 14px;
  accent-color: var(--accent);
}

.key-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.key-row input {
  flex: 1;
  min-width: 0;
}

.ghost:disabled,
.quiet:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

code {
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--paper-lo);
  font-family: var(--font-mono);
  font-size: 0.92em;
}

.note {
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--ink-3);
}

.note[data-tone="warn"] {
  color: var(--danger);
}

.sheet-status {
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--accent);
}

.primary {
  align-self: flex-start;
  padding: 8px 16px;
  border-radius: 8px;
  background: var(--ink);
  color: var(--paper-hi);
  font-size: 12.5px;
  letter-spacing: 0.04em;
  transition:
    background 0.18s ease,
    transform 0.15s ease;
}

.primary:hover {
  background: var(--accent);
}

.primary:active {
  transform: translateY(1px);
}

.ghost {
  align-self: flex-start;
  padding: 7px 12px;
  border: 1px solid var(--rule-strong);
  border-radius: 8px;
  font-size: 12.5px;
  color: var(--ink-2);
  transition:
    border-color 0.16s ease,
    color 0.16s ease;
}

.ghost:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.voices {
  display: flex;
  flex-direction: column;
  gap: 6px;
  list-style: none;
}

.voice {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  border: 1px solid var(--rule);
  border-radius: 9px;
  font-size: 13px;
  cursor: pointer;
  transition:
    border-color 0.16s ease,
    background 0.16s ease;
}

.voice:hover {
  border-color: var(--rule-strong);
  background: #fffdf9;
}

.voice.on {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.voice input {
  accent-color: var(--accent);
}

.voice-name {
  color: var(--ink);
}

.voice-meta {
  margin-left: auto;
  font-size: 11px;
  color: var(--ink-3);
}

.record {
  padding: 9px 12px;
  border: 1px dashed var(--rule-strong);
  border-radius: 9px;
  font-size: 12.5px;
  color: var(--ink-2);
  text-align: center;
  transition:
    border-color 0.16s ease,
    background 0.16s ease,
    color 0.16s ease;
}

.record:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.record.live {
  border-style: solid;
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
}

.record:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ---- 过渡与动效 ---- */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: transform 0.24s cubic-bezier(0.22, 0.61, 0.36, 1);
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

@keyframes pulse {
  50% {
    opacity: 0.35;
  }
}

@keyframes sweep {
  to {
    transform: rotate(360deg);
  }
}

@keyframes breathe {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(149, 81, 47, 0.12);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(149, 81, 47, 0);
  }
}

/* ---- 窄窗与矮窗 ---- */
@media (max-width: 700px) {
  .app {
    border: none;
  }

  .letterhead,
  .thread,
  .composer {
    padding-left: 18px;
    padding-right: 18px;
  }

  .clone-strip {
    padding-left: 18px;
    padding-right: 18px;
  }

  .name {
    font-size: 20px;
  }

  .chip {
    max-width: 96px;
  }
}

@media (max-height: 620px) {
  .letterhead {
    padding-top: 12px;
    padding-bottom: 10px;
  }

  .thread {
    padding-top: 16px;
    gap: 16px;
  }

  .speak {
    width: 92px;
    height: 92px;
  }

  .ring {
    width: 86px;
    height: 86px;
  }

  .ptt {
    width: 72px;
    height: 72px;
    font-size: 13.5px;
  }

  .composer {
    gap: 6px;
    padding-top: 10px;
    padding-bottom: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
</style>
