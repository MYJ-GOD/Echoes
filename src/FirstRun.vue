<script setup lang="ts">
/**
 * 首启向导（ADR-011/016）：检测 → 准备运行环境 → 选 LLM。
 *
 * 数据面全部走壳命令：探测与下载由 sidecar 的一次性 `--setup` 进程完成，
 * 进度经 `setup://event` 推来；本组件只管呈现与写设置。
 */
import { computed, onMounted, onUnmounted, ref } from "vue";
import type { UnlistenFn } from "@tauri-apps/api/event";

import * as ipc from "./lib/ipc";

const emit = defineEmits<{ done: [] }>();

const MODEL_LABELS: Record<string, string> = {
  "faster-whisper-small": "语音识别 · Whisper small",
  "bge-small-zh-v1.5": "记忆 · bge 中文嵌入",
  "cosyvoice2-0.5b": "声音 · CosyVoice2 0.5B",
};

const step = ref<"detect" | "install" | "llm">("detect");
const report = ref<ipc.SetupReport | null>(null);
const detectError = ref("");
const profile = ref("cpu");

const installing = ref(false);
const installError = ref("");
const runtimePct = ref(0);
const modelPct = ref<Record<string, number>>({});
const installNote = ref("");

const settings = ref<ipc.SettingsView | null>(null);
const provider = ref<"ollama" | "openai">("ollama");
const model = ref("qwen3:8b");
const baseUrl = ref("");
const key = ref("");
const saving = ref(false);
const saveError = ref("");

let unlisten: UnlistenFn | null = null;

const gpu = computed(() => report.value?.gpu ?? null);
const runtimeNeeded = computed(() => {
  const r = report.value;
  if (!r) return false;
  return r.needsRuntime;
});
const runtimeSizeGb = computed(() =>
  profile.value === "cuda126" ? 3.5 : 1.2
);
const weightsMb = computed(() => {
  const r = report.value;
  if (!r) return 0;
  // 权重体积按清单：whisper 461 + bge 95 + cosyvoice 3800
  const known: Record<string, number> = {
    "faster-whisper-small": 461,
    "bge-small-zh-v1.5": 95,
    "cosyvoice2-0.5b": 3800,
  };
  return r.missingModels.reduce((sum, id) => sum + (known[id] ?? 0), 0);
});
const readyHint = computed(() => {
  const r = report.value;
  if (!r) return "";
  if (r.devVenv) return "开发环境：直接使用 sidecar/.venv，跳过运行时下载。";
  if (r.activeProfile) return `运行时已安装：${r.activeProfile}。`;
  return `需要下载运行时（约 ${runtimeSizeGb.value}GB）与权重。`;
});

onMounted(async () => {
  unlisten = await ipc.onSetupEvent((event) => {
    if (event.type === "progress") {
      if (event.step === "runtime") {
        runtimePct.value = event.pct;
      } else {
        modelPct.value = { ...modelPct.value, [event.item]: event.pct };
      }
    }
  });
  await detect();
  try {
    settings.value = await ipc.getSettings();
    baseUrl.value = settings.value.baseUrl;
    if (settings.value.provider === "openai") {
      provider.value = "openai";
      model.value = settings.value.model;
    }
  } catch {
    // 设置读不到不阻塞向导：完成时用默认值
  }
});

async function detect(): Promise<void> {
  detectError.value = "";
  report.value = null;
  try {
    const result = await ipc.setupDetect();
    if (result.type === "detect") {
      report.value = result.report;
      profile.value = result.report.recommendedProfile;
    } else if (result.type === "error") {
      detectError.value = result.message;
    }
  } catch (err) {
    detectError.value = String(err);
  }
}

onUnmounted(() => {
  unlisten?.();
});

