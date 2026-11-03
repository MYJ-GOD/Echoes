<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import type { UnlistenFn } from "@tauri-apps/api/event";

import * as ipc from "../lib/ipc";
import type { SidecarMessage } from "../lib/ipc";
import FirstRun from "../FirstRun.vue";
import { useRecovery } from "../composables/useRecovery";
import { historyTurnRows, useHistory } from "../composables/useHistory";
import { useSettings } from "../composables/useSettings";
import { useAudioDevices } from "../composables/useAudioDevices";
import ChatComposer from "../components/chat/ChatComposer.vue";
import ChatHeader from "../components/chat/ChatHeader.vue";
import MessageItem from "../components/chat/MessageItem.vue";
import DsButton from "../components/ui/DsButton.vue";
import DsChip from "../components/ui/DsChip.vue";
import DsEmptyState from "../components/ui/DsEmptyState.vue";
import type { ChatMessage } from "../components/chat/types";

const props = withDefaults(
  defineProps<{
    /** D2：挂在 AppShell 里时隐藏品牌词、放宽内容列，不再自己画窗口壳。 */
    embedded?: boolean;
  }>(),
  { embedded: false },
);

// ---- 外观主题（纯展示偏好：localStorage，不进 sidecar 契约） ----
type ThemeId = "paper" | "nocturne";
/** 「跟随系统」按 prefers-color-scheme 在浅色/深色之间切 */
type ThemeChoice = ThemeId | "system";
const THEME_KEY = "echoes.theme";
const darkQuery =
  typeof window !== "undefined" && "matchMedia" in window
    ? window.matchMedia("(prefers-color-scheme: dark)")
    : null;

function readStoredTheme(): ThemeChoice {
  try {
    const raw = localStorage.getItem(THEME_KEY);
    if (raw === "system" || raw === "paper" || raw === "nocturne") {
      return raw;
    }
  } catch {
    // 隐私模式/存储被禁：按默认主题走
  }
  return "paper";
}

/** 选择 → 实际主题 id（system 时看系统暗色偏好）。 */
function resolveTheme(choice: ThemeChoice): ThemeId {
  if (choice !== "system") return choice;
  return darkQuery?.matches ? "nocturne" : "paper";
}

function applyTheme(): void {
  document.documentElement.dataset.theme = resolveTheme(readStoredTheme());
}

// 侧车帧类型来自 `lib/ipc_types.ts`（由 sidecar 的 pydantic 模型生成，13.2-1）：
// 协议改名会在这里编译期报错，而不是运行时静默失败。

// 阶段 0 第一周：文本→LLM→文本 经 StdioTransport 打通；
// 麦克风（PTT）与音频播放为壳侧采集验证（风险 10），后续接入。
const messages = ref<ChatMessage[]>([]);

/** 进对话的消息统一从这里入列：集中补时间戳（台面主题要显示 22:41）。 */
function pushMessage(msg: Omit<ChatMessage, "at">): void {
  messages.value.push({ ...msg, at: Date.now() });
}

/** R4 4.4/4.5：定位最后一条用户消息（重说/编辑的锚点）。 */
const lastUserIndex = computed(() => {
  for (let index = messages.value.length - 1; index >= 0; index--) {
    const message = messages.value[index];
    if (message.role === "user" && message.kind !== "error") return index;
  }
  return -1;
});

const canRetry = computed(
  () => !busy.value && !firstRun.value && lastUserIndex.value >= 0,
);

/** 重跑前去掉末尾的 assistant 气泡（新回复到达时会重新追加）。 */
function dropTrailingReply(): void {
  while (messages.value.length > 0) {
    const last = messages.value[messages.value.length - 1];
    if (last.role === "assistant" && last.kind !== "error") messages.value.pop();
    else break;
  }
}

/** R4 4.4：重说上一轮（sidecar 复用原文；旧 turn 成功后被取代）。 */
function retryLast(): void {
  if (!canRetry.value) return;
  dropTrailingReply();
  busy.value = true;
  void ipc.retryTurn().catch((err) => {
    busy.value = false;
    pushMessage({
      role: "assistant",
      kind: "error",
      text: `重说失败：${String(err)}`,
    });
  });
}

