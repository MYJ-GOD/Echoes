<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: "ready" | "active" | "waiting" | "error" | "idle";
    label?: string;
  }>(),
  {
    tone: "idle",
    label: "",
  },
);
</script>

<template>
  <span class="ds-status" :class="`ds-status--${tone}`">
    <span class="ds-status__dot" aria-hidden="true"></span>
    <span v-if="label" class="ds-status__label">{{ label }}</span>
    <slot />
  </span>
</template>

<style scoped>
.ds-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-3);
  font-size: var(--text-meta);
  line-height: var(--text-meta-line);
  white-space: nowrap;
}

.ds-status__dot {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 50%;
  background: currentColor;
}

.ds-status--ready {
  color: var(--ok);
}

.ds-status--active {
  color: var(--accent);
}

.ds-status--active .ds-status__dot {
  animation: ds-status-pulse 1.8s ease-in-out infinite;
}

.ds-status--waiting {
  color: var(--warn);
}

.ds-status--error {
  color: var(--danger);
}

@keyframes ds-status-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.45;
    transform: scale(0.8);
  }
}
</style>
