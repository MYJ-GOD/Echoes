<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import DsButton from "../components/ui/DsButton.vue";
import DsCard from "../components/ui/DsCard.vue";
import DsCheckbox from "../components/ui/DsCheckbox.vue";
import DsChip from "../components/ui/DsChip.vue";
import DsDialog from "../components/ui/DsDialog.vue";
import DsEmptyState from "../components/ui/DsEmptyState.vue";
import DsErrorState from "../components/ui/DsErrorState.vue";
import DsField from "../components/ui/DsField.vue";
import DsIconButton from "../components/ui/DsIconButton.vue";
import DsInput from "../components/ui/DsInput.vue";
import DsListRow from "../components/ui/DsListRow.vue";
import DsMeter from "../components/ui/DsMeter.vue";
import DsPttButton from "../components/ui/DsPttButton.vue";
import DsSegmented from "../components/ui/DsSegmented.vue";
import DsSelect from "../components/ui/DsSelect.vue";
import DsSkeleton from "../components/ui/DsSkeleton.vue";
import DsStatusDot from "../components/ui/DsStatusDot.vue";
import DsSwitch from "../components/ui/DsSwitch.vue";
import DsTextarea from "../components/ui/DsTextarea.vue";
import DsToast from "../components/ui/DsToast.vue";
import DsWaveform from "../components/ui/DsWaveform.vue";

const route = useRoute();
const mode = ref("light");
const density = ref("comfortable");
const themeOptions = [
  { value: "system", label: "跟随系统" },
  { value: "light", label: "浅色" },
  { value: "dark", label: "深色" },
];
const densityOptions = [
  { value: "comfortable", label: "舒适" },
  { value: "compact", label: "紧凑" },
];

const name = ref("Echoes");
const sampleText = ref("");
const invalidModel = ref("");
const checked = ref(true);
const switched = ref(true);
const voiceMode = ref("local");
const dialogOpen = ref(false);
const toastOpen = ref(false);
const toastMessage = ref("设置已保存");
const pttState = ref<"idle" | "listening" | "busy" | "disabled">("idle");
const meter = ref(42);

const colorTokens = [
  ["--bg", "背景"],
  ["--surface", "表面"],
  ["--surface-2", "次级表面"],
  ["--raised", "浮起"],
  ["--ink", "主文字"],
  ["--ink-2", "次文字"],
  ["--ink-3", "元信息"],
  ["--rule", "分隔线"],
  ["--accent", "主色"],
  ["--signal", "录音"],
  ["--ok", "就绪"],
  ["--warn", "警告"],
  ["--danger", "错误"],
];

function applySkin(): void {
  const root = document.documentElement;
  root.dataset.skin = "next";
  root.dataset.mode = mode.value;
  root.dataset.density = density.value;
}

function resetSkin(): void {
  const root = document.documentElement;
  delete root.dataset.skin;
  delete root.dataset.mode;
  delete root.dataset.density;
}

function pttStart(): void {
  pttState.value = "listening";
  meter.value = 78;
}

function pttStop(): void {
  pttState.value = "idle";
  meter.value = 12;
}

function showToast(message: string): void {
  toastMessage.value = message;
  toastOpen.value = true;
  window.setTimeout(() => {
    toastOpen.value = false;
  }, 3200);
}

watch([mode, density], applySkin);

watch(
  [() => route.query.mode, () => route.query.density],
  ([nextMode, nextDensity]) => {
    mode.value =
      nextMode === "dark" || nextMode === "system" || nextMode === "light"
        ? nextMode
        : "light";
    density.value = nextDensity === "compact" ? "compact" : "comfortable";
    applySkin();
  },
  { immediate: true },
);

onUnmounted(resetSkin);
</script>