async function startInstall(): Promise<void> {
  step.value = "install";
  installing.value = true;
  installError.value = "";
  installNote.value = "";
  const current = report.value;
  try {
    if (current && runtimeNeeded.value) {
      const result = await ipc.setupInstall("install-runtime", {
        profile: profile.value,
      });
      if (result.type === "error") {
        installError.value = `${result.code}：${result.message}`;
      }
    }
    if (current && current.missingModels.length > 0) {
      const result = await ipc.setupInstall("install-models", {
        ids: current.missingModels,
      });
      if (result.type === "error") {
        installError.value = `${result.code}：${result.message}`;
      } else if (result.type === "result" && result.detail) {
        const failed = Object.entries(result.detail)
          .filter(([, status]) => status !== "installed" && status !== "already")
          .map(([id]) => MODEL_LABELS[id] ?? id);
        if (failed.length > 0) {
          installNote.value = `部分权重没装成：${failed.join("、")}（可重试）`;
        }
      }
    }
  } catch (err) {
    installError.value = String(err);
  } finally {
    installing.value = false;
  }
}

function resumeLater(): void {
  step.value = "llm";
}

async function finish(skip = false): Promise<void> {
  saving.value = true;
  saveError.value = "";
  try {
    if (!skip) {
      const base: ipc.SettingsView =
        settings.value ??
        ({
          provider: "ollama",
          model: "qwen3:8b",
          privacyMode: true,
          baseUrl: "",
          hasKey: false,
          firstRunDone: false,
        } satisfies ipc.SettingsView);
      const payload: ipc.SettingsView = {
        ...base,
        provider: provider.value,
        model: model.value.trim() || "qwen3:8b",
        baseUrl: provider.value === "openai" ? baseUrl.value.trim() : "",
        privacyMode: provider.value !== "openai",
      };
      await ipc.saveSettings(payload);
      if (provider.value === "openai" && key.value.trim() !== "") {
        await ipc.saveLlmKey(key.value.trim());
      }
    }
    await ipc.completeSetup();
    emit("done");
  } catch (err) {
    saveError.value = String(err);
  } finally {
    saving.value = false;
  }
}

function pctOf(id: string): number {
  return modelPct.value[id] ?? 0;
}
</script>

