<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import type { UnlistenFn } from "@tauri-apps/api/event";

import * as ipc from "./lib/ipc";
import type { SidecarMessage } from "./lib/ipc";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  /** 被打断的 assistant 气泡（3.4 三跳：turn_complete(status=CANCELLED)） */
  interrupted?: boolean;
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
});
const profileStatus = ref("");
let profileRetry: number | null = null;
let profileAttempts = 0;

async function loadProfile(): Promise<void> {
  try {
    const [persona, settings] = await Promise.all([
      ipc.getPersona(),
      ipc.getSettings(),
    ]);
    personaDraft.value = persona;
    settingsDraft.value = settings;
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

function protocolDown(code: string, message: string): void {
  engineState.value = "error";
  messages.value.push({ role: "assistant", text: `⚠ ${code}：${message}` });
}

onMounted(async () => {
  unlisten = await ipc.onSidecarEvent(handleFrame, (failure) => {
    protocolDown(failure.code, failure.message);
  });
  void loadProfile();
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
      }
      break;
    case "error":
      messages.value.push({
        role: "assistant",
        text: `⚠ ${frame.code}：${frame.message}`,
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

function onWindowBlur(): void {
  void stopCapture();
}

onMounted(() => {
  window.addEventListener("blur", onWindowBlur);
});

onUnmounted(() => {
  window.removeEventListener("blur", onWindowBlur);
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
  busy.value = true;
  try {
    await ipc.sendUserText(text);
  } catch (err) {
    messages.value.push({ role: "assistant", text: `⚠ 发送失败：${String(err)}` });
    streaming.value = false;
    busy.value = false;
  }
}
</script>

<template>
  <main class="chat">
    <header>
      <h1>Echoes</h1>
      <span class="status">sidecar 状态：{{ engineState }}</span>
      <button class="settings-open" @click="showSettings = true">设置</button>
    </header>

    <ul class="history">
      <li v-for="(m, i) in messages" :key="i" :class="m.role">
        <span v-if="m.text !== ''" class="bubble">{{ m.text }}</span>
        <span v-if="m.interrupted" class="cut">已打断</span>
      </li>
      <li v-if="messages.length === 0" class="empty">和 Echoes 说点什么…</li>
    </ul>

    <section v-if="clonePhase !== null || cloneError" class="clone-panel">
      <div v-if="clonePhase" class="clone-line">
        <span class="clone-label">{{ clonePhaseLabel }}</span>
        <progress :value="clonePct" max="100"></progress>
        <span class="pct">{{ clonePct }}%</span>
        <button class="link" @click="cancelClone">取消</button>
      </div>
      <p v-if="cloneError" class="clone-error">⚠ {{ cloneError }}</p>
    </section>

    <footer>
      <input v-model="input" type="text" placeholder="输入消息…" @keyup.enter="send" />
      <button @click="send">发送</button>
      <button v-if="busy" class="stop" title="停止本次回复" @click="stopTurn">停止</button>
      <button
        class="ptt"
        :class="{ recording: listening }"
        :disabled="!pttEnabled"
        :title="
          !asrReady
            ? 'ASR 就绪后可用'
            : busy
              ? '按住说话（会打断当前回复）'
              : '按住说话（松开结束）'
        "
        @mousedown.prevent="pttStart"
        @mouseup="pttStop"
        @mouseleave="pttStop"
        @touchstart.prevent="pttStart"
        @touchend.prevent="pttStop"
        @touchcancel="pttStop"
      >
        {{ listening ? "松开结束" : busy ? "打断并说话" : "按住说话" }}
      </button>
      <button
        class="clone"
        :class="{ recording: listening && captureMode === 'clone' }"
        :disabled="!cloneEnabled"
        :title="
          hasClonedVoice
            ? '重新克隆音色（按住 3–6 秒）'
            : '按住 3–6 秒说话，克隆你的声音'
        "
        @mousedown.prevent="cloneStart"
        @mouseup="cloneStop"
        @mouseleave="cloneStop"
        @touchstart.prevent="cloneStart"
        @touchend.prevent="cloneStop"
        @touchcancel="cloneStop"
      >
        {{
          listening && captureMode === "clone"
            ? `录音中 ${cloneSeconds}s`
            : hasClonedVoice
              ? "重克隆"
              : "克隆音色"
        }}
      </button>
      <button class="mic" @click="micProbe">{{ micStatus || "麦克风自检" }}</button>
    </footer>

    <div
      v-if="showSettings"
      class="settings-overlay"
      @click.self="showSettings = false"
    >
      <section class="settings-panel">
        <div class="settings-head">
          <h2>人设与设置</h2>
          <button class="link" @click="showSettings = false">关闭</button>
        </div>
        <p v-if="profileStatus" class="settings-status">{{ profileStatus }}</p>

        <label>
          人设名字
          <input v-model="personaDraft.name" type="text" maxlength="50" />
        </label>
        <label>
          人设提示词
          <textarea
            v-model="personaDraft.systemPrompt"
            rows="6"
            maxlength="4000"
          ></textarea>
        </label>
        <button @click="savePersona">保存人设</button>

        <hr />

        <label>
          Provider
          <select v-model="settingsDraft.provider">
            <option value="ollama">Ollama（本地）</option>
            <option value="mock">Mock（无模型）</option>
          </select>
        </label>
        <label>
          模型
          <input v-model="settingsDraft.model" type="text" maxlength="100" />
        </label>
        <label class="check">
          <input v-model="settingsDraft.privacyMode" type="checkbox" />
          隐私模式（本地 provider 始终不出网）
        </label>
        <p class="hint">
          当前仅本地 provider，无需 API key。保存后在下一轮对话生效；人设覆盖默认人设。
        </p>
        <button @click="saveSettings">保存设置</button>
      </section>
    </div>
  </main>
</template>

<style>
* {
  margin: 0;
  box-sizing: border-box;
}
body {
  font-family: system-ui, "Microsoft YaHei", sans-serif;
  background: #141218;
  color: #e6e1e5;
  height: 100vh;
}
.chat {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 640px;
  margin: 0 auto;
  padding: 16px;
}
header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #2b2831;
}
h1 {
  font-size: 20px;
}
.status {
  font-size: 12px;
  color: #8a8494;
}
.history {
  flex: 1;
  overflow-y: auto;
  list-style: none;
  padding: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.history .user {
  align-self: flex-end;
}
.bubble {
  display: inline-block;
  max-width: 80%;
  padding: 8px 12px;
  border-radius: 12px;
  background: #26232a;
  line-height: 1.5;
  white-space: pre-wrap;
}
.user .bubble {
  background: #4a4458;
}
.cut {
  margin-left: 6px;
  font-size: 11px;
  color: #8a8494;
}
.empty {
  color: #6f6a7a;
  font-size: 13px;
}
footer {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #2b2831;
}
footer input {
  flex: 1;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #343038;
  background: #1c1921;
  color: inherit;
}
footer button {
  padding: 10px 16px;
  border-radius: 10px;
  border: none;
  background: #6750a4;
  color: white;
  cursor: pointer;
}
footer button:disabled {
  opacity: 0.4;
}
footer .ptt,
footer .clone,
footer .mic,
footer .stop {
  background: #36343b;
}
footer .clone.recording {
  background: #b3261e;
}
.clone-panel {
  padding: 8px 0;
  border-top: 1px solid #2b2831;
}
.clone-line {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #b9b2c4;
}
.clone-line progress {
  flex: 1;
  height: 6px;
  accent-color: #6750a4;
}
.clone-label {
  min-width: 44px;
}
.clone-line .link {
  border: none;
  background: transparent;
  color: #a79ab8;
  cursor: pointer;
  font-size: 12px;
  text-decoration: underline;
  padding: 0;
}
.clone-error {
  margin-top: 6px;
  font-size: 12px;
  color: #f2b8b5;
  line-height: 1.4;
}
footer .ptt.recording {
  background: #b3261e;
}
footer .mic {
  font-size: 12px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 人设卡 / Settings（3.4 拉取语义：保存后下一轮生效） */
.settings-open {
  margin-left: auto;
  padding: 6px 12px;
  border: none;
  border-radius: 8px;
  background: #36343b;
  color: inherit;
  font-size: 12px;
  cursor: pointer;
}
.settings-overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
}
.settings-panel {
  width: min(520px, 92vw);
  max-height: 86vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;
  border: 1px solid #343038;
  border-radius: 14px;
  background: #1e1b23;
}
.settings-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.settings-head h2 {
  font-size: 16px;
}
.settings-panel label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #b9b2c4;
}
.settings-panel label.check {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
.settings-panel input[type="text"],
.settings-panel textarea,
.settings-panel select {
  padding: 8px 10px;
  border: 1px solid #343038;
  border-radius: 8px;
  background: #141218;
  color: inherit;
  font: inherit;
}
.settings-panel textarea {
  resize: vertical;
  line-height: 1.5;
}
.settings-panel button {
  align-self: flex-start;
  padding: 8px 14px;
  border: none;
  border-radius: 8px;
  background: #6750a4;
  color: white;
  cursor: pointer;
}
.settings-panel button.link {
  padding: 0;
  background: transparent;
  color: #a79ab8;
  text-decoration: underline;
}
.settings-panel hr {
  width: 100%;
  border: none;
  border-top: 1px solid #2b2831;
}
.settings-status,
.settings-panel .hint {
  font-size: 12px;
  color: #8a8494;
  line-height: 1.5;
}
</style>