<template>
  <div class="ds-page">
    <header class="ds-top">
      <div>
        <p class="ds-eyebrow">Design system · D1</p>
        <h1 class="ds-title">纸上回声 <span>/ Paper &amp; Signal</span></h1>
      </div>
      <div class="ds-top__controls">
        <DsSegmented v-model="mode" :options="themeOptions" label="主题" />
        <DsSegmented v-model="density" :options="densityOptions" label="密度" />
      </div>
    </header>

    <main class="ds-main">
      <section class="ds-sample" aria-label="对话示例">
        <div class="ds-sample__copy">
          <p class="ds-eyebrow">Signature · 回声线</p>
          <h2 class="ds-display">她还在听。</h2>
          <p class="ds-lede">
            按住空格说话，或者写一句。状态不是装饰：这条线会跟着“听 / 想 / 说”变化。
          </p>
          <DsWaveform state="listening" :bars="36" :height="34" />
          <div class="ds-row-gap">
            <DsChip selected>今天有点累</DsChip>
            <DsChip>讲个故事</DsChip>
            <DsChip>你还记得……</DsChip>
          </div>
        </div>

        <article class="ds-chat">
          <header class="ds-chat__head">
            <div class="ds-chat__id">
              <span class="ds-chat__name">{{ name || "Echoes" }}</span>
              <DsStatusDot tone="ready" label="就绪" />
            </div>
            <div class="ds-chat__tools">
              <DsChip>内置音色</DsChip>
              <DsIconButton label="更多">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <circle cx="5" cy="12" r="1.6" />
                  <circle cx="12" cy="12" r="1.6" />
                  <circle cx="19" cy="12" r="1.6" />
                </svg>
              </DsIconButton>
            </div>
          </header>

          <div class="ds-chat__thread">
            <div class="ds-msg ds-msg--her">
              <div class="ds-msg__meta">
                <time>09:41</time>
                <span>她</span>
              </div>
              <div class="ds-msg__body">
                <p>我还记得你说过，雨天喜欢听爵士。</p>
                <p>今天也下雨了。</p>
              </div>
            </div>
            <div class="ds-msg ds-msg--you">
              <div class="ds-msg__meta">
                <time>09:42</time>
                <span>你</span>
              </div>
              <div class="ds-msg__body">
                <p>放一首吧。</p>
              </div>
            </div>
          </div>

          <footer class="ds-chat__composer">
            <DsPttButton
              :state="pttState"
              label="按住说话"
              @start="pttStart"
              @stop="pttStop"
            />
            <input
              v-model="sampleText"
              class="ds-chat__input"
              type="text"
              placeholder="写点什么…"
              aria-label="示例输入"
            />
            <DsButton variant="primary" size="sm">发送</DsButton>
          </footer>
          <div class="ds-chat__hint">
            <DsWaveform :state="pttState === 'listening' ? 'listening' : 'idle'" :bars="18" :height="12" />
            <span>按住空格说话 · 松开发送</span>
          </div>
        </article>
      </section>

      <section class="ds-section">
        <div class="ds-section__head">
          <p class="ds-eyebrow">Color</p>
          <h2 class="ds-h2">冷纸、墨、深绿信号</h2>
          <p class="ds-lede">珊瑚只用于录音与停止；主色只用于选中、焦点与链接。</p>
        </div>
        <div class="ds-swatches">
          <div v-for="[token, label] in colorTokens" :key="token" class="ds-swatch">
            <span class="ds-swatch__chip" :style="{ background: `var(${token})` }"></span>
            <span class="ds-swatch__name">{{ label }}</span>
            <code class="ds-swatch__token">{{ token }}</code>
          </div>
        </div>
      </section>

      <section class="ds-section">
        <div class="ds-section__head">
          <p class="ds-eyebrow">Type</p>
          <h2 class="ds-h2">三个角色，一条尺度</h2>
        </div>
        <div class="ds-type">
          <div class="ds-type__row">
            <span class="ds-type__meta">Display · 24/32</span>
            <p class="ds-display">她还在听。</p>
          </div>
          <div class="ds-type__row">
            <span class="ds-type__meta">Title · 18/26</span>
            <p class="ds-h2">声音与人格</p>
          </div>
          <div class="ds-type__row">
            <span class="ds-type__meta">Voice · 16/27 · serif</span>
            <p class="ds-voice">我还记得你说过，雨天喜欢听爵士。今天也下雨了。</p>
          </div>
          <div class="ds-type__row">
            <span class="ds-type__meta">Body · 14/22</span>
            <p class="ds-body">只显示仍在生效的事实；被取代或删除的不再参与检索。</p>
          </div>
          <div class="ds-type__row">
            <span class="ds-type__meta">Meta · 12/16 · mono</span>
            <p class="ds-mono">qwen3:8b · 12ms · Ctrl+Shift+P</p>
          </div>
        </div>
      </section>

      <section class="ds-section">
        <div class="ds-section__head">
          <p class="ds-eyebrow">Controls</p>
          <h2 class="ds-h2">按钮、字段、选择</h2>
        </div>
        <div class="ds-grid">
          <DsCard>
            <p class="ds-label">按钮</p>
            <div class="ds-row-gap">
              <DsButton variant="primary">保存设置</DsButton>
              <DsButton>取消</DsButton>
              <DsButton variant="ghost">稍后</DsButton>
              <DsButton variant="danger">删除</DsButton>
            </div>
            <div class="ds-row-gap">
              <DsButton variant="primary" size="sm">小号</DsButton>
              <DsButton size="lg">大号</DsButton>
              <DsButton disabled>不可用</DsButton>
              <DsButton loading>保存中</DsButton>
            </div>
            <div class="ds-row-gap">
              <DsIconButton label="设置">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
                  <path d="M4 7h9M18 7h2M4 17h3M12 17h8" />
                  <circle cx="15.5" cy="7" r="2.2" />
                  <circle cx="9.5" cy="17" r="2.2" />
                </svg>
              </DsIconButton>
              <DsIconButton label="删除" tone="danger">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
                  <path d="M4 7h16M9 7V5h6v2M7 7l1 13h8l1-13" />
                </svg>
              </DsIconButton>
            </div>
          </DsCard>

          <DsCard>
            <p class="ds-label">字段</p>
            <div class="ds-stack">
              <DsField label="她的名字" hint="显示在对话页眉，最多 50 字">
                <DsInput v-model="name" placeholder="Echoes" />
              </DsField>
              <DsField label="系统提示词" hint="她是谁、怎么说话、记得什么">
                <DsTextarea v-model="sampleText" placeholder="她是谁、怎么说话、记得什么…" :rows="3" />
              </DsField>
              <DsField label="语音识别" hint="本地 whisper 不出本机">
                <DsSelect v-model="voiceMode">
                  <option value="local">本地 whisper</option>
                  <option value="cloud">云端 / 兼容端点</option>
                </DsSelect>
              </DsField>
              <DsField label="模型" error="模型名不能为空">
                <DsInput v-model="invalidModel" placeholder="qwen3:8b" invalid />
              </DsField>
            </div>
          </DsCard>

          <DsCard>
            <p class="ds-label">选择</p>
            <div class="ds-stack">
              <DsSegmented v-model="voiceMode" :options="[
                { value: 'local', label: '本地' },
                { value: 'cloud', label: '云端' },
              ]" label="引擎路径" />
              <DsCheckbox v-model="checked" label="隐私模式" hint="禁止任何云端出网" />
              <DsSwitch v-model="switched" label="关闭窗口时最小化到托盘" hint="后台仍可被快捷键唤起" />
              <div class="ds-row-gap">
                <DsChip selected>全部</DsChip>
                <DsChip>偏好</DsChip>
                <DsChip>身份</DsChip>
                <DsChip>事件</DsChip>
                <DsChip tone="ok">已连接</DsChip>
                <DsChip tone="warn">待切换</DsChip>
                <DsChip tone="danger">失败</DsChip>
              </div>
            </div>
          </DsCard>
        </div>
      </section>

      <section class="ds-section">
        <div class="ds-section__head">
          <p class="ds-eyebrow">States</p>
          <h2 class="ds-h2">空、错、加载、进度</h2>
        </div>
        <div class="ds-grid">
          <DsCard>
            <DsEmptyState title="聊得越多，这里越丰富。" description="她记住的事会自动出现在这里；也可以手动添加一条。">
              <DsButton variant="primary" size="sm">手动添加</DsButton>
              <DsButton size="sm">批量导入</DsButton>
            </DsEmptyState>
          </DsCard>
          <DsCard>
            <DsErrorState title="这次没接上。" description="可以重试，或去设置看看引擎。">
              <DsButton size="sm">重试</DsButton>
              <DsButton variant="ghost" size="sm">去设置</DsButton>
            </DsErrorState>
            <div class="ds-stack">
              <DsSkeleton width="60%" />
              <DsSkeleton width="100%" />
              <DsSkeleton width="82%" />
              <DsMeter :value="meter" label="麦克风电平" show-value />
              <DsMeter :value="72" label="克隆质量" tone="ok" show-value />
            </div>
          </DsCard>
          <DsCard>
            <p class="ds-label">列表行</p>
            <div class="ds-stack">
              <DsListRow title="今天 · 雨天和爵士" meta="09:42 · 12 轮" clickable selected />
              <DsListRow title="本周 · 关于搬家" meta="周三 21:10 · 8 轮" clickable>
                <template #leading>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
                    <path d="M4 5h16v14H4z" />
                    <path d="M4 9h16" />
                  </svg>
                </template>
              </DsListRow>
              <DsListRow title="更早 · 第一次见面" meta="10 月 12 日 · 24 轮" clickable />
            </div>
            <div class="ds-stack">
              <DsStatusDot tone="ready" label="就绪" />
              <DsStatusDot tone="active" label="正在说" />
              <DsStatusDot tone="waiting" label="等待引擎" />
              <DsStatusDot tone="error" label="出错" />
            </div>
          </DsCard>
        </div>
      </section>

      <section class="ds-section">
        <div class="ds-section__head">
          <p class="ds-eyebrow">Motion &amp; overlays</p>
          <h2 class="ds-h2">状态动效与浮层</h2>
          <p class="ds-lede">只动 transform / opacity；减少动效时全部静止。</p>
        </div>
        <DsCard>
          <div class="ds-row-gap">
            <DsButton @click="dialogOpen = true">打开对话框</DsButton>
            <DsButton variant="ghost" @click="showToast('设置已保存')">显示提示</DsButton>
            <DsButton variant="ghost" @click="showToast('这次没接上，可以重试。')">错误提示</DsButton>
          </div>
          <div class="ds-wave-row">
            <div class="ds-wave-row__item">
              <DsWaveform state="idle" :bars="24" :height="26" />
              <span class="ds-mono">idle</span>
            </div>
            <div class="ds-wave-row__item">
              <DsWaveform state="listening" :bars="24" :height="26" />
              <span class="ds-mono">listening</span>
            </div>
            <div class="ds-wave-row__item">
              <DsWaveform state="thinking" :bars="24" :height="26" />
              <span class="ds-mono">thinking</span>
            </div>
            <div class="ds-wave-row__item">
              <DsWaveform state="speaking" :bars="24" :height="26" />
              <span class="ds-mono">speaking</span>
            </div>
          </div>
        </DsCard>
      </section>

      <p class="ds-foot">
        D1 · primitive sandbox。P2 起把这套 token 挂到主窗口，P3 拆对话页。
      </p>
    </main>

    <DsDialog
      :open="dialogOpen"
      title="删除这段对话？"
      description="原文会从历史中移除；记忆里的事实不受影响。"
      @close="dialogOpen = false"
    >
      <p>这个动作不可撤销。</p>
      <template #footer>
        <DsButton variant="ghost" @click="dialogOpen = false">取消</DsButton>
        <DsButton variant="danger" data-autofocus @click="dialogOpen = false">删除</DsButton>
      </template>
    </DsDialog>

    <DsToast :open="toastOpen" :message="toastMessage" tone="info" @close="toastOpen = false" />
  </div>
