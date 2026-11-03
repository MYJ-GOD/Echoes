<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import type { UnlistenFn } from "@tauri-apps/api/event";

import * as ipc from "../../lib/ipc";
import { PERSONA_PRESETS } from "../../lib/personaPresets";
import { useAudioDevices } from "../../composables/useAudioDevices";
import { useData } from "../../composables/useData";
import { useDensity } from "../../composables/useDensity";
import { useSettings } from "../../composables/useSettings";
import { useTheme } from "../../composables/useTheme";
import type { ThemeMode } from "../../composables/useTheme";
import DsButton from "../ui/DsButton.vue";
import DsCard from "../ui/DsCard.vue";
import DsCheckbox from "../ui/DsCheckbox.vue";
import DsChip from "../ui/DsChip.vue";
import DsField from "../ui/DsField.vue";
import DsInput from "../ui/DsInput.vue";
import DsMeter from "../ui/DsMeter.vue";
import DsSelect from "../ui/DsSelect.vue";
import DsSegmented from "../ui/DsSegmented.vue";
import DsSkin from "../ui/DsSkin.vue";
import DsStatusDot from "../ui/DsStatusDot.vue";
import DsSwitch from "../ui/DsSwitch.vue";
import DsTextarea from "../ui/DsTextarea.vue";
import PageHeader from "../layout/PageHeader.vue";
import { settingsIcons } from "../layout/icons";

type Section =
  | "appearance"
  | "persona"
  | "engine"
  | "voice"
  | "data"
  | "shortcuts"
  | "about";

const sections: { id: Section; label: string; title: string; desc: string }[] = [
  {
    id: "appearance",
    label: "外观",
    title: "外观",
    desc: "主题只换颜色，不改变布局。跟随系统会按操作系统的深浅色自动切换。",
  },
  {
    id: "persona",
    label: "人设",
    title: "声音与人格",
    desc: "名字与系统提示词会进入每一轮对话；保存后下一轮生效。",
  },
  {
    id: "engine",
    label: "引擎与启动",
    title: "引擎与启动",
    desc: "三条链各自可选本地或云端。云端端点需要逐链同意；选定的路径不会被静默替换。",
  },
  {
    id: "voice",
    label: "声音与设备",
    title: "声音与设备",
    desc: "音色、麦克风与扬声器。样本和克隆音色只留在本机。",
  },
  {
    id: "data",
    label: "数据与隐私",
    title: "数据与隐私",
    desc: "导出、备份、还原与彻底删除。云端 key 不属于导出内容。",
  },
  {
    id: "shortcuts",
    label: "快捷键",
    title: "快捷键与系统",
    desc: "开机自启、关闭行为、后台通知与说话快捷键。",
  },
  {
    id: "about",
    label: "关于",
    title: "关于",
    desc: "版本、诊断包与许可信息。",
  },
];

const props = withDefaults(
  defineProps<{
    /** true = 主窗口内的整页回退；false = Tauri 独立设置窗口。 */
    inline?: boolean;
  }>(),
  { inline: false },
);

const router = useRouter();
const section = ref<Section>("appearance");
const current = computed(
  () => sections.find((item) => item.id === section.value) ?? sections[0]!,
);

const {
  mode: themeMode,
  resolved: themeResolved,
  setMode: setTheme,
} = useTheme();
const themeValue = computed({
  get: () => themeMode.value,
  set: (value: string) => setTheme(value as ThemeMode),
});
const themeOptions = [
  { value: "system", label: "跟随系统" },
  { value: "light", label: "浅色" },
  { value: "dark", label: "深色" },
];

const { density, setDensity } = useDensity();
const densityValue = computed({
  get: () => density.value,
  set: (value: string) => setDensity(value === "compact" ? "compact" : "comfortable"),
});
const densityOptions = [
  { value: "comfortable", label: "舒适" },
  { value: "compact", label: "紧凑" },
];

const {
  personaDraft,
  settingsDraft,
  firstRun,
  llmKeyDraft,
  keyStatus,
  ttsKeyDraft,
  ttsKeyStatus,
  asrKeyDraft,
  asrKeyStatus,
  activeLlm,
  activeTts,
  activeAsr,
  llmPending,
  ttsPending,
  asrPending,
  preset,
  presetLabel,
  voices,
  voicesStatus,
  voiceBusy,
  VOICE_LIMIT,
  clonedVoiceCount,
  voiceQuotaReached,
  renameVoiceItem,
  deleteVoiceItem,
  profileStatus,
  privacyConflict,
  ttsPrivacyConflict,
  asrPrivacyConflict,
  llmNeedsConsent,
  asrNeedsConsent,
  ttsNeedsConsent,
  loadProfile,
  savePersona,
  saveSettings,
  onProviderChange,
  onTtsProviderChange,
  onAsrProviderChange,
  applyPreset,
  saveKey,
  clearKey,
  saveTtsKey,
  clearTtsKey,
  saveAsrKey,
  clearAsrKey,
  loadVoices,
  modelOptions,
  modelsStatus,
  localModelsStatus,
  installingModels,
  installPct,
  modelInventory,
  modelInventoryStatus,
  removingModel,
  loadModelInventory,
  removeModel,
  loadModels,
  loadLocalModels,
  installLocalModels,
  chooseVoice,
  voiceLabel,
  noteEngines,
} = useSettings();

const PRESETS = [
  { id: "cloud", name: "云端", desc: "三条链全云，开箱即用" },
  { id: "offline", name: "本地", desc: "全本地，隐私优先" },
  { id: "hybrid", name: "混合", desc: "云脑 + 本地耳朵/嗓子" },
] as const;

const {
  inputDevices,
  outputDevices,
  inputDeviceId,
  outputDeviceName,
  volume,
  micLevel,
  previewing,
  status: audioStatus,
  refreshDevices,
  selectInput,
  selectOutput,
  applyOutputDevice,
  applyVolume,
  testOutput,
  togglePreview,
  openMicStream,
} = useAudioDevices();

const {
  status: dataStatus,
  busy: dataBusy,
  exportPath,
  importPath,
  diagnosticsPath,
  backups,
  backupsStatus,
  wipeConfirm,
  wiped,
  loadBackups,
  exportData,
  backupNow,
  importData,
  exportDiagnostics,
  wipeAll,
} = useData();

// ---- 主题 ----
const themePreview = computed(() => themeResolved.value);

function applyPersonaPreset(event: Event): void {
  const target = event.target as HTMLSelectElement;
  const preset = PERSONA_PRESETS.find((item) => item.id === target.value);
  if (preset) personaDraft.value.systemPrompt = preset.prompt;
  target.value = "";
}

