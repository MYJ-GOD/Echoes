<script setup lang="ts">
import { computed, onMounted } from "vue";

import PageHeader from "../components/layout/PageHeader.vue";
import DsButton from "../components/ui/DsButton.vue";
import DsCard from "../components/ui/DsCard.vue";
import DsEmptyState from "../components/ui/DsEmptyState.vue";
import DsErrorState from "../components/ui/DsErrorState.vue";
import DsSkin from "../components/ui/DsSkin.vue";
import DsStatusDot from "../components/ui/DsStatusDot.vue";
import { useSettings } from "../composables/useSettings";
import * as ipc from "../lib/ipc";

const {
  voices,
  voicesStatus,
  voiceBusy,
  selectedVoiceName,
  clonedVoiceCount,
  VOICE_LIMIT,
  hasClonedVoice,
  loadVoices,
  chooseVoice,
  renameVoiceItem,
  deleteVoiceItem,
  voiceLabel,
} = useSettings();

const current = computed(() => voices.value.find((voice) => voice.selected));

onMounted(() => {
  void loadVoices();
});

async function openSettings(): Promise<void> {
  try {
    await ipc.openSettingsWindow();
  } catch {
    // 设置窗口由左侧入口兜底；这里不重复实现抽屉。
  }
}

function tone(status: string): "ready" | "waiting" | "error" {
  if (status === "ready") return "ready";
  if (status === "training") return "waiting";
  return "error";
}

function statusLabel(status: string): string {
  if (status === "ready") return "可用";
  if (status === "training") return "准备中";
  if (status === "failed") return "失败";
  return status;
}
</script>

<template>
  <DsSkin class="voice-skin">
      <PageHeader
        title="声音"
        description="当前音色会被新回复使用；失败时明确报错，不会静默换成内置音色。"
      >
        <template #actions>
          <DsButton :disabled="voiceBusy !== ''" @click="loadVoices">刷新</DsButton>
          <DsButton variant="primary" @click="openSettings">管理 / 克隆</DsButton>
        </template>
      </PageHeader>

      <main class="voice-page">
        <DsCard padding="lg" class="voice__current">
          <div>
            <p class="voice__eyebrow">当前音色</p>
            <p class="voice__name">{{ selectedVoiceName }}</p>
            <p class="voice__meta">
              {{ current?.id === "builtin:default" ? "内置音色" : "克隆 / 云端音色" }}
              · 已用 {{ clonedVoiceCount }} / {{ VOICE_LIMIT }}
            </p>
          </div>
          <DsStatusDot
            :tone="current?.status === 'ready' ? 'ready' : 'waiting'"
            :label="current ? statusLabel(current.status) : '读取中'"
          />
        </DsCard>

        <DsErrorState
          v-if="voicesStatus"
          title="读取音色失败。"
          description="确认 sidecar 已启动，然后刷新。"
        >
          <DsButton size="sm" @click="loadVoices">重试</DsButton>
        </DsErrorState>

        <section class="voice__list" aria-label="音色列表">
          <p class="voice__section">全部音色</p>
          <div
            v-for="voice in voices"
            :key="voice.id"
            class="vrow"
            :class="{ 'is-selected': voice.selected }"
          >
            <button
              type="button"
              class="vrow__main"
              :disabled="voice.status !== 'ready' || voiceBusy !== ''"
              @click="chooseVoice(voice.id)"
            >
              <span class="vrow__radio" :class="{ 'is-on': voice.selected }" aria-hidden="true"></span>
              <span class="vrow__text">
                <span class="vrow__name">{{ voice.displayName }}</span>
                <span class="vrow__meta">{{ voiceLabel(voice) }}</span>
              </span>
              <DsStatusDot :tone="tone(voice.status)" :label="statusLabel(voice.status)" />
            </button>

            <span
              v-if="voice.id !== 'builtin:default' && !voice.id.startsWith('openai:')"
              class="vrow__actions"
            >
              <DsButton variant="ghost" size="sm" :disabled="voiceBusy !== ''" @click="renameVoiceItem(voice)">
                改名
              </DsButton>
              <DsButton variant="ghost" size="sm" :disabled="voiceBusy !== ''" @click="deleteVoiceItem(voice)">
                删除
              </DsButton>
            </span>
          </div>

          <DsEmptyState
            v-if="voices.length === 0 && !voicesStatus"
            title="先用内置音色，或克隆一个。"
            description="克隆会用本机麦克风录 3–6 秒；样本与音色只留在本机。"
          >
            <DsButton variant="primary" size="sm" @click="openSettings">打开设置</DsButton>
          </DsEmptyState>
        </section>

        <DsCard padding="lg" class="voice__clone">
          <div>
            <p class="voice__section">克隆我的音色</p>
            <p class="voice__meta">
              录音、样本校验和相似度质检在设置窗口完成；低于阈值会被拒绝，不会绑定到会话。
            </p>
          </div>
          <DsButton :disabled="voiceBusy !== ''" @click="openSettings">
            {{ hasClonedVoice ? "重新克隆" : "开始克隆" }}
          </DsButton>
        </DsCard>
      </main>
  </DsSkin>
</template>

<style scoped>
.voice-skin {
  flex: 1;
  min-height: 0;
}

.voice-page {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 0;
  width: min(820px, 100%);
  padding: var(--space-6);
  overflow-y: auto;
}

.voice__current {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.voice__eyebrow,
.voice__section {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  line-height: 14px;
  text-transform: uppercase;
}

.voice__name {
  margin-top: 4px;
  color: var(--ink);
  font-family: var(--font-voice);
  font-size: 22px;
  line-height: 30px;
}

.voice__meta {
  margin-top: 2px;
  color: var(--ink-2);
  font-size: 12px;
  line-height: 18px;
}

.voice__list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.voice__section {
  padding: var(--space-2) 2px 4px;
}

.vrow {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  border-radius: var(--radius-control);
  transition: background-color var(--dur-hover) var(--ease);
}

.vrow:hover {
  background: var(--surface-2);
}

.vrow.is-selected {
  background: var(--accent-soft);
}

.vrow__main {
  display: flex;
  flex: 1;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
  padding: 10px 8px;
  text-align: left;
}

.vrow__main:disabled {
  cursor: default;
}

.vrow__radio {
  width: 14px;
  height: 14px;
  flex: none;
  border: 1px solid var(--rule-strong);
  border-radius: 50%;
  background: var(--raised);
}

.vrow__radio.is-on {
  border: 4px solid var(--accent);
}

.vrow__text {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.vrow__name {
  color: var(--ink);
  font-size: 13px;
  line-height: 18px;
}

.vrow__meta {
  color: var(--ink-3);
  font-size: 11px;
  line-height: 16px;
}

.vrow__actions {
  display: flex;
  flex: none;
  gap: 0;
  opacity: 0;
  transition: opacity var(--dur-hover) var(--ease);
}

.vrow:hover .vrow__actions,
.vrow:focus-within .vrow__actions {
  opacity: 1;
}

.voice__clone {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

@media (max-width: 900px) {
  .vrow__actions {
    opacity: 1;
  }
}
</style>