</template>

<style scoped>
.ds-page {
  height: 100vh;
  overflow-y: auto;
  background: var(--bg);
  color: var(--ink);
}

.ds-top {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-6);
  padding: var(--space-5) var(--space-8);
  border-bottom: 1px solid var(--rule);
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(12px);
}

.ds-top__controls {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.ds-main {
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: var(--space-8) var(--space-8) var(--space-12);
}

.ds-eyebrow {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  line-height: 16px;
  text-transform: uppercase;
}

.ds-title {
  margin-top: var(--space-1);
  color: var(--ink);
  font-size: 22px;
  font-weight: 600;
  line-height: 30px;
}

.ds-title span {
  color: var(--ink-3);
  font-weight: 400;
}

.ds-display {
  color: var(--ink);
  font-family: var(--font-voice);
  font-size: var(--text-display);
  line-height: var(--text-display-line);
}

.ds-h2 {
  color: var(--ink);
  font-size: var(--text-title);
  font-weight: 600;
  line-height: var(--text-title-line);
}

.ds-lede,
.ds-body {
  color: var(--ink-2);
  font-size: var(--text-body);
  line-height: var(--text-body-line);
}

.ds-voice {
  max-width: 58ch;
  color: var(--ink);
  font-family: var(--font-voice);
  font-size: var(--text-voice);
  line-height: var(--text-voice-line);
}

.ds-mono {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 16px;
  font-variant-numeric: tabular-nums;
}

.ds-label {
  margin-bottom: var(--space-3);
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.ds-sample {
  display: grid;
  grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
  gap: var(--space-8);
  align-items: stretch;
  padding-bottom: var(--space-10);
  border-bottom: 1px solid var(--rule);
}

.ds-sample__copy {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  justify-content: center;
  padding: var(--space-6) 0;
}

.ds-row-gap {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
}

.ds-chat {
  display: flex;
  flex-direction: column;
  min-height: 380px;
  border: 1px solid var(--rule);
  border-radius: var(--radius-card);
  background: var(--surface);
  box-shadow: var(--shadow-1);
}

.ds-chat__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--rule);
}

