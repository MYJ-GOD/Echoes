<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

// 壳事件侧车帧（结对 sidecar.rs 的 ShellEvent；未知 kind 忽略 —— 3.4 兼容规则）
type ShellEventPayload =
  | { kind: "sidecar"; event: SidecarFrame }
  | { kind: "protocol"; code: string; message: string; fatal: boolean };

type SidecarFrame =
  | {
      type: "hello";
      sidecar_version: string;
      protocol_version: string;
      engines?: { name: string; ready: boolean }[];
    }
  | { type: "state"; state: string }
  | { type: "asr_final"; session_id: string; text: string; is_final: boolean }
  | { type: "assistant_text"; session_id: string; text: string }
  | { type: "turn_complete"; session_id: string; turn_seq: number; status: string }
  | { type: "error"; session_id: string | null; code: string; message: string };

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

function protocolDown(code: string, message: string): void {
  engineState.value = "error";
  messages.value.push({ role: "assistant", text: `⚠ ${code}：${message}` });
}

onMounted(async () => {
  unlisten = await listen<ShellEventPayload>("sidecar://event", (e) => {
    const payload = e.payload;
    if (payload.kind === "protocol") {
      protocolDown(payload.code, payload.message);
      return;
    }
    handleFrame(payload.event);
  });
});

onUnmounted(() => {
  unlisten?.();
});

function handleFrame(frame: SidecarFrame): void {
  switch (frame.type) {
    case "hello":
      asrReady.value =
        frame.engines?.some((e) => e.name === "asr" && e.ready) ?? false;
      break;
    case "state":
      engineState.value = String(frame.state);
      break;
    case "asr_final":
      // 语音面输入：sidecar 随后立即进入 turn（asr_final 与 user_text 等价）。
      messages.value.push({ role: "user", text: String(frame.text) });
      busy.value = true;
      micStatus.value = "麦克风就绪";
      break;
    case "assistant_text": {
      const text = String(frame.text);
      const last = messages.value[messages.value.length - 1];
      if (streaming.value && last?.role === "assistant") {
        last.text = text; // text=截至当前全量，直接替换
      } else {
        messages.value.push({ role: "assistant", text });
        streaming.value = true;
      }
      break;
    }
    case "turn_complete":
      streaming.value = false;
      busy.value = false;
      break;
    case "error":
      messages.value.push({
        role: "assistant",
        text: `⚠ ${frame.code}：${frame.message}`,
      });
      streaming.value = false;
      busy.value = false;
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
const pttHeld = ref(false);
const listening = ref(false);
const pttEnabled = computed(
  () => !busy.value && engineState.value === "ready" && asrReady.value,
);

let micStream: MediaStream | null = null;
let micCtx: AudioContext | null = null;
let micSource: MediaStreamAudioSourceNode | null = null;
let micProcessor: ScriptProcessorNode | null = null;
let micMute: GainNode | null = null;
let pendingSamples: number[] = [];
// 串行化分片上行：Tauri IPC 保序，但 Promise 链保证「尾片 → is_final」严格在后。
let sendChain: Promise<unknown> = Promise.resolve();

function enqueueChunk(samples: number[]): void {
  sendChain = sendChain
    .then(() => invoke("ptt_push", { samples }))
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

async function pttStart(): Promise<void> {
  if (!pttEnabled.value || pttHeld.value) return;
  pttHeld.value = true;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    if (!pttHeld.value) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    // 先 flush 在途播放（打断首跳）并复位重采样器，再开始送分片。
    await invoke("ptt_start");
    if (!pttHeld.value) {
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
    micStatus.value = "🎙 录音中…";
  } catch (err) {
    pttHeld.value = false;
    cleanupMic();
    micStatus.value = `⚠ ${micErrorMessage(err)}`;
  }
}

async function pttStop(): Promise<void> {
  if (!pttHeld.value) return;
  pttHeld.value = false;
  if (!micStream) return; // getUserMedia 尚未返回：pttStart 会自行清理
  const rest = pendingSamples;
  pendingSamples = [];
  cleanupMic();
  try {
    await sendChain;
    if (rest.length > 0) {
      await invoke("ptt_push", { samples: rest });
    }
    await invoke("ptt_stop");
    micStatus.value = "识别中…";
  } catch (err) {
    micStatus.value = `⚠ ${String(err)}`;
  }
}

function onWindowBlur(): void {
  void pttStop();
}

onMounted(() => {
  window.addEventListener("blur", onWindowBlur);
});

onUnmounted(() => {
  window.removeEventListener("blur", onWindowBlur);
  pttHeld.value = false;
  cleanupMic();
});

async function send(): Promise<void> {
  const text = input.value.trim();
  if (!text || busy.value) return;
  messages.value.push({ role: "user", text });
  input.value = "";
  busy.value = true;
  try {
    await invoke("send_user_text", { text });
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
    </header>

    <ul class="history">
      <li v-for="(m, i) in messages" :key="i" :class="m.role">
        <span v-if="m.text !== ''" class="bubble">{{ m.text }}</span>
      </li>
      <li v-if="messages.length === 0" class="empty">和 Echoes 说点什么…</li>
    </ul>

    <footer>
      <input v-model="input" type="text" placeholder="输入消息…" @keyup.enter="send" />
      <button :disabled="busy" @click="send">发送</button>
      <button
        class="ptt"
        :class="{ recording: listening }"
        :disabled="!pttEnabled"
        :title="asrReady ? '按住说话（松开结束）' : 'ASR 就绪后可用'"
        @mousedown.prevent="pttStart"
        @mouseup="pttStop"
        @mouseleave="pttStop"
        @touchstart.prevent="pttStart"
        @touchend.prevent="pttStop"
        @touchcancel="pttStop"
      >
        {{ listening ? "松开结束" : "按住说话" }}
      </button>
      <button class="mic" @click="micProbe">{{ micStatus || "麦克风自检" }}</button>
    </footer>
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
footer .mic {
  background: #36343b;
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
</style>