/** 只把技术异常翻译成人话；业务提示（已保存/缺少模型）原样保留。 */
function friendly(value: string): string {
  if (!value) return "";
  if (/TypeError|Cannot read properties|invoke|not a function/i.test(value)) {
    return "读取失败。确认 sidecar 已启动后再试。";
  }
  return value;
}

// ---- 快捷键 / 系统 ----
const NOTIFY_KEY = "echoes.notify.reply";
const PTT_MODE_KEY = "echoes.ptt.mode";
const autostartEnabled = ref(false);
const autostartStatus = ref("");
const closeToTray = ref(true);
const closeToTrayStatus = ref("");
const notifyOnReply = ref(readNotify());
const pttShortcut = ref("Alt+Space");
const pttShortcutDraft = ref("Alt+Space");
const pttShortcutStatus = ref("");
const pttMode = ref<"hold" | "toggle">(readPttMode());

function readNotify(): boolean {
  try {
    return localStorage.getItem(NOTIFY_KEY) === "on";
  } catch {
    return false;
  }
}

function saveNotify(): void {
  try {
    localStorage.setItem(NOTIFY_KEY, notifyOnReply.value ? "on" : "off");
  } catch {
    // 只在本次会话生效
  }
}

function readPttMode(): "hold" | "toggle" {
  try {
    return localStorage.getItem(PTT_MODE_KEY) === "toggle" ? "toggle" : "hold";
  } catch {
    return "hold";
  }
}

function savePttMode(): void {
  try {
    localStorage.setItem(PTT_MODE_KEY, pttMode.value);
  } catch {
    // 只在本次会话生效
  }
}

async function loadAutostart(): Promise<void> {
  try {
    autostartEnabled.value = await ipc.autostartGet();
  } catch {
    autostartStatus.value = "读取开机自启失败。";
  }
}

async function toggleAutostart(): Promise<void> {
  autostartStatus.value = "";
  try {
    await ipc.autostartSet(autostartEnabled.value);
    autostartEnabled.value = await ipc.autostartGet();
  } catch {
    autostartStatus.value = "设置开机自启失败。";
    autostartEnabled.value = !autostartEnabled.value;
  }
}

async function loadCloseToTray(): Promise<void> {
  try {
    closeToTray.value = await ipc.closeToTrayGet();
  } catch {
    closeToTrayStatus.value = "读取关闭行为失败。";
  }
}

async function toggleCloseToTray(): Promise<void> {
  closeToTrayStatus.value = "";
  try {
    await ipc.closeToTraySet(closeToTray.value);
    closeToTray.value = await ipc.closeToTrayGet();
  } catch {
    closeToTrayStatus.value = "设置关闭行为失败。";
    closeToTray.value = !closeToTray.value;
  }
}

async function loadPttShortcut(): Promise<void> {
  pttShortcutStatus.value = "";
  try {
    pttShortcut.value = await ipc.pttShortcutGet();
    pttShortcutDraft.value = pttShortcut.value;
  } catch {
    pttShortcutStatus.value = "读取说话快捷键失败。";
  }
}

async function applyPttShortcut(): Promise<void> {
  const next = pttShortcutDraft.value.trim();
  if (!next || next === pttShortcut.value) return;
  pttShortcutStatus.value = "";
  try {
    await ipc.pttShortcutSet(next);
    pttShortcut.value = await ipc.pttShortcutGet();
    pttShortcutDraft.value = pttShortcut.value;
    pttShortcutStatus.value = `已生效：${pttShortcut.value}`;
  } catch {
    pttShortcutStatus.value = "快捷键注册失败；旧快捷键仍有效。";
  }
}

// ---- 克隆 ----
const CLONE_MIN_SECONDS = 3;
const CLONE_MAX_SECONDS = 6;
const CLONE_CHUNK = 4800;

const clonePhase = ref<null | "recording" | "training" | "checking">(null);
const clonePct = ref(0);
const cloneError = ref("");
const cloneSeconds = ref(0);

let cloneTimer: number | null = null;
let cloneStream: MediaStream | null = null;
let cloneCtx: AudioContext | null = null;
let cloneSource: MediaStreamAudioSourceNode | null = null;
let cloneProcessor: ScriptProcessorNode | null = null;
let cloneMute: GainNode | null = null;
let cloneSamples: number[] = [];
let cloneSend: Promise<unknown> = Promise.resolve();