/** R4 4.5：编辑上一条并重跑（旧版本保留在历史里）。 */
function editLast(): void {
  if (!canRetry.value) return;
  const index = lastUserIndex.value;
  const current = messages.value[index];
  if (!current) return;
  const next = window.prompt("编辑上一条（会重新生成回复）", current.text);
  if (next === null) return;
  const text = next.trim();
  if (!text || text === current.text) return;
  current.text = text;
  dropTrailingReply();
  busy.value = true;
  void ipc.editLastTurn(text).catch((err) => {
    busy.value = false;
    pushMessage({
      role: "assistant",
      kind: "error",
      text: `编辑失败：${String(err)}`,
    });
  });
}

const input = ref("");
const busy = ref(false);
const engineState = ref("connecting");
// hello.engines 分级就绪（3.4 v1.4）：ASR 未就绪前 PTT 不可用。
const asrReady = ref(false);
// assistant 流式气泡边界：true=最后一条 assistant 气泡在途（assistant_text 全量替换渲染），
// 收尾由 turn_complete（或 error）复位 —— v1.4.1 语义。
const streaming = ref(false);
let unlisten: UnlistenFn | null = null;
let unlistenPtt: UnlistenFn | null = null;
let unlistenSettings: UnlistenFn | null = null;
let unlistenTalk: UnlistenFn | null = null;

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
// ---- 人设卡 / Settings（3.4 拉取语义：壳写 SQLite，sidecar 每轮读取） ----
const router = useRouter();

async function openSettings(): Promise<void> {
  try {
    await ipc.openSettingsWindow();
  } catch {
    // 独立窗口建不出来时退回主窗口的整页设置。
    await router.push("/settings");
  }
}

const {
  settingsDraft,
  firstRun,
  companionName,
  selectedVoiceName,
  loadProfile,
  loadVoices,
  noteEngines,
} = useSettings();

// ---- R5 隐私可视化：状态栏常驻标识 + 三链实际去向（不改变任何开关，只念当前配置） ----
function destination(provider: string, baseUrl: string): string {
  if (provider !== "openai") return "本地";
  if (!baseUrl || ipc.isLoopbackBaseUrl(baseUrl)) return "本机";
  try {
    return new URL(baseUrl).host || baseUrl;
  } catch {
    return baseUrl;
  }
}

/** 例：「对话 → 本机 · 识别 → 本地 · 合成 → 本地」 */
const chainSummary = computed(() =>
  [
    `对话 → ${destination(settingsDraft.value.provider, settingsDraft.value.baseUrl)}`,
    `识别 → ${destination(settingsDraft.value.asrProvider, settingsDraft.value.asrBaseUrl)}`,
    `合成 → ${destination(settingsDraft.value.ttsProvider, settingsDraft.value.ttsBaseUrl)}`,
  ].join(" · "),
);

const NOTIFY_KEY = "echoes.notify.reply";

function readNotifyOnReply(): boolean {
  try {
    return localStorage.getItem(NOTIFY_KEY) === "on";
  } catch {
    return false;
  }
}

/** 后台回复完成：只在窗口不可见时提示，内容截断，不写日志。 */
function maybeNotify(): void {
  if (!readNotifyOnReply() || !document.hidden) return;
  const last = messages.value[messages.value.length - 1];
  if (last?.role !== "assistant" || !last.text.trim()) return;
  const body = last.text.trim().replace(/\s+/g, " ").slice(0, 80);
  void ipc.appNotify(companionName.value, body).catch(() => {
    // 通知失败不影响对话（系统可能禁用了通知）
  });
}

// ---- R5 2.8/§2.7：链失败统计 + 一键切换 + 只读模式 ----
type Chain = "llm" | "asr" | "tts";
/** 连续历史写失败（成功写入一次由 sidecar 清零；UI 侧只在用户显式解除时清零） */
const historyFailures = ref(0);
/** 本轮失败的链（成功完成一轮后清空）；三条链都失败 → 只读 */
const failedChains = ref<Chain[]>([]);
const readOnly = computed(
  () => historyFailures.value >= 3 || failedChains.value.length >= 3,
);
const switchStatus = ref("");

