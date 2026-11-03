<script setup lang="ts">
withDefaults(
  defineProps<{
    state?: "idle" | "listening" | "busy" | "disabled";
    size?: "sm" | "md" | "lg";
    label?: string;
  }>(),
  {
    state: "idle",
    size: "md",
    label: "按住说话",
  },
);

const emit = defineEmits<{ start: []; stop: [] }>();

function onDown(event: PointerEvent): void {
  if (event.button !== 0) return;
  (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
  emit("start");
}

function onUp(): void {
  emit("stop");
}

function onKeyDown(event: KeyboardEvent): void {
  if (event.code !== "Space" || event.repeat) return;
  event.preventDefault();
  emit("start");
}

function onKeyUp(event: KeyboardEvent): void {
  if (event.code !== "Space") return;
  event.preventDefault();
  emit("stop");
}
</script>

<template>
  <button
    type="button"
    class="ds-ptt"
    :class="[`ds-ptt--${size}`, `ds-ptt--${state}`]"
    :aria-label="state === 'listening' ? '松开发送' : label"
    :title="state === 'disabled' ? '引擎启动中' : label"
    :disabled="state === 'disabled'"
    @pointerdown.prevent="onDown"
    @pointerup="onUp"
    @pointercancel="onUp"
    @pointerleave="state === 'listening' && onUp()"
    @keydown="onKeyDown"
    @keyup="onKeyUp"
    @blur="state === 'listening' && onUp()"
  >
    <svg
      v-if="state === 'busy'"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
    <svg
      v-else
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.7"
      stroke-linecap="round"
      aria-hidden="true"
    >
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  </button>
</template>

<style scoped>
.ds-ptt {
  --ptt-size: var(--control-h);
  display: grid;
  place-items: center;
  width: var(--ptt-size);
  height: var(--ptt-size);
  flex: none;
  border: 1px solid var(--rule-strong);
  border-radius: 50%;
  background: var(--raised);
  color: var(--ink-2);
  touch-action: none;
  transition:
    background-color var(--dur-hover) var(--ease),
    border-color var(--dur-hover) var(--ease),
    color var(--dur-hover) var(--ease),
    transform var(--dur-hover) var(--ease);
}

.ds-ptt--sm {
  --ptt-size: var(--control-h-sm);
}

.ds-ptt--lg {
  --ptt-size: var(--control-h-lg);
}

.ds-ptt svg {
  width: 45%;
  height: 45%;
}

.ds-ptt:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.ds-ptt--listening,
.ds-ptt--busy {
  border-color: var(--signal);
  background: var(--signal);
  color: var(--accent-ink);
}

.ds-ptt--listening {
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--signal) 16%, transparent);
}

.ds-ptt--disabled {
  border-color: var(--rule);
  background: var(--surface-2);
  color: var(--ink-3);
  opacity: 1;
}

.ds-ptt:active:not(:disabled) {
  transform: scale(0.96);
}
</style>