const cloneRecording = computed(() => clonePhase.value === "recording");
const cloneDisabled = computed(
  () =>
    clonePhase.value === "training" ||
    clonePhase.value === "checking" ||
    voiceQuotaReached.value ||
    settingsDraft.value.ttsProvider === "openai",
);
const cloneLabel = computed(() => {
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

function cloneCleanup(): void {
  if (cloneProcessor) cloneProcessor.onaudioprocess = null;
  cloneProcessor?.disconnect();
  cloneSource?.disconnect();
  cloneMute?.disconnect();
  cloneStream?.getTracks().forEach((track) => track.stop());
  if (cloneCtx && cloneCtx.state !== "closed") void cloneCtx.close();
  cloneProcessor = null;
  cloneSource = null;
  cloneMute = null;
  cloneStream = null;
  cloneCtx = null;
  cloneSamples = [];
}

function stopCloneTimer(): void {
  if (cloneTimer !== null) {
    window.clearInterval(cloneTimer);
    cloneTimer = null;
  }
}

function enqueueClone(samples: number[]): void {
  cloneSend = cloneSend
    .then(() => ipc.clonePush(samples))
    .catch((err) => {
      cloneError.value = `音频上传失败：${String(err)}`;
    });
}

async function startClone(): Promise<void> {
  if (cloneRecording.value) {
    await stopClone();
    return;
  }
  if (cloneDisabled.value) return;
  cloneError.value = "";
  clonePhase.value = "recording";
  clonePct.value = 0;
  cloneSeconds.value = 0;
  try {
    const stream = await openMicStream();
    cloneStream = stream;
    await ipc.cloneRecordStart();
    const ctx = new AudioContext({ sampleRate: 48000 });
    if (Math.round(ctx.sampleRate) !== 48000) {
      await ctx.close();
      throw new Error(`采集采样率应为 48k（当前 ${ctx.sampleRate}Hz）`);
    }
    await ctx.resume();
    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = (event) => {
      const data = event.inputBuffer.getChannelData(0);
      for (let index = 0; index < data.length; index += 1) {
        const value = Math.max(-1, Math.min(1, data[index]!));
        cloneSamples.push(
          Math.round(value < 0 ? value * 0x8000 : value * 0x7fff),
        );
      }
      while (cloneSamples.length >= CLONE_CHUNK) {
        enqueueClone(cloneSamples.splice(0, CLONE_CHUNK));
      }
    };
    source.connect(processor);
    const mute = ctx.createGain();
    mute.gain.value = 0;
    processor.connect(mute);
    mute.connect(ctx.destination);
    cloneCtx = ctx;
    cloneSource = source;
    cloneProcessor = processor;
    cloneMute = mute;
    cloneTimer = window.setInterval(() => {
      cloneSeconds.value += 1;
      if (cloneSeconds.value >= CLONE_MAX_SECONDS) void stopClone();
    }, 1000);
  } catch (err) {
    cloneCleanup();
    stopCloneTimer();
    clonePhase.value = null;
    cloneError.value = `无法录音：${String(err)}`;
    void ipc.cloneCancel().catch(() => undefined);
  }
}

async function stopClone(): Promise<void> {
  if (clonePhase.value !== "recording") return;
  if (cloneSeconds.value < CLONE_MIN_SECONDS) {
    cloneError.value = "至少录 3 秒再结束。";
    return;
  }
  stopCloneTimer();
  const rest = cloneSamples;
  cloneSamples = [];
  cloneCleanup();
  try {
    await cloneSend;
    if (rest.length > 0) await ipc.clonePush(rest);
    await ipc.cloneRecordStop();
    clonePhase.value = "training";
    cloneSeconds.value = 0;
  } catch (err) {
    clonePhase.value = null;
    cloneError.value = `结束录音失败：${String(err)}`;
  }
}

async function cancelClone(): Promise<void> {
  stopCloneTimer();
  cloneCleanup();
  try {
    await ipc.cloneCancel();
  } catch {
    // 取消失败不阻塞 UI
  }
  clonePhase.value = null;
  clonePct.value = 0;
  cloneSeconds.value = 0;
}

// ---- 数据 / 关于 ----
const recoveryBusy = ref(false);
const recoveryNotice = ref("");
const version = ref("0.1.0");

async function restoreBackup(path: string): Promise<void> {
  if (!window.confirm(`从备份「${path}」还原？当前数据库会被覆盖。`)) return;
  recoveryBusy.value = true;
  recoveryNotice.value = "";
  try {
    await ipc.recoveryRestore(path);
    recoveryNotice.value = "已还原；请退出后重新打开 Echoes。";
  } catch {
    recoveryNotice.value = "还原失败。确认备份文件仍存在后重试。";
  } finally {
    recoveryBusy.value = false;
  }
}

async function rerunSetup(): Promise<void> {
  try {
    await ipc.resetSetup();
    firstRun.value = true;
    profileStatus.value = "首启向导已重置；回到主窗口后会重新出现。";
  } catch {
    profileStatus.value = "重置首启向导失败。";
  }
}

// ---- 保存 ----
const saving = ref(false);

async function saveAll(): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  try {
    await savePersona();
    await saveSettings();
  } finally {
    saving.value = false;
  }
}

// ---- 事件 ----
let unlisten: UnlistenFn | null = null;

function handleFrame(frame: { type: string; [key: string]: unknown }): void {
  if (frame.type === "hello") {
    const engines = (frame as { engines?: Array<{ name: string; provider?: string | null; model?: string | null }> }).engines;
    if (engines) noteEngines(engines);
    // 设置窗口可能先于 sidecar 打开：hello 到了再拉一次，避免一直显示空列表。
    void loadProfile();
    void loadVoices();
    return;
  }
  if (frame.type === "clone_progress") {
    const progress = frame as {
      phase?: string;
      pct?: number;
    };
    clonePhase.value =
      progress.phase === "recording" ||
      progress.phase === "training" ||
      progress.phase === "checking"
        ? progress.phase
        : "training";
    clonePct.value = Number(progress.pct) || 0;
    if (clonePhase.value === "checking" && clonePct.value >= 100) {
      clonePhase.value = null;
      clonePct.value = 100;
      void loadVoices();
    }
    return;
  }
  if (frame.type === "error" && clonePhase.value !== null) {
    clonePhase.value = null;
    cloneError.value = "克隆失败。确认样本足够长且环境不吵后重试。";
  }
}

onMounted(async () => {
  void loadProfile();
  void loadVoices();
  void loadAutostart();
  void loadCloseToTray();
  void loadPttShortcut();
  void refreshDevices();
  void applyOutputDevice();
  void applyVolume();
  void loadBackups();
  void loadModelInventory();
  void loadLocalModels();
  try {
    const { getVersion } = await import("@tauri-apps/api/app");
    version.value = await getVersion();
  } catch {
    // 浏览器预览：保留基线版本
  }
  try {
    unlisten = await ipc.onSidecarEvent((frame) => handleFrame(frame as never));
  } catch {
    // 事件总线不可用：设置仍可读，引擎状态显示等待
  }
});

onUnmounted(() => {
  unlisten?.();
  stopCloneTimer();
  if (clonePhase.value !== null) void ipc.cloneCancel().catch(() => undefined);
  cloneCleanup();
});

async function closeWindow(): Promise<void> {
  if (props.inline) {
    await router.push("/");
    return;
  }
  try {
    await ipc.closeWindow();
  } catch {
    // 浏览器预览
  }
}
</script>

<template>
  <DsSkin class="settings-skin">
    <!-- 独立窗口自绘标题栏：与主窗口同一套（品牌 + 最小化/关闭），
         `decorations: false` 由 Rust 侧保证；inline 回退时主壳已有标题栏，不再重复。 -->
    <header
      v-if="!inline"
      class="settings__titlebar"
      data-tauri-drag-region="deep"
    >
      <span class="settings__brand">ECHOES</span>
      <span class="settings__titlebar-divider" aria-hidden="true"></span>
      <span class="settings__titlebar-label">设置</span>
      <div class="settings__controls">
        <button
          type="button"
          class="settings__ctrl"
          aria-label="最小化"
          title="最小化"
          @click="ipc.minimizeWindow()"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M2 5h6" stroke="currentColor" stroke-width="1" />
          </svg>
        </button>
        <button
          type="button"
          class="settings__ctrl settings__ctrl--close"
          aria-label="关闭"
          title="关闭"
          @click="closeWindow"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
            <path d="M2.4 2.4l5.2 5.2M7.6 2.4L2.4 7.6" stroke="currentColor" stroke-width="1" />
          </svg>
        </button>
      </div>
    </header>

    <div class="settings">
      <aside class="settings__nav" aria-label="设置分组">
        <nav class="settings__nav-list">
          <button
            v-for="item in sections"
            :key="item.id"
            type="button"
            class="settings__nav-item"
            :class="{ 'is-on': section === item.id }"
            :aria-current="section === item.id ? 'page' : undefined"
            :title="item.label"
            @click="section = item.id"
          >
            <span class="settings__nav-icon" aria-hidden="true">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.7"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  v-for="(path, index) in settingsIcons[item.id]"
                  :key="index"
                  :d="path"
                />
              </svg>
            </span>
            <span class="settings__nav-label">{{ item.label }}</span>
          </button>
        </nav>

        <div class="settings__nav-bottom">
          <button
            type="button"
            class="settings__nav-item"
            :title="inline ? '返回对话' : '关闭窗口'"
            @click="closeWindow"
          >
            <span class="settings__nav-icon" aria-hidden="true">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.7"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  v-for="(path, index) in settingsIcons.back"
                  :key="index"
                  :d="path"
                />
              </svg>
            </span>
            <span class="settings__nav-label">{{ inline ? "返回对话" : "关闭窗口" }}</span>
          </button>
        </div>
      </aside>

      <main class="settings__main">
        <PageHeader eyebrow="Settings" :title="current.title" :description="current.desc">
          <template #actions>
            <DsStatusDot
              :tone="activeLlm && activeAsr && activeTts ? 'ready' : 'waiting'"
              :label="activeLlm && activeAsr && activeTts ? '引擎已就绪' : '等待 sidecar'"
            />
          </template>
        </PageHeader>

        <div class="settings__body">
          <section v-show="section === 'appearance'" class="settings__section">
            <DsCard>
              <div class="settings__row">
                <div>
                  <p class="settings__label">主题</p>
                  <p class="settings__hint">浅色 / 深色两套 token；跟随系统自动切换。</p>
                </div>
                <DsSegmented v-model="themeValue" :options="themeOptions" label="主题" />
              </div>
            </DsCard>

            <DsCard>
              <div class="settings__row">
                <div>
                  <p class="settings__label">密度</p>
                  <p class="settings__hint">舒适 / 紧凑只改间距和行高，不改布局。</p>
                </div>
                <DsSegmented v-model="densityValue" :options="densityOptions" label="密度" />
              </div>
            </DsCard>

            <DsCard>
              <p class="settings__label">预览</p>
              <div class="theme-preview" :data-preview="themePreview">
                <span class="theme-preview__name">她还在听。</span>
                <span class="theme-preview__meta">按住空格说话</span>
                <span class="theme-preview__accent"></span>
              </div>
            </DsCard>
          </section>

          <section v-show="section === 'persona'" class="settings__section">
            <DsCard>
              <div class="settings__stack">
                <DsField label="人格预设" hint="选择后覆盖系统提示词，可再手改">
                  <DsSelect @change="applyPersonaPreset">
                    <option value="">选择预设…</option>
                    <option
                      v-for="item in PERSONA_PRESETS"
                      :key="item.id"
                      :value="item.id"
                    >
                      {{ item.name }} · {{ item.desc }}
                    </option>
                  </DsSelect>
                </DsField>
                <DsField label="名字">
                  <DsInput v-model="personaDraft.name" placeholder="Echoes" />
                </DsField>
                <DsField label="系统提示词" hint="她是谁、怎么说话、记得什么">
                  <DsTextarea
                    v-model="personaDraft.systemPrompt"
                    :rows="7"
                    placeholder="她是谁、怎么说话、记得什么…"
                  />
                </DsField>
              </div>
            </DsCard>
          </section>

          <section v-show="section === 'engine'" class="settings__section">
            <DsCard>
              <p class="settings__label">一键套用</p>
              <div class="settings__chips">
                <DsChip
                  v-for="item in PRESETS"
                  :key="item.id"
                  :selected="preset === item.id"
                  :title="item.desc"
                  @click="applyPreset(item.id)"
                >
                  {{ item.name }}
                </DsChip>
                <span class="settings__hint">当前：{{ presetLabel }}</span>
              </div>
              <p class="settings__hint">
                预设只改链路；模型 / 端点 / Key 保留。任一链单独修改后标记为「自定义」。
              </p>
            </DsCard>

            <DsCard>
              <div class="settings__card-head">
                <p class="settings__label">对话模型（LLM）</p>
                <DsStatusDot
                  :tone="activeLlm ? 'ready' : 'waiting'"
                  :label="activeLlm ? `${activeLlm.provider ?? '?'}${activeLlm.model ? ' · ' + activeLlm.model : ''}` : '等待 sidecar'"
                />
              </div>
              <div class="settings__stack">
                <DsField label="后端">
                  <DsSelect v-model="settingsDraft.provider" @change="onProviderChange">
                    <option value="ollama">本地 Ollama</option>
                    <option value="openai">云端 / 兼容端点（API key）</option>
                    <option value="mock">无模型（仅测试）</option>
                  </DsSelect>
                </DsField>
                <DsField label="模型">
                  <DsInput v-model="settingsDraft.model" placeholder="qwen3:8b / deepseek-chat" />
                </DsField>
                <DsField v-if="settingsDraft.provider === 'openai'" label="Base URL" hint="填到 /v1 为止">
                  <DsInput v-model="settingsDraft.baseUrl" placeholder="https://api.deepseek.com/v1" />
                </DsField>
                <DsField
                  v-if="settingsDraft.provider === 'openai'"
                  label="API key"
                  :hint="settingsDraft.hasKey ? '已保存在 Windows 凭据管理器（留空不修改）' : '保存到 Windows 凭据管理器'"
                >
                  <div class="settings__key-row">
                    <DsInput v-model="llmKeyDraft" type="password" placeholder="sk-…" />
                    <DsButton size="sm" :disabled="llmKeyDraft.trim() === ''" @click="saveKey">保存</DsButton>
                    <DsButton variant="ghost" size="sm" :disabled="!settingsDraft.hasKey" @click="clearKey">清除</DsButton>
                  </div>
                </DsField>
                <p v-if="keyStatus" class="settings__hint">{{ friendly(keyStatus) }}</p>
                <DsCheckbox
                  v-if="llmNeedsConsent"
                  v-model="settingsDraft.llmCloudConsent"
                  label="我知晓对话文本会发送至该端点（数据出境）"
                />
                <div class="settings__actions">
                  <DsButton variant="ghost" size="sm" @click="loadModels">拉取模型列表</DsButton>
                  <span v-if="modelsStatus" class="settings__hint">{{ friendly(modelsStatus) }}</span>
                </div>
                <DsSelect v-if="modelOptions.length" v-model="settingsDraft.model" aria-label="已发现的模型">
                  <option value="">选择模型…</option>
                  <option v-for="option in modelOptions" :key="option.id" :value="option.id">
                    {{ option.id }}
                  </option>
                </DsSelect>
                <p v-if="llmPending" class="settings__hint" data-tone="warn">下一轮切换到新引擎。</p>
              </div>
            </DsCard>

            <DsCard>
              <div class="settings__card-head">
                <p class="settings__label">语音识别（ASR）</p>
                <DsStatusDot
                  :tone="activeAsr ? 'ready' : 'waiting'"
                  :label="activeAsr ? `${activeAsr.provider ?? '?'}${activeAsr.model ? ' · ' + activeAsr.model : ''}` : '等待 sidecar'"
                />
              </div>
              <div class="settings__stack">
                <DsField label="引擎">
                  <DsSelect v-model="settingsDraft.asrProvider" @change="onAsrProviderChange">
                    <option value="whisper">本地 whisper（录音不出本机）</option>
                    <option value="openai">云端 / 兼容端点（API key）</option>
                    <option value="mock">无模型（仅测试）</option>
                  </DsSelect>
                </DsField>
                <DsField v-if="settingsDraft.asrProvider === 'whisper'" label="档位">
                  <DsSelect v-model="settingsDraft.asrModel">
                    <option value="tiny">tiny（最快，准确度最低）</option>
                    <option value="base">base</option>
                    <option value="small">small（推荐）</option>
                  </DsSelect>
                </DsField>
                <DsField v-else label="模型">
                  <DsInput v-model="settingsDraft.asrModel" placeholder="whisper-1 / gpt-4o-transcribe" />
                </DsField>
                <DsField v-if="settingsDraft.asrProvider === 'openai'" label="Base URL">
                  <DsInput v-model="settingsDraft.asrBaseUrl" placeholder="https://api.openai.com/v1" />
                </DsField>
                <DsField
                  v-if="settingsDraft.asrProvider === 'openai'"
                  label="API key"
                  :hint="settingsDraft.hasAsrKey ? '已保存（留空不修改）' : '原始录音会发送到该端点'"
                >
                  <div class="settings__key-row">
                    <DsInput v-model="asrKeyDraft" type="password" placeholder="sk-…" />
                    <DsButton size="sm" :disabled="asrKeyDraft.trim() === ''" @click="saveAsrKey">保存</DsButton>
                    <DsButton variant="ghost" size="sm" :disabled="!settingsDraft.hasAsrKey" @click="clearAsrKey">清除</DsButton>
                  </div>
                </DsField>
                <p v-if="asrKeyStatus" class="settings__hint">{{ friendly(asrKeyStatus) }}</p>
                <DsCheckbox
                  v-if="asrNeedsConsent"
                  v-model="settingsDraft.asrCloudConsent"
                  label="我知晓原始录音会发送至该端点（数据出境）"
                />
                <p v-if="asrPrivacyConflict" class="settings__hint" data-tone="warn">
                  该端点与隐私模式互斥：请关闭隐私模式，或改填本机端点。
                </p>
                <p v-if="asrPending" class="settings__hint" data-tone="warn">下一次录音切换到新引擎。</p>
              </div>
            </DsCard>

            <DsCard>
              <div class="settings__card-head">
                <p class="settings__label">语音合成（TTS）</p>
                <DsStatusDot
                  :tone="activeTts ? 'ready' : 'waiting'"
                  :label="activeTts ? `${activeTts.provider ?? '?'}${activeTts.model ? ' · ' + activeTts.model : ''}` : '等待 sidecar'"
                />
              </div>
              <div class="settings__stack">
                <DsField label="引擎">
                  <DsSelect v-model="settingsDraft.ttsProvider" @change="onTtsProviderChange">
                    <option value="cosyvoice2">本地 CosyVoice2（可克隆音色）</option>
                    <option value="openai">云端 / 兼容端点（API key）</option>
                    <option value="mock">无模型（仅测试）</option>
                  </DsSelect>
                </DsField>
                <template v-if="settingsDraft.ttsProvider === 'openai'">
                  <DsField label="模型">
                    <DsInput v-model="settingsDraft.ttsModel" placeholder="tts-1 / gpt-4o-mini-tts" />
                  </DsField>
                  <DsField label="Base URL">
                    <DsInput v-model="settingsDraft.ttsBaseUrl" placeholder="https://api.openai.com/v1" />
                  </DsField>
                  <DsField
                    label="API key"
                    :hint="settingsDraft.hasTtsKey ? '已保存（留空不修改）' : '合成文本会发送到该端点'"
                  >
                    <div class="settings__key-row">
                      <DsInput v-model="ttsKeyDraft" type="password" placeholder="sk-…" />
                      <DsButton size="sm" :disabled="ttsKeyDraft.trim() === ''" @click="saveTtsKey">保存</DsButton>
                      <DsButton variant="ghost" size="sm" :disabled="!settingsDraft.hasTtsKey" @click="clearTtsKey">清除</DsButton>
                    </div>
                  </DsField>
                  <p v-if="ttsKeyStatus" class="settings__hint">{{ friendly(ttsKeyStatus) }}</p>
                  <DsCheckbox
                    v-if="ttsNeedsConsent"
                    v-model="settingsDraft.ttsCloudConsent"
                    label="我知晓合成文本会发送至该端点（数据出境）"
                  />
                  <p v-if="ttsPrivacyConflict" class="settings__hint" data-tone="warn">
                    该端点与隐私模式互斥：请关闭隐私模式，或改填本机端点。
                  </p>
                </template>
                <p v-if="ttsPending" class="settings__hint" data-tone="warn">下一句话切换到新引擎。</p>
              </div>
            </DsCard>

            <DsCard>
              <div class="settings__card-head">
                <p class="settings__label">本地模型</p>
                <DsButton variant="ghost" size="sm" @click="loadLocalModels(); loadModelInventory()">
                  检测
                </DsButton>
              </div>
              <ul v-if="modelInventory.length" class="model-list">
                <li v-for="model in modelInventory" :key="model.id">
                  <span :class="model.installed ? 'model-ok' : 'model-missing'">
                    {{ model.installed ? "✓" : "✗" }}
                  </span>
                  <span class="model-id">{{ model.id }}</span>
                  <span class="model-size">
                    {{ model.bytes ? `${(model.bytes / 1024 / 1024).toFixed(1)} MB` : `约 ${Math.round(model.expectedMb)} MB` }}
                  </span>
                  <DsButton
                    v-if="model.installed && model.kind !== 'ollama'"
                    variant="ghost"
                    size="sm"
                    :disabled="removingModel !== ''"
                    @click="removeModel(model.id)"
                  >
                    {{ removingModel === model.id ? "删除中…" : "删除" }}
                  </DsButton>
                  <span v-else-if="model.kind === 'ollama'" class="settings__hint">Ollama 管理</span>
                </li>
              </ul>
              <p v-if="modelInventoryStatus" class="settings__hint">{{ friendly(modelInventoryStatus) }}</p>
              <p v-if="localModelsStatus" class="settings__hint">{{ friendly(localModelsStatus) }}</p>
              <div class="settings__actions">
                <DsButton :disabled="installingModels" @click="installLocalModels">
                  {{ installingModels ? `安装中 ${installPct}%` : "安装缺失模型" }}
                </DsButton>
              </div>
              <p class="settings__hint">
                目录由 ECHOES_MODELS_DIR 指定；运行中删除/安装后需重启 sidecar 才生效。
              </p>
            </DsCard>
          </section>

          <section v-show="section === 'voice'" class="settings__section">
            <DsCard>
              <div class="settings__card-head">
                <p class="settings__label">当前音色</p>
                <DsStatusDot
                  :tone="voices.find((voice) => voice.selected)?.status === 'ready' ? 'ready' : 'waiting'"
                  :label="voices.find((voice) => voice.selected)?.displayName ?? '读取中'"
                />
              </div>
              <p class="settings__hint">
                已用 {{ clonedVoiceCount }} / {{ VOICE_LIMIT }}。切换音色只影响新回复，旧回复不变。
              </p>
              <div class="voice-list">
                <div
                  v-for="voice in voices"
                  :key="voice.id"
                  class="voice-row"
                  :class="{ 'is-selected': voice.selected }"
                >
                  <button
                    type="button"
                    class="voice-row__main"
                    :disabled="voice.status !== 'ready' || voiceBusy !== ''"
                    @click="chooseVoice(voice.id)"
                  >
                    <span class="voice-row__radio" :class="{ 'is-on': voice.selected }" aria-hidden="true"></span>
                    <span class="voice-row__text">
                      <span class="voice-row__name">{{ voice.displayName }}</span>
                      <span class="voice-row__meta">{{ voiceLabel(voice) }}</span>
                    </span>
                  </button>
                  <span
                    v-if="voice.id !== 'builtin:default' && !voice.id.startsWith('openai:')"
                    class="voice-row__actions"
                  >
                    <DsButton variant="ghost" size="sm" :disabled="voiceBusy !== ''" @click="renameVoiceItem(voice)">改名</DsButton>
                    <DsButton variant="ghost" size="sm" :disabled="voiceBusy !== ''" @click="deleteVoiceItem(voice)">删除</DsButton>
                  </span>
                </div>
                <p v-if="voices.length === 0" class="settings__hint">{{ friendly(voicesStatus) || "还没有可用音色。" }}</p>
              </div>
            </DsCard>

            <DsCard>
              <div class="settings__card-head">
                <p class="settings__label">克隆我的音色</p>
                <span class="settings__hint">{{ cloneLabel }}</span>
              </div>
              <p class="settings__hint">
                用本机麦克风录 3–6 秒。样本与音色只留在本机；相似度低于阈值会被拒绝。
              </p>
              <div class="settings__actions">
                <DsButton
                  :variant="cloneRecording ? 'danger' : 'primary'"
                  :disabled="cloneDisabled"
                  @click="startClone"
                >
                  {{
                    cloneRecording
                      ? `结束录音（${cloneSeconds}s）`
                      : clonePhase === "training" || clonePhase === "checking"
                        ? cloneLabel
                        : "开始录音"
                  }}
                </DsButton>
                <DsButton
                  v-if="clonePhase"
                  variant="ghost"
                  size="sm"
                  @click="cancelClone"
                >
                  取消
                </DsButton>
              </div>
              <DsMeter
                v-if="clonePhase && clonePhase !== 'recording'"
                :value="clonePct"
                label="克隆进度"
                show-value
              />
              <p v-if="cloneError" class="settings__hint" data-tone="error">{{ cloneError }}</p>
              <p v-if="settingsDraft.ttsProvider === 'openai'" class="settings__hint">
                云端 TTS 只提供预置音色；克隆需要切回本地 CosyVoice2。
              </p>
            </DsCard>

            <DsCard>
              <div class="settings__card-head">
                <p class="settings__label">音频设备</p>
                <DsButton variant="ghost" size="sm" @click="refreshDevices">刷新</DsButton>
              </div>
              <div class="settings__stack">
                <DsField label="麦克风">
                  <DsSelect v-model="inputDeviceId" @change="selectInput(inputDeviceId)">
                    <option value="">系统默认</option>
                    <option v-for="device in inputDevices" :key="device.deviceId" :value="device.deviceId">
                      {{ device.label || "未命名麦克风" }}
                    </option>
                  </DsSelect>
                </DsField>
                <div class="audio-meter">
                  <DsMeter :value="micLevel * 100" label="输入电平" />
                  <DsButton variant="ghost" size="sm" @click="togglePreview">
                    {{ previewing ? "停止试听" : "试听电平" }}
                  </DsButton>
                </div>
                <DsField label="扬声器 / 耳机">
                  <DsSelect v-model="outputDeviceName" @change="selectOutput(outputDeviceName)">
                    <option value="">系统默认</option>
                    <option v-for="device in outputDevices" :key="device.id" :value="device.id">
                      {{ device.name }}{{ device.isDefault ? "（默认）" : "" }}
                    </option>
                  </DsSelect>
                </DsField>
                <DsField :label="`音量 ${Math.round(volume * 100)}%`">
                  <div class="audio-meter">
                    <input
                      v-model.number="volume"
                      class="range"
                      type="range"
                      min="0"
                      max="1"
                      step="0.05"
                      @input="applyVolume"
                    />
                    <DsButton variant="ghost" size="sm" @click="testOutput">试听</DsButton>
                  </div>
                </DsField>
                <p v-if="audioStatus" class="settings__hint">{{ friendly(audioStatus) }}</p>
              </div>
            </DsCard>
          </section>

          <section v-show="section === 'data'" class="settings__section">
            <DsCard>
              <DsSwitch
                v-model="settingsDraft.privacyMode"
                label="隐私模式"
                hint="禁止任何云端出网；本机环回地址不受影响"
              />
              <p v-if="privacyConflict || ttsPrivacyConflict || asrPrivacyConflict" class="settings__hint" data-tone="warn">
                当前有公网端点与隐私模式互斥：请关闭隐私模式，或把端点改成本机地址。
              </p>
            </DsCard>

            <DsCard>
              <p class="settings__label">导出与备份</p>
              <p class="settings__hint">
                导出包含对话原文、记忆与音色元数据；不含设置与云端 key。导入是合并语义。
              </p>
              <div class="settings__actions">
                <DsButton :disabled="dataBusy" @click="exportData">导出数据</DsButton>
                <DsButton :disabled="dataBusy" @click="backupNow">立即备份</DsButton>
                <DsButton :disabled="dataBusy" @click="exportDiagnostics">导出诊断包</DsButton>
              </div>
              <p v-if="exportPath" class="settings__hint">导出文件：{{ exportPath }}</p>
              <p v-if="diagnosticsPath" class="settings__hint">诊断包：{{ diagnosticsPath }}</p>
              <DsField label="导入文件路径（合并导入）">
                <div class="settings__key-row">
                  <DsInput v-model="importPath" placeholder="C:\Users\…\echoes-export-….json" />
                  <DsButton size="sm" :disabled="dataBusy || !importPath.trim()" @click="importData">导入</DsButton>
                </div>
              </DsField>
              <p v-if="dataStatus" class="settings__hint">{{ friendly(dataStatus) }}</p>
            </DsCard>

            <DsCard>
              <div class="settings__card-head">
                <p class="settings__label">备份</p>
                <DsButton variant="ghost" size="sm" @click="loadBackups">刷新</DsButton>
              </div>
              <ul v-if="backups.length" class="backup-list">
                <li v-for="backup in backups" :key="backup.path">
                  <span class="settings__hint">{{ backup.name }}</span>
                  <DsButton
                    variant="ghost"
                    size="sm"
                    :disabled="recoveryBusy"
                    @click="restoreBackup(backup.path)"
                  >
                    还原
                  </DsButton>
                </li>
              </ul>
              <p v-if="backupsStatus" class="settings__hint">{{ friendly(backupsStatus) }}</p>
              <p v-if="recoveryNotice" class="settings__hint">{{ recoveryNotice }}</p>
            </DsCard>

            <DsCard>
              <p class="settings__label">彻底删除</p>
              <p class="settings__hint">
                删除数据库、备份、音色样本与日志，并清除云端 key；不可撤销。
              </p>
              <DsField label="输入「删除全部数据」确认">
                <DsInput v-model="wipeConfirm" :disabled="wiped" />
              </DsField>
              <DsButton
                variant="danger"
                :disabled="dataBusy || wiped || !wipeConfirm.trim()"
                @click="wipeAll"
              >
                彻底删除
              </DsButton>
            </DsCard>
          </section>

          <section v-show="section === 'shortcuts'" class="settings__section">
            <DsCard>
              <div class="settings__stack">
                <DsSwitch
                  v-model="autostartEnabled"
                  label="开机自启"
                  hint="登录 Windows 后自动在托盘运行"
                  @update:model-value="toggleAutostart"
                />
                <DsSwitch
                  v-model="closeToTray"
                  label="关闭窗口时最小化到托盘"
                  hint="后台仍可被快捷键唤起"
                  @update:model-value="toggleCloseToTray"
                />
                <DsSwitch
                  v-model="notifyOnReply"
                  label="后台回复完成时发系统通知"
                  hint="窗口可见时不打扰"
                  @update:model-value="saveNotify"
                />
                <p v-if="autostartStatus" class="settings__hint">{{ friendly(autostartStatus) }}</p>
                <p v-if="closeToTrayStatus" class="settings__hint">{{ friendly(closeToTrayStatus) }}</p>
              </div>
            </DsCard>

            <DsCard>
              <div class="settings__stack">
                <DsField label="说话快捷键" hint="Tauri 加速键写法，例如 Alt+Space">
                  <div class="settings__key-row">
                    <DsInput v-model="pttShortcutDraft" placeholder="Alt+Space" @keydown.enter="applyPttShortcut" />
                    <DsButton
                      size="sm"
                      :disabled="!pttShortcutDraft.trim() || pttShortcutDraft.trim() === pttShortcut"
                      @click="applyPttShortcut"
                    >
                      应用
                    </DsButton>
                  </div>
                </DsField>
                <DsField :label="`${pttShortcut} 模式`">
                  <DsSelect v-model="pttMode" @change="savePttMode">
                    <option value="hold">按住说话</option>
                    <option value="toggle">按一下开始 / 再按停止</option>
                  </DsSelect>
                </DsField>
                <p v-if="pttShortcutStatus" class="settings__hint">{{ friendly(pttShortcutStatus) }}</p>
              </div>
            </DsCard>
          </section>

          <section v-show="section === 'about'" class="settings__section">
            <DsCard>
              <div class="settings__row">
                <div>
                  <p class="settings__label">版本</p>
                  <p class="settings__version">{{ version }}</p>
                </div>
                <DsButton @click="exportDiagnostics">导出诊断包</DsButton>
              </div>
              <p class="settings__hint">
                诊断包包含脱敏设置、日志与版本信息，不包含对话原文与云端 key。
              </p>
              <p v-if="diagnosticsPath" class="settings__hint">{{ diagnosticsPath }}</p>
            </DsCard>

            <DsCard>
              <p class="settings__label">维护</p>
              <p class="settings__hint">
                重置首启向导后，回到主窗口会重新检测机器、运行时和模型。
              </p>
              <DsButton @click="rerunSetup">重新运行首启向导</DsButton>
            </DsCard>

            <DsCard>
              <p class="settings__label">许可</p>
              <p class="settings__hint">
                Echoes 使用 MIT 许可的第三方组件；模型与音色许可见安装目录的 MODEL-LICENSES.md。
              </p>
            </DsCard>
          </section>
        </div>

        <footer class="settings__footer">
          <span v-if="profileStatus" class="settings__status">{{ friendly(profileStatus) }}</span>
          <span v-else class="settings__hint">保存后下一轮对话 / 下一次录音生效。</span>
          <div class="settings__footer-actions">
            <DsButton v-if="!inline" variant="ghost" @click="closeWindow">
              关闭
            </DsButton>
            <DsButton variant="primary" :loading="saving" @click="saveAll">
              保存设置
            </DsButton>
          </div>
        </footer>
      </main>
    </div>
  </DsSkin>
</template>

<style scoped>
.settings-skin {
  flex: 1;
  min-height: 0;
}

/* ---- 自绘标题栏：尺寸/配色与主窗口 AppTitleBar 对齐 ---- */
.settings__titlebar {
  display: flex;
  flex: none;
  height: var(--titlebar-h);
  align-items: center;
  border-bottom: 1px solid var(--rule);
  background: var(--surface);
  color: var(--ink-3);
  user-select: none;
  -webkit-user-select: none;
}

.settings__brand {
  padding-left: 12px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.28em;
  line-height: 1;
  text-transform: uppercase;
  pointer-events: none;
}

.settings__titlebar-divider {
  width: 1px;
  height: 12px;
  margin: 0 10px;
  background: var(--rule);
  pointer-events: none;
}

.settings__titlebar-label {
  flex: 1;
  color: var(--ink-2);
  font-size: 12px;
  pointer-events: none;
}

.settings__controls {
  display: flex;
  align-self: stretch;
}

.settings__ctrl {
  display: grid;
  place-items: center;
  width: 44px;
  color: var(--ink-2);
  transition:
    background-color var(--dur-hover) var(--ease),
    color var(--dur-hover) var(--ease);
}

.settings__ctrl:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.settings__ctrl:active {
  background: var(--rule);
}

.settings__ctrl--close:hover {
  background: var(--danger);
  color: var(--accent-ink);
}

.settings {
  display: grid;
  flex: 1;
  grid-template-columns: 180px minmax(0, 1fr);
  min-height: 0;
  background: var(--bg);
}

.settings__nav {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 0;
  padding: 8px 6px;
  border-right: 1px solid var(--rule);
  background: var(--surface);
}

.settings__nav-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 0;
  overflow-y: auto;
}