/** 错误码 → 链（不解析文案；未知码返回 null，不显示切换按钮）。 */
function chainForCode(code?: string): Chain | null {
  if (!code) return null;
  if (code.startsWith("LLM_")) return "llm";
  if (code.startsWith("ASR_")) return "asr";
  if (code.startsWith("TTS_")) return "tts";
  return null;
}

function chainProvider(chain: Chain): string {
  switch (chain) {
    case "llm":
      return settingsDraft.value.provider;
    case "asr":
      return settingsDraft.value.asrProvider;
    case "tts":
      return settingsDraft.value.ttsProvider;
  }
}

function chainHasKey(chain: Chain): boolean {
  switch (chain) {
    case "llm":
      return settingsDraft.value.hasKey;
    case "asr":
      return settingsDraft.value.hasAsrKey;
    case "tts":
      return settingsDraft.value.hasTtsKey;
  }
}

function chainConsented(chain: Chain): boolean {
  switch (chain) {
    case "llm":
      return settingsDraft.value.llmCloudConsent;
    case "asr":
      return settingsDraft.value.asrCloudConsent;
    case "tts":
      return settingsDraft.value.ttsCloudConsent;
  }
}

/** 按钮文案：当前在云端 → 改用本地；当前本地 → 改用云端（LLM 附带重试）。 */
function switchLabel(chain: Chain | null): string {
  if (chain === null) return "";
  const cloud = chainProvider(chain) === "openai";
  const verb = cloud ? "改用本地" : "改用云端";
  if (chain === "llm") return `${verb}并重试`;
  return `${verb}（需重新说一遍）`;
}

async function switchChain(chain: Chain): Promise<void> {
  switchStatus.value = "";
  const cloud = chainProvider(chain) === "openai";
  if (!cloud && (!chainHasKey(chain) || !chainConsented(chain))) {
    switchStatus.value = "切换到云端需要先在设置里填 Key 并勾选数据出境同意";
    void openSettings();
    return;
  }
  const draft = settingsDraft.value;
  if (chain === "llm") draft.provider = cloud ? "ollama" : "openai";
  if (chain === "asr") draft.asrProvider = cloud ? "whisper" : "openai";
  if (chain === "tts") draft.ttsProvider = cloud ? "cosyvoice2" : "openai";

  try {
    await ipc.saveSettings(draft);
    await loadProfile();
    await loadVoices();
    switchStatus.value = cloud
      ? `${chain === "llm" ? "对话" : chain === "asr" ? "识别" : "合成"}已切到本地`
      : `${chain === "llm" ? "对话" : chain === "asr" ? "识别" : "合成"}已切到云端`;
    failedChains.value = failedChains.value.filter((item) => item !== chain);
    if (chain === "llm") {
      await ipc.retryTurn();
    }
  } catch (err) {
    switchStatus.value = `切换失败：${String(err)}`;
  }
}

/** 用户显式解除只读（磁盘问题没修好时，下一轮会再次报错并重新计数）。 */
function resetReadOnly(): void {
  historyFailures.value = 0;
  failedChains.value = [];
  switchStatus.value = "";
}

/** 模板入口：错误码 → 链 → 切换（无链的码不显示按钮）。 */
function switchChainByCode(code?: string): void {
  const chain = chainForCode(code);
  if (chain) void switchChain(chain);
}

function noticeAction(code?: string): string {
  return switchLabel(chainForCode(code));
}

const PTT_MODE_KEY = "echoes.ptt.mode";
type PttMode = "hold" | "toggle";

function readPttMode(): PttMode {
  try {
    return localStorage.getItem(PTT_MODE_KEY) === "toggle" ? "toggle" : "hold";
  } catch {
    return "hold";
  }
}

/** 1d.2 两模式：按住说话（PTT）/ 按一下切换（托盘与快捷键共用）。 */
const pttMode = ref<PttMode>(readPttMode());

