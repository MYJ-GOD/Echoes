<script setup lang="ts">
import { useSkinMode } from "../../composables/useSkinMode";

const { mode } = useSkinMode();

withDefaults(
  defineProps<{
    open: boolean;
    message: string;
    tone?: "info" | "success" | "error";
  }>(),
  {
    tone: "info",
  },
);

const emit = defineEmits<{ close: [] }>();
</script>

<template>
  <Teleport to="body">
    <Transition name="ds-toast">
      <div
        v-if="open"
        class="ds-toast"
        :class="`ds-toast--${tone}`"
        data-skin="next"
        :data-mode="mode"
        :role="tone === 'error' ? 'alert' : 'status'"
      >
        <span class="ds-toast__dot" aria-hidden="true"></span>
        <span class="ds-toast__message">{{ message }}</span>
        <button type="button" class="ds-toast__close" aria-label="关闭" @click="emit('close')">
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            aria-hidden="true"
          >
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.ds-toast {
  position: fixed;
  right: var(--space-6);
  bottom: var(--space-6);
  z-index: 120;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  max-width: min(360px, calc(100vw - 32px));
  padding: 10px 12px;
  border: 1px solid var(--rule);
  border-radius: var(--radius-card);
  background: var(--raised);
  color: var(--ink);
  box-shadow: var(--shadow-2);
  font-size: 13px;
  line-height: 18px;
}

.ds-toast__dot {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: var(--accent);
}

.ds-toast--success .ds-toast__dot {
  background: var(--ok);
}

.ds-toast--error .ds-toast__dot {
  background: var(--danger);
}

.ds-toast__message {
  flex: 1;
  min-width: 0;
}

.ds-toast__close {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  flex: none;
  border-radius: var(--radius-control);
  color: var(--ink-3);
}

.ds-toast__close:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.ds-toast-enter-active,
.ds-toast-leave-active {
  transition:
    opacity var(--dur-enter) var(--ease),
    transform var(--dur-enter) var(--ease);
}

.ds-toast-enter-from,
.ds-toast-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