.settings__nav-bottom {
  flex: none;
  padding-top: 8px;
  border-top: 1px solid var(--rule);
}

.settings__nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 34px;
  padding: 0 8px;
  border-radius: var(--radius-control);
  color: var(--ink-2);
  font-size: 13px;
  text-align: left;
  white-space: nowrap;
  transition:
    background-color var(--dur-hover) var(--ease),
    color var(--dur-hover) var(--ease);
}

.settings__nav-item:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.settings__nav-item.is-on {
  background: var(--accent-soft);
  color: var(--accent);
}

.settings__nav-item.is-on::before {
  content: "";
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 2px;
  border-radius: 2px;
  background: var(--accent);
}

.settings__nav-icon {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  flex: none;
}

.settings__nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.settings__main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}

.settings__body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-3);
  width: 100%;
  max-width: 820px;
  min-height: 0;
  padding: var(--space-4) var(--space-6) var(--space-6);
  overflow-y: auto;
}

.settings__section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.settings__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.settings__stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.settings__label {
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

.settings__hint {
  color: var(--ink-3);
  font-size: 12px;
  line-height: 18px;
}

.settings__hint[data-tone="warn"] {
  color: var(--warn);
}

.settings__hint[data-tone="error"] {
  color: var(--danger);
}

.settings__card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.settings__chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin: var(--space-2) 0;
}