<template>
  <div class="setup" role="dialog" aria-modal="true" aria-label="首次启动设置">
    <div class="page">
      <header class="head">
        <p class="eyebrow">Echoes · 初次见面</p>
        <h1 v-if="step === 'detect'">先看看这台机器</h1>
        <h1 v-else-if="step === 'install'">准备运行环境</h1>
        <h1 v-else>她从哪里思考</h1>
        <p v-if="step === 'detect'" class="lede">
          本体已经装好了。语音识别、声音和记忆都在这台机器上跑，只下载它们需要的东西。
        </p>
        <p v-else-if="step === 'install'" class="lede">
          下载可以中断重来；装好的部分不会重复下载。
        </p>
        <p v-else class="lede">
          声音与记忆始终留在本机。只有「想」这一步可以交给云端，或者同样留在本机。
        </p>
      </header>

      <!-- 第一步：检测 -->
      <section v-if="step === 'detect'" class="body">
        <p v-if="detectError" class="error">
          {{ detectError }}
          <button type="button" class="quiet" @click="detect">重试</button>
        </p>
        <p v-else-if="!report" class="note">正在检查硬件与依赖…</p>

        <template v-else>
          <dl class="specs">
            <div>
              <dt>处理器</dt>
              <dd>{{ report.cpu }}</dd>
            </div>
            <div>
              <dt>内存</dt>
              <dd>{{ report.ramGb ?? "—" }} GB</dd>
            </div>
            <div>
              <dt>显卡</dt>
              <dd>
                <template v-if="report.gpu">
                  {{ report.gpu.name }} · {{ report.gpu.vramGb }} GB
                </template>
                <template v-else>未检测到 NVIDIA 显卡</template>
              </dd>
            </div>
            <div>
              <dt>磁盘可用</dt>
              <dd>{{ report.diskFreeGb }} GB</dd>
            </div>
            <div>
              <dt>Ollama</dt>
              <dd>
                {{
                  report.ollama.reachable
                    ? `运行中 · ${report.ollama.models.length} 个模型`
                    : "未运行（可选）"
                }}
              </dd>
            </div>
          </dl>

          <div class="choice">
            <p class="label">运行时档位</p>
            <div class="options">
              <button
                type="button"
                class="option"
                :class="{ on: profile === 'cuda126' }"
                :disabled="!gpu"
                @click="profile = 'cuda126'"
              >
                <span>CUDA 12.6</span>
                <span class="sub">约 3.5GB · 推荐给 6GB 以上显存</span>
              </button>
              <button
                type="button"
                class="option"
                :class="{ on: profile === 'cpu' }"
                @click="profile = 'cpu'"
              >
                <span>CPU</span>
                <span class="sub">约 1.2GB · 慢，但哪台机器都能跑</span>
              </button>
            </div>
          </div>

          <p class="note">{{ readyHint }}</p>
          <p class="note">
            待下载：运行时
            {{ runtimeNeeded ? `约 ${runtimeSizeGb}GB` : "（已就绪）" }} + 权重约
            {{ (weightsMb / 1024).toFixed(1) }}GB
          </p>
          <ul v-if="report.notes.length" class="notes">
            <li v-for="note in report.notes" :key="note">{{ note }}</li>
          </ul>
        </template>

        <footer class="actions">
          <button
            type="button"
            class="primary"
            :disabled="!report || installing"
            @click="startInstall"
          >
            开始准备
          </button>
          <button type="button" class="quiet" @click="finish(true)">
            稍后再说（只能打字）
          </button>
        </footer>
      </section>

      <!-- 第二步：下载 -->
      <section v-else-if="step === 'install'" class="body">
        <ul class="tasks">
          <li v-if="runtimeNeeded" class="task">
            <div class="task-head">
              <span>运行时 · {{ profile }}</span>
              <span class="pct">{{ runtimePct }}%</span>
            </div>
            <div class="meter">
              <span class="fill" :style="{ width: `${runtimePct}%` }"></span>
            </div>
          </li>
          <li
            v-for="id in report?.missingModels ?? []"
            :key="id"
            class="task"
          >
            <div class="task-head">
              <span>{{ MODEL_LABELS[id] ?? id }}</span>
              <span class="pct">{{ pctOf(id) }}%</span>
            </div>
            <div class="meter">
              <span class="fill" :style="{ width: `${pctOf(id)}%` }"></span>
            </div>
          </li>
        </ul>

        <p v-if="installing" class="note">正在下载，完成后才能使用语音…</p>
        <p v-if="installError" class="error">{{ installError }}</p>
        <p v-if="installNote" class="note" data-tone="warn">{{ installNote }}</p>
        <p v-if="!runtimeNeeded && (report?.missingModels.length ?? 0) === 0" class="note">
          运行环境已经齐了。
        </p>

        <footer class="actions">
          <button type="button" class="primary" :disabled="installing" @click="resumeLater">
            下一步
          </button>
          <button v-if="installing" type="button" class="quiet" @click="resumeLater">
            后台继续，先去配置
          </button>
        </footer>
      </section>

      <!-- 第三步：LLM -->
      <section v-else class="body">
        <div class="options">
          <button
            type="button"
            class="option"
            :class="{ on: provider === 'ollama' }"
            @click="provider = 'ollama'"
          >
            <span>本地 Ollama</span>
            <span class="sub">不出网，需要本机已安装 Ollama</span>
          </button>
          <button
            type="button"
            class="option"
            :class="{ on: provider === 'openai' }"
            @click="provider = 'openai'"
          >
            <span>云端 API key</span>
            <span class="sub">DeepSeek / Kimi / 硅基流动 / OpenAI 兼容</span>
          </button>
        </div>

        <template v-if="provider === 'ollama'">
          <label class="field">
            <span>模型</span>
            <input v-model="model" type="text" maxlength="100" placeholder="qwen3:8b" />
          </label>
          <p class="note">
            没装 Ollama？到 ollama.com 安装后执行
            <code>ollama pull {{ model || "qwen3:8b" }}</code>，再回来选它。
          </p>
        </template>

        <template v-else>
          <label class="field">
            <span>Base URL</span>
            <input
              v-model="baseUrl"
              type="text"
              maxlength="300"
              placeholder="https://api.deepseek.com/v1"
            />
          </label>
          <label class="field">
            <span>模型</span>
            <input v-model="model" type="text" maxlength="100" placeholder="deepseek-chat" />
          </label>
          <label class="field">
            <span>API key</span>
            <input v-model="key" type="password" autocomplete="off" placeholder="sk-…" />
          </label>
          <p class="note">
            key 存 Windows 凭据管理器，不进数据库；云端模式下隐私模式会自动关闭——
            对话内容会经该 API。
          </p>
        </template>

        <p v-if="saveError" class="error">{{ saveError }}</p>

        <footer class="actions">
          <button type="button" class="primary" :disabled="saving" @click="finish()">
            开始陪伴
          </button>
          <button type="button" class="quiet" :disabled="saving" @click="finish(true)">
            先用默认设置
          </button>
        </footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.setup {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 24px;
  overflow-y: auto;
  background: radial-gradient(
    120% 80% at 50% 0%,
    var(--paper-hi) 0%,
    var(--paper) 62%
  );
}