/** 托盘/快捷键的统一入口：在采集就停，否则开始。 */
function toggleTalk(): void {
  if (firstRun.value) return;
  if (captureHeld.value) pttStop();
  else pttStart();
}

/** R5：主窗口回到前台时刷新设置（独立设置窗口保存后同步；无跨窗口事件总线）。 */
function onWindowFocus(): void {
  applyTheme();
  void loadProfile();
  void loadVoices();
}

// ---- R1e 音频设备：只保留播放路径需要的三项，设备选择在设置窗口 ----
const {
  refreshDevices,
  applyOutputDevice,
  applyVolume,
  openMicStream,
} = useAudioDevices();

// ---- R1c 历史 / 会话切换 ----
// R5 长会话：只渲染最近 N 条，往上翻时按批追加（DOM 不随轮次线性膨胀）。
const RENDER_STEP = 80;
const renderLimit = ref(RENDER_STEP);
const visibleMessages = computed(() =>
  messages.value.length <= renderLimit.value
    ? messages.value
    : messages.value.slice(messages.value.length - renderLimit.value)
);
const hiddenMessageCount = computed(
  () => messages.value.length - visibleMessages.value.length
);
const lastMessage = computed(() => messages.value[messages.value.length - 1]);

/** 追加更早的一批，并保持当前视口位置（不然内容会整体往下跳）。 */
async function showEarlierMessages(): Promise<void> {
  const el = historyEl.value;
  const before = el?.scrollHeight ?? 0;
  renderLimit.value += RENDER_STEP;
  await nextTick();
  if (el) el.scrollTop += el.scrollHeight - before;
}

// D3：历史抽屉搬到 /history 页面；对话页只保留「活动会话 + 最近线程」所需的两项。
const { activeSessionId, loadSessions } = useHistory((rows) => {
  messages.value = rows;
  renderLimit.value = RENDER_STEP;
});

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

function protocolDown(code: string, message: string): void {
  engineState.value = "error";
  pushMessage({
    role: "assistant",
    kind: "error",
    text: `${code}：${message}`,
  });
  if (code === "SIDECAR_LAUNCH_FAILED" || code === "MIGRATION_FAILED") {
    void loadRecovery();
  }
}

// R1a：迁移失败不自动还原；只在 marker 存在时显示恢复面。
const {
  recovery,
  choice: recoveryChoice,
  busy: recoveryBusy,
  notice: recoveryNotice,
  showManual: recoveryShowManual,
  load: loadRecovery,
  open: openRecovery,
  close: closeRecovery,
  restore: restoreRecovery,
} = useRecovery();

onMounted(async () => {
  void loadRecovery();
  try {
    unlisten = await ipc.onSidecarEvent(handleFrame, (failure) => {
      protocolDown(failure.code, failure.message);
    });
    unlistenPtt = await ipc.onPttShortcut((pressed) => {
      if (firstRun.value) return;
      if (pttMode.value === "toggle") {
        // 开关模式只认"按下"，松开不再触发停止
        if (pressed) toggleTalk();
        return;
      }
      if (pressed) pttStart();
      else pttStop();
    });
    unlistenTalk = await ipc.onTalkToggle(toggleTalk);
    unlistenSettings = await ipc.onOpenSettings(() => {
      void openSettings();
    });
  } catch (err) {
    // 浏览器预览 / 事件总线不可用：不让挂载中断，下面的初始化照常跑
    console.warn("sidecar event bus unavailable:", err);
  }
  void loadProfile();
  void loadVoices();
  if (!maybeLoadDemoThread()) void loadRecentThread();
  // 设备选择与音量是设备级偏好（localStorage），挂载后立即回放给壳侧
  void refreshDevices();
  void applyOutputDevice();
  void applyVolume();
});

onUnmounted(() => {
  unlisten?.();
  unlistenPtt?.();
  unlistenSettings?.();
  unlistenTalk?.();
});