.settings__key-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.settings__key-row :deep(.ds-input) {
  flex: 1;
}

.settings__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.settings__status {
  color: var(--accent);
  font-size: 12px;
  line-height: 18px;
}

.settings__footer {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-6);
  border-top: 1px solid var(--rule);
  background: var(--surface);
}

.settings__footer-actions {
  display: flex;
  gap: var(--space-2);
}

.settings__version {
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 20px;
  line-height: 28px;
}

.theme-preview {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--rule);
  border-radius: var(--radius-card);
  background: var(--surface);
}

.theme-preview[data-preview="dark"] {
  border-color: #3a423e;
  background: #171c1a;
}

.theme-preview__name {
  color: var(--ink);
  font-family: var(--font-voice);
  font-size: 20px;
  line-height: 28px;
}

.theme-preview[data-preview="dark"] .theme-preview__name {
  color: #e8e9e3;
}

.theme-preview__meta {
  color: var(--ink-3);
  font-size: 11px;
}

.theme-preview__accent {
  width: 36px;
  height: 2px;
  margin-top: 4px;
  background: var(--accent);
}

.theme-preview[data-preview="dark"] .theme-preview__accent {
  background: #8fc3b0;
}

.model-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: var(--space-2) 0;
}

.model-list li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 24px;
  font-size: 12px;
}