.ds-chat__id,
.ds-chat__tools {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.ds-chat__name {
  color: var(--ink);
  font-size: 14px;
  font-weight: 600;
}

.ds-chat__thread {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-5);
  padding: var(--space-5) var(--space-5) var(--space-3);
  overflow-y: auto;
}

.ds-msg {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: var(--space-3);
}

.ds-msg__meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 3px;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 15px;
}

.ds-msg__meta span {
  color: var(--ink-2);
}

.ds-msg--her .ds-msg__body {
  padding-left: var(--space-3);
  border-left: 2px solid var(--accent);
}

.ds-msg--her .ds-msg__body p {
  color: var(--ink);
  font-family: var(--font-voice);
  font-size: var(--text-voice);
  line-height: var(--text-voice-line);
}

.ds-msg--you .ds-msg__body {
  display: inline-block;
  justify-self: start;
  padding: 8px 10px;
  border-radius: var(--radius-control);
  background: var(--surface-2);
}

.ds-msg--you .ds-msg__body p {
  color: var(--ink-2);
  font-size: var(--text-body);
  line-height: var(--text-body-line);
}

.ds-chat__composer {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin: 0 var(--space-4) var(--space-2);
  padding: 5px 5px 5px 8px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-card);
  background: var(--raised);
}

.ds-chat__input {
  flex: 1;
  min-width: 0;
  height: var(--control-h);
  border: 0;
  background: transparent;
  color: var(--ink);
  font-size: 13px;
}