.page {
  width: min(560px, 100%);
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 28px 30px 24px;
  border: 1px solid var(--rule);
  border-radius: 4px;
  background: var(--paper-hi);
  box-shadow: 0 18px 48px rgba(35, 32, 27, 0.08);
}

.eyebrow {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.26em;
  text-transform: uppercase;
  color: var(--ink-3);
}

h1 {
  margin-top: 4px;
  font-family: var(--font-voice);
  font-size: 26px;
  font-weight: 400;
}

.lede {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--ink-2);
}

.body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.specs {
  display: grid;
  gap: 0;
  border-top: 1px solid var(--rule);
}

.specs > div {
  display: grid;
  grid-template-columns: 84px 1fr;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--rule);
}

dt {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--ink-3);
  padding-top: 2px;
}

dd {
  font-size: 13px;
  color: var(--ink);
  overflow-wrap: anywhere;
}

.choice {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.label {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--ink-2);
}

.options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.option {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 10px 12px;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: #fffdf9;
  text-align: left;
  transition:
    border-color 0.16s ease,
    background 0.16s ease;
}

.option:hover:not(:disabled) {
  border-color: var(--rule-strong);
}

.option.on {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.option:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.option span:first-child {
  font-size: 13.5px;
  color: var(--ink);
}

.sub {
  font-size: 11px;
  line-height: 1.5;
  color: var(--ink-3);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
  color: var(--ink-2);
}

.field input {
  padding: 8px 10px;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: #fffdf9;
  font-size: 13.5px;
  color: var(--ink);
}

.field input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.note {
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--ink-3);
}

.note[data-tone="warn"] {
  color: var(--accent);
}

.notes {
  margin: 0;
  padding-left: 16px;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--ink-3);
}

.error {
  padding: 8px 10px;
  border-left: 2px solid var(--danger);
  border-radius: 0 6px 6px 0;
  background: rgba(158, 59, 46, 0.05);
  font-size: 12px;
  line-height: 1.6;
  color: var(--danger);
  overflow-wrap: anywhere;
}

.tasks {
  display: flex;
  flex-direction: column;
  gap: 12px;
  list-style: none;
}

.task {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  font-size: 12.5px;
  color: var(--ink-2);
}

.pct {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-3);
}

.meter {
  height: 3px;
  border-radius: 2px;
  background: var(--paper-lo);
  overflow: hidden;
}

.fill {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 0.3s ease;
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 4px;
}

.primary {
  padding: 9px 18px;
  border-radius: 8px;
  background: var(--ink);
  color: var(--paper-hi);
  font-size: 12.5px;
  letter-spacing: 0.04em;
  transition: background 0.18s ease;
}

.primary:hover:not(:disabled) {
  background: var(--accent);
}

.primary:disabled {
  opacity: 0.5;
  cursor: default;
}

.quiet {
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--ink-3);
}

.quiet:hover:not(:disabled) {
  color: var(--accent);
  background: var(--accent-soft);
}

code {
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--paper-lo);
  font-family: var(--font-mono);
  font-size: 0.94em;
}

@media (max-width: 560px) {
  .options {
    grid-template-columns: 1fr;
  }

  .page {
    padding: 22px 20px 18px;
  }
}
</style>
