<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import DsButton from "../ui/DsButton.vue";
import DsPttButton from "../ui/DsPttButton.vue";
import DsWaveform from "../ui/DsWaveform.vue";

const props = withDefaults(
  defineProps<{
    busy: boolean;
    listening: boolean;
    readOnly: boolean;
    pttDisabled: boolean;
    hint: string;
    engineState: string;
    micTone?: string;
    micNotice?: string;
    switchStatus?: string;
    canRetry?: boolean;
    historyFailures?: number;
    failedChainsCount?: number;
  }>(),
  {
    micTone: "",
    micNotice: "",
    switchStatus: "",
    canRetry: false,
    historyFailures: 0,
    failedChainsCount: 0,
  },
);

const emit = defineEmits<{
  send: [];
  pttStart: [];
  pttStop: [];
  resetReadOnly: [];
  openSettings: [];
  retry: [];
  edit: [];
}>();

const model = defineModel<string>({ default: "" });
const textarea = ref<HTMLTextAreaElement | null>(null);
const INPUT_MAX_H = 120;

function autosize(): void {
  const el = textarea.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, INPUT_MAX_H)}px`;
}

function focus(): void {
  void nextTick(() => {
    textarea.value?.focus();
    autosize();
  });
}

watch(model, () => {
  void nextTick(autosize);
});

function onKeydown(event: KeyboardEvent): void {
  if (event.key !== "Enter" || event.shiftKey) return;
  if (event.isComposing || event.keyCode === 229) return;
  event.preventDefault();
  emit("send");
}

const pttState = computed(() => {
  if (props.listening) return "listening" as const;
  if (props.busy) return "busy" as const;
  if (props.pttDisabled) return "disabled" as const;
  return "idle" as const;
});

const waveState = computed(() => {
  if (props.listening) return "listening" as const;
  if (props.engineState === "speaking") return "speaking" as const;
  if (props.engineState === "generating") return "thinking" as const;
  return "idle" as const;
});

const readOnlyMessage = computed(
  () =>
    `只读模式：引擎连续失败，暂时只能查看历史与记忆（${props.historyFailures} 次写入失败 / ${props.failedChainsCount} 条链不可用）。`,
);

defineExpose({ focus });
</script>

<template>
  <footer class="chat-composer">
    <div v-if="readOnly" class="chat-composer__readonly" role="status">
      <span>{{ readOnlyMessage }}</span>
      <DsButton variant="ghost" size="sm" @click="emit('openSettings')">
        去设置
      </DsButton>
      <DsButton variant="ghost" size="sm" @click="emit('resetReadOnly')">
        解除只读
      </DsButton>
    </div>

    <p v-if="switchStatus" class="chat-composer__switch">{{ switchStatus }}</p>

    <div class="chat-composer__bar">
      <DsPttButton
        :state="pttState"
        size="lg"
        label="按住说话"
        @start="emit('pttStart')"
        @stop="emit('pttStop')"
      />
      <textarea
        ref="textarea"
        v-model="model"
        class="chat-composer__input"
        rows="1"
        :placeholder="readOnly ? '只读模式：先修复引擎或解除只读' : '写点什么…'"
        aria-label="文字消息"
        autocomplete="off"
        :disabled="readOnly"
        @input="autosize"
        @keydown="onKeydown"
      ></textarea>
      <DsButton
        variant="primary"
        size="sm"
        :disabled="readOnly || model.trim() === ''"
        @click="emit('send')"
      >
        发送
      </DsButton>
    </div>

    <div class="chat-composer__hint">
      <DsWaveform :state="waveState" :bars="18" :height="12" />
      <span>{{ listening ? "正在听 · 松开发送" : hint }}</span>
    </div>

    <div v-if="canRetry" class="chat-composer__turn-actions">
      <DsButton variant="ghost" size="sm" @click="emit('retry')">重说</DsButton>
      <DsButton variant="ghost" size="sm" @click="emit('edit')">
        编辑上一条
      </DsButton>
    </div>

    <p v-if="micTone === 'warn'" class="chat-composer__mic-note">
      {{ micNotice }}
    </p>
  </footer>
</template>

<style scoped>
.chat-composer {
  display: flex;
  flex: none;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-6) var(--space-4);
  border-top: 1px solid var(--rule);
  background: var(--surface);
}

.chat-composer__readonly {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 10px;
  border: 1px solid color-mix(in srgb, var(--warn) 32%, var(--rule));
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--warn) 7%, var(--surface));
  color: var(--warn);
  font-size: 12px;
  line-height: 18px;
}

.chat-composer__readonly span {
  flex: 1;
  min-width: 220px;
}

.chat-composer__switch {
  color: var(--warn);
  font-size: 12px;
  line-height: 18px;
}

.chat-composer__bar {
  display: flex;
  align-items: flex-end;
  gap: var(--space-2);
  padding: 5px 5px 5px 8px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-card);
  background: var(--raised);
  transition: border-color var(--dur-hover) var(--ease);
}

.chat-composer__bar:focus-within {
  border-color: var(--accent);
}

.chat-composer__input {
  flex: 1;
  min-width: 0;
  max-height: 120px;
  padding: 7px 0;
  border: 0;
  background: transparent;
  color: var(--ink);
  font: inherit;
  font-size: 13px;
  line-height: 20px;
  resize: none;
  overflow-y: auto;
}

.chat-composer__input::placeholder {
  color: var(--ink-3);
}

.chat-composer__input:focus {
  outline: none;
}

.chat-composer__input:disabled {
  color: var(--ink-3);
}

.chat-composer__hint {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 16px;
  color: var(--ink-3);
  font-size: 12px;
  line-height: 16px;
}

.chat-composer__turn-actions {
  display: flex;
  gap: var(--space-2);
}

.chat-composer__mic-note {
  color: var(--warn);
  font-size: 11px;
  line-height: 16px;
}
</style>