.model-id {
  flex: 1;
  color: var(--ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-size {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
}

.model-ok {
  color: var(--ok);
}

.model-missing {
  color: var(--danger);
}

.voice-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: var(--space-2);
}

.voice-row {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  border-radius: var(--radius-control);
}

.voice-row:hover {
  background: var(--surface-2);
}

.voice-row.is-selected {
  background: var(--accent-soft);
}

.voice-row__main {
  display: flex;
  flex: 1;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
  padding: 8px;
  text-align: left;
}

.voice-row__radio {
  width: 14px;
  height: 14px;
  flex: none;
  border: 1px solid var(--rule-strong);
  border-radius: 50%;
  background: var(--raised);
}

.voice-row__radio.is-on {
  border: 4px solid var(--accent);
}

.voice-row__text {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.voice-row__name {
  color: var(--ink);
  font-size: 13px;
  line-height: 18px;
}

.voice-row__meta {
  color: var(--ink-3);
  font-size: 11px;
  line-height: 16px;
}

.voice-row__actions {
  display: flex;
  flex: none;
  gap: 0;
}

.audio-meter {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.audio-meter :deep(.ds-meter) {
  flex: 1;
}

.range {
  width: 100%;
  accent-color: var(--accent);
}

.backup-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.backup-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: 4px 0;
  border-bottom: 1px solid var(--rule);
}

@media (max-width: 680px) {
  .settings {
    grid-template-columns: 56px minmax(0, 1fr);
  }

  .settings__nav-item {
    justify-content: center;
    padding: 0;
    height: 38px;
  }

  .settings__nav-label {
    display: none;
  }

  .settings__nav-item.is-on::before {
    top: 6px;
    bottom: 6px;
  }

  .settings__body,
  .settings__footer {
    padding-left: var(--space-3);
    padding-right: var(--space-3);
  }
}
</style>
