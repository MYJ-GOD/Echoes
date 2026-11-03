<script setup lang="ts">
import DsButton from "../ui/DsButton.vue";
import type { ChatMessage } from "./types";

const props = withDefaults(
  defineProps<{
    message: ChatMessage;
    companionName: string;
    streaming?: boolean;
    isLast?: boolean;
    errorAction?: string;
  }>(),
  {
    streaming: false,
    isLast: false,
    errorAction: "",
  },
);

const emit = defineEmits<{ errorAction: [] }>();

function clock(at: number): string {
  return new Date(at).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

const isError = () => props.message.kind === "error";
</script>

<template>
  <li v-if="isError()" class="chat-notice">
    <p class="chat-notice__text">{{ message.text }}</p>
    <DsButton
      v-if="errorAction"
      variant="ghost"
      size="sm"
      @click="emit('errorAction')"
    >
      {{ errorAction }}
    </DsButton>
  </li>

  <li v-else class="chat-msg" :class="`chat-msg--${message.role}`">
    <div class="chat-msg__meta">
      <time>{{ clock(message.at) }}</time>
      <span>{{ message.role === "assistant" ? companionName : "你" }}</span>
    </div>
    <div class="chat-msg__body">
      <p class="chat-msg__text">
        {{ message.text }}<span
          v-if="streaming && isLast && message.role === 'assistant'"
          class="chat-msg__caret"
          aria-hidden="true"
        ></span>
      </p>
      <p v-if="message.interrupted" class="chat-msg__note">已打断</p>
    </div>
  </li>
</template>

<style scoped>
.chat-msg {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  gap: var(--space-3);
}

.chat-msg__meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 3px;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 16px;
  font-variant-numeric: tabular-nums;
}

.chat-msg__meta span {
  color: var(--ink-2);
}

.chat-msg__body {
  min-width: 0;
}

.chat-msg--assistant .chat-msg__body {
  padding-left: var(--space-3);
  border-left: 2px solid var(--accent);
}

.chat-msg--assistant .chat-msg__text {
  max-width: 62ch;
  color: var(--ink);
  font-family: var(--font-voice);
  font-size: var(--text-voice);
  line-height: var(--text-voice-line);
}

.chat-msg--user .chat-msg__body {
  justify-self: start;
  max-width: 72ch;
  padding: 8px 10px;
  border-radius: var(--radius-control);
  background: var(--surface-2);
}

.chat-msg--user .chat-msg__text {
  color: var(--ink-2);
  font-size: var(--text-body);
  line-height: var(--text-body-line);
}

.chat-msg__text {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.chat-msg__caret {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: -0.12em;
  background: var(--accent);
  animation: chat-caret 1s steps(2, start) infinite;
}

.chat-msg__note {
  margin-top: 4px;
  color: var(--ink-3);
  font-size: 11px;
  line-height: 15px;
}

.chat-notice {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, var(--danger) 32%, var(--rule));
  border-radius: var(--radius-control);
  background: color-mix(in srgb, var(--danger) 7%, var(--surface));
}

.chat-notice__text {
  color: var(--danger);
  font-size: 12px;
  line-height: 18px;
  overflow-wrap: anywhere;
}

@keyframes chat-caret {
  to {
    visibility: hidden;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chat-msg__caret {
    animation: none;
  }
}

@media (max-width: 700px) {
  .chat-msg {
    grid-template-columns: 48px minmax(0, 1fr);
    gap: var(--space-2);
  }
}
</style>