.ds-chat__input::placeholder {
  color: var(--ink-3);
}

.ds-chat__input:focus {
  outline: none;
}

.ds-chat__hint {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-4) var(--space-3);
  color: var(--ink-3);
  font-size: 11px;
}

.ds-section {
  padding: var(--space-8) 0;
  border-bottom: 1px solid var(--rule);
}

.ds-section__head {
  margin-bottom: var(--space-5);
}

.ds-section__head .ds-h2 {
  margin: var(--space-1) 0 var(--space-2);
}

.ds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--space-4);
  align-items: start;
}

.ds-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.ds-swatches {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: var(--space-3);
}

.ds-swatch {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ds-swatch__chip {
  display: block;
  height: 46px;
  margin-bottom: var(--space-1);
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-control);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--bg) 40%, transparent);
}

.ds-swatch__name {
  color: var(--ink);
  font-size: 12px;
}

.ds-swatch__token {
  color: var(--ink-3);
  font-size: 11px;
}

.ds-type {
  display: grid;
  gap: var(--space-4);
}

.ds-type__row {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: var(--space-4);
  align-items: baseline;
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--rule);
}

.ds-type__meta {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 11px;
}

.ds-wave-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
  margin-top: var(--space-5);
}

.ds-wave-row__item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.ds-foot {
  padding-top: var(--space-6);
  color: var(--ink-3);
  font-size: 12px;
}

@media (max-width: 900px) {
  .ds-top {
    align-items: flex-start;
    flex-direction: column;
    padding: var(--space-4);
  }

  .ds-main {
    padding: var(--space-4);
  }

  .ds-sample {
    grid-template-columns: 1fr;
  }

  .ds-type__row {
    grid-template-columns: 1fr;
    gap: var(--space-1);
  }
}
</style>