function handleFrame(frame: SidecarMessage): void {
  switch (frame.type) {
    case "hello":
      asrReady.value = frame.engines.some((e) => e.name === "asr" && e.ready);
      noteEngines(frame.engines);
      void loadRecentThread();
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
      pushMessage({ role: "user", text: frame.text });
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
        pushMessage({ role: "assistant", text });
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
      if (status === "SUCCESS") {
        // 一轮完整通过三条链：之前的单链失败不再算「不可用」
        failedChains.value = [];
        maybeNotify();
      }
      break;
    }
    case "error":
      pushMessage({
        role: "assistant",
        kind: "error",
        text: `${frame.code}：${frame.message}`,
        code: frame.code,
      });
      streaming.value = false;
      busy.value = false;
      if (frame.code === "HISTORY_WRITE_FAILED") historyFailures.value += 1;
      {
        const chain = chainForCode(frame.code);
        if (chain && !failedChains.value.includes(chain)) {
          failedChains.value = [...failedChains.value, chain];
        }
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

// ---- 按住说话（§12 步骤 4）：getUserMedia 48k PCM16 分片 → Rust 重采样 16k → WS ----
const PTT_CHUNK = 4800; // 100ms @48k
const captureHeld = ref(false);
const listening = ref(false);
/** 3.5 动作矩阵：generating/speaking 期 PTT 可用，按下即打断（不是禁用）。 */
const pttEnabled = computed(
  () =>
    !readOnly.value &&
    asrReady.value &&
    (engineState.value === "ready" ||
      engineState.value === "generating" ||
      engineState.value === "speaking"),
);

// 按住期间不能把按钮置灰：disabled 元素收不到 mouseup，会一直录到上限。
const pttHoldDisabled = computed(() => !captureHeld.value && !pttEnabled.value);

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
    .then(() => ipc.pttPush(samples))
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

/** 采集入口：48k→16k→WS；PTT 按下即打断。 */
async function startCapture(): Promise<void> {
  if (!pttEnabled.value || captureHeld.value) return;
  captureHeld.value = true;
  void ipc.showHud();
  if (busy.value) {
    // 三跳首跳：按下即关闸门 + 清播放缓冲 + 通知 sidecar 取消（≤100ms 内静音，
    // 不等 sidecar 确认）。必须先于 getUserMedia——权限/设备协商可能要几百毫秒。
    void ipc.interruptTurn().catch((err) => {
      micStatus.value = `⚠ 打断失败：${String(err)}`;
    });
  }
  try {
    const stream = await openMicStream();
    if (!captureHeld.value) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    await ipc.pttStart();
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
    micStatus.value = "🎙 录音中…";
  } catch (err) {
    captureHeld.value = false;
    cleanupMic();
    void ipc.hideHud();
    micStatus.value = `⚠ ${micErrorMessage(err)}`;
  }
}

async function stopCapture(): Promise<void> {
  if (!captureHeld.value) return;
  captureHeld.value = false;
  if (!micStream) return; // getUserMedia 尚未返回：startCapture 会自行清理
  const rest = pendingSamples;
  pendingSamples = [];
  cleanupMic();
  try {
    await sendChain;
    if (rest.length > 0) await ipc.pttPush(rest);
    await ipc.pttStop();
    micStatus.value = "识别中…";
  } catch (err) {
    micStatus.value = `⚠ ${String(err)}`;
  }
}

function pttStart(): void {
  if (readOnly.value) return;
  void startCapture();
}

function pttStop(): void {
  void stopCapture();
}

function onSetupDone(): void {
  firstRun.value = false;
  // 向导可能刚写入了 provider/model/key：重新拉一次设置与音色
  void loadProfile();
  void loadVoices();
}

function onWindowBlur(): void {
  void stopCapture();
}

onMounted(() => {
  // main.ts 已在挂载前写入 dataset（避免暗色主题首帧闪白），这里按当前选择再校准一次
  applyTheme();
  // 跟随系统时，系统主题切换要即时生效
  darkQuery?.addEventListener("change", applyTheme);
  window.addEventListener("blur", onWindowBlur);
  // 独立设置窗口保存后，主窗口回到前台时重新拉取设置/音色（无跨窗口事件总线）
  window.addEventListener("focus", onWindowFocus);
});

onUnmounted(() => {
  darkQuery?.removeEventListener("change", applyTheme);
  window.removeEventListener("blur", onWindowBlur);
  window.removeEventListener("focus", onWindowFocus);
  captureHeld.value = false;
  cleanupMic();
});

/** 停止播放（3.5 动作矩阵）：丢弃当前 turn 但不进入采集 → `control(cancel_turn)`。 */
function stopTurn(): void {
  void ipc.cancelTurn().catch((err) => {
    micStatus.value = `⚠ 停止失败：${String(err)}`;
  });
}

/** 上翻看历史时新消息静默到达：给一个回到最新的出口 */
function scrollToLatest(): void {
  const el = historyEl.value;
  if (!el) return;
  pinned.value = true;
  el.scrollTop = el.scrollHeight;
}

const composerRef = ref<{ focus: () => void } | null>(null);
const suggestions = ["今天有点累", "给我讲个故事", "你还记得……"];

function useSuggestion(text: string): void {
  input.value = text;
  composerRef.value?.focus();
}

async function send(): Promise<void> {
  if (readOnly.value) return;
  const text = input.value.trim();
  if (!text) return;
  if (busy.value) {
    // 3.5：文本输入 = 打断并发起新 turn（旧 turn 收尾为 CANCELLED）
    void ipc.interruptTurn().catch(() => {});
  }
  pushMessage({ role: "user", text });
  input.value = "";
  pinned.value = true;
  busy.value = true;
  composerRef.value?.focus();
  try {
    await ipc.sendUserText(text);
  } catch (err) {
    pushMessage({
      role: "assistant",
      kind: "error",
      text: `发送失败：${String(err)}`,
    });
    streaming.value = false;
    busy.value = false;
  }
}

let threadLoaded = false;
let threadLoading = false;

/** 仅开发态：`#/?demo=1` 或 `#/chat?demo=1` 时用固定线程做视觉回归。 */
function maybeLoadDemoThread(): boolean {
  if (!import.meta.env.DEV) return false;
  const params = new URLSearchParams(window.location.hash.split("?")[1] ?? "");
  if (params.get("demo") !== "1") return false;
  const now = Date.now();
  messages.value = [
    {
      role: "user",
      text: "今天有点累，不想说话。",
      at: now - 4 * 60_000,
    },
    {
      role: "assistant",
      text: "那就先不用说话。我把声音放小一点，陪你把这段雨听完。",
      at: now - 3 * 60_000,
    },
    {
      role: "user",
      text: "你还记得我上次说的那张唱片吗？",
      at: now - 2 * 60_000,
    },
    {
      role: "assistant",
      text: "记得。你说它在雨天听起来像有人在隔壁房间翻书。要我从第二首开始放吗？",
      at: now - 60_000,
    },
    {
      role: "assistant",
      text: "我找一下那张唱片……",
      at: now - 30_000,
      interrupted: true,
    },
    {
      role: "assistant",
      kind: "error",
      code: "LLM_PROVIDER_UNAVAILABLE",
      text: "这次没接上。可以重试，或去设置看看引擎。",
      at: now - 10_000,
    },
  ];
  threadLoaded = true;
  return true;
}

/**
 * D3：回到对话页时把活动会话的最近 40 轮回填到线程。
 * 历史页点「继续对话」会在 sessionStorage 里留一个 id，优先用它。
 * sidecar 未就绪时静默失败，等 hello 再试。
 */
async function loadRecentThread(): Promise<void> {
  if (threadLoaded || threadLoading || messages.value.length > 0) {
    return;
  }
  threadLoading = true;
  try {
    let pending = "";
    try {
      pending = sessionStorage.getItem("echoes.openSession") ?? "";
    } catch {
      // 隐私模式/存储不可用：退回到当前活动会话
    }
    let sessionId = pending;
    if (!sessionId) {
      await loadSessions();
      sessionId = activeSessionId.value;
    }
    if (!sessionId) return;
    const turns = await ipc.historyList(sessionId, 40, 0);
    if (pending) {
      try {
        sessionStorage.removeItem("echoes.openSession");
      } catch {
        // 存储不可用：不影响线程加载
      }
    }
    messages.value = turns.slice().reverse().flatMap(historyTurnRows);
    renderLimit.value = RENDER_STEP;
    threadLoaded = true;
    await nextTick();
    scrollToLatest();
  } catch {
    // 浏览器预览或 sidecar 还在启动；保留空态，hello 时会再试一次。
  } finally {
    threadLoading = false;
  }
}
</script>

<template>
  <div
    v-if="recoveryShowManual || recovery?.failed"
    class="recovery-mask"
    role="alertdialog"
    aria-modal="true"
  >
    <section class="recovery-card">
      <div class="block-head">
        <div>
          <p class="eyebrow">数据恢复</p>
          <h2>{{ recovery?.failed ? "启动没有完成" : "从备份还原" }}</h2>
        </div>
        <button
          v-if="!recovery?.failed"
          type="button"
          class="quiet"
          @click="closeRecovery"
        >
          关闭
        </button>
      </div>
      <p class="recovery-message">
        {{
          recovery?.message ||
          (recovery?.failed
            ? "数据库迁移失败。旧库仍在，备份已保留。"
            : "选一个备份覆盖当前数据库；适合数据异常、误删后回滚。")
        }}
      </p>
      <p v-if="recovery?.dbPath" class="note recovery-path">{{ recovery.dbPath }}</p>

      <label v-if="recovery?.backups.length" class="recovery-field">
        <span>选择备份</span>
        <select v-model="recoveryChoice">
          <option v-for="backup in recovery.backups" :key="backup.path" :value="backup.path">
            {{ backup.name }}
          </option>
        </select>
      </label>
      <p v-else-if="!recovery" class="note">读取备份中…</p>
      <p v-else class="note">backup 目录里没有 .db 备份。</p>

      <button
        type="button"
        class="recovery-restore"
        :disabled="!recoveryChoice || recoveryBusy"
        @click="restoreRecovery"
      >
        {{ recoveryBusy ? "还原中…" : "从备份还原" }}
      </button>
      <p v-if="recoveryNotice" class="note" role="status">{{ recoveryNotice }}</p>
      <p class="note">还原不会自动重启应用；请退出后重新打开 Echoes。</p>
    </section>
  </div>
  <div class="app embedded">
    <FirstRun v-if="firstRun" @done="onSetupDone" />
    <ChatHeader
      :name="companionName"
      :state-label="stateLabel"
      :state-tone="stateTone"
      :privacy-mode="settingsDraft.privacyMode"
      :privacy-title="chainSummary"
      :voice-name="selectedVoiceName"
      :busy="busy"
      :can-recover="engineState === 'error'"
      @open-settings="openSettings"
      @stop="stopTurn"
      @recover="openRecovery"
    />

    <div class="thread-wrap">
      <ol
        ref="historyEl"
        class="thread"
        aria-live="polite"
        aria-relevant="additions"
        @scroll.passive="onThreadScroll"
      >
        <li v-if="messages.length === 0" class="thread-empty">
          <DsEmptyState
            title="她还在听。"
            description="按住空格说话，或者写一句。"
          >
            <DsChip
              v-for="suggestion in suggestions"
              :key="suggestion"
              @click="useSuggestion(suggestion)"
            >
              {{ suggestion }}
            </DsChip>
          </DsEmptyState>
        </li>

        <li v-if="hiddenMessageCount > 0" class="earlier">
          <DsButton variant="ghost" size="sm" @click="showEarlierMessages">
            显示更早的 {{ hiddenMessageCount }} 条
          </DsButton>
        </li>

        <MessageItem
          v-for="(m, i) in visibleMessages"
          :key="hiddenMessageCount + i"
          :message="m"
          :companion-name="companionName"
          :streaming="streaming"
          :is-last="m === lastMessage"
          :error-action="noticeAction(m.code)"
          @error-action="switchChainByCode(m.code)"
        />
      </ol>

      <transition name="fade">
        <button
          v-if="!pinned && messages.length > 0"
          type="button"
          class="jump"
          @click="scrollToLatest"
        >
          <svg
            width="11"
            height="11"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            aria-hidden="true"
          >
            <path d="M12 5v13M6 12l6 6 6-6" />
          </svg>
          回到最新
        </button>
      </transition>
    </div>

    <ChatComposer
      ref="composerRef"
      v-model="input"
      :busy="busy"
      :listening="listening"
      :read-only="readOnly"
      :ptt-disabled="pttHoldDisabled"
      :hint="pttHint"
      :engine-state="engineState"
      :mic-tone="micTone"
      :mic-notice="micNotice"
      :switch-status="switchStatus"
      :can-retry="canRetry"
      :history-failures="historyFailures"
      :failed-chains-count="failedChains.length"
      @send="send"
      @ptt-start="pttStart"
      @ptt-stop="pttStop"
      @reset-read-only="resetReadOnly"
      @open-settings="openSettings"
      @retry="retryLast"
      @edit="editLast"
    />
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

/* 主题 token 在 src/styles/themes.css：这里只留结构与布局 */

html,
body,
#app {
  height: 100%;
}

/* 自绘标题栏与信纸列上下排列（fragment 根节点） */
#app {
  display: flex;
  flex-direction: column;
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
  flex: 1;
  min-height: 0;
  width: 100%;
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

/* D2：挂进 AppShell 后的对话页 —— 品牌由标题栏承担，内容列放宽到 860。 */
.app.embedded {
  max-width: 860px;
  border-left: none;
  border-right: none;
  background: transparent;
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
.thread-wrap {
  flex: 1;
  min-height: 0;
  position: relative;
  display: flex;
}

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



.thread-empty {
  display: flex;
  justify-content: center;
  padding-top: 10vh;
}

.thread-empty .ds-empty {
  align-items: center;
  text-align: center;
}

.thread-empty .ds-empty__actions {
  justify-content: center;
}

/* R5 分段渲染：更早的消息按批展开 */
.earlier {
  display: flex;
  justify-content: center;
  list-style: none;
}





.jump {
  position: absolute;
  left: 50%;
  bottom: 12px;
  z-index: 2;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border: 1px solid var(--rule-strong);
  border-radius: 999px;
  background: var(--paper-hi);
  font-size: 11.5px;
  color: var(--ink-2);
  white-space: nowrap;
  box-shadow: 0 4px 16px rgba(35, 32, 27, 0.1);
  transition:
    border-color 0.16s ease,
    color 0.16s ease;
}

.jump:hover {
  border-color: var(--accent);
  color: var(--accent);
}

/* 恢复面/首启共用的少量排版（设置面板已搬出 Chat） */
.eyebrow {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  line-height: 14px;
  text-transform: uppercase;
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.note {
  color: var(--ink-3);
  font-size: 12px;
  line-height: 18px;
}

.note[data-tone="warn"] {
  color: var(--warn);
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

.recovery-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: 24px;
  background: color-mix(in srgb, var(--ink, #2b2722) 38%, transparent);
  backdrop-filter: blur(3px);
}

.recovery-card {
  width: min(560px, 100%);
  padding: 28px 30px;
  border: 1px solid var(--line, #d8d0c2);
  border-radius: 14px;
  background: var(--paper, #f7f1e5);
  box-shadow: 0 24px 80px rgb(30 24 16 / 24%);
}

.recovery-card h2 {
  margin: 6px 0 12px;
  font-size: 1.35rem;
}

.recovery-message {
  margin: 0 0 10px;
  color: var(--muted, #6f6658);
  line-height: 1.7;
}

.recovery-path {
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}

.recovery-field {
  display: grid;
  gap: 6px;
  margin: 16px 0;
  font-size: 0.88rem;
}

.recovery-field select {
  width: 100%;
  padding: 9px 10px;
  border: 1px solid var(--line, #d8d0c2);
  border-radius: 8px;
  background: #fffdf8;
  color: inherit;
}

.recovery-restore {
  margin-top: 4px;
  padding: 10px 16px;
  border: 0;
  border-radius: 999px;
  background: var(--ink, #2b2722);
  color: var(--paper, #f7f1e5);
  cursor: pointer;
}

.recovery-restore:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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
