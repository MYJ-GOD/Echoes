<script setup lang="ts">
withDefaults(
  defineProps<{
    selected?: boolean;
    tone?: "neutral" | "accent" | "ok" | "warn" | "danger";
    disabled?: boolean;
  }>(),
  {
    selected: false,
    tone: "neutral",
    disabled: false,
  },
);

defineEmits<{ click: [event: MouseEvent] }>();
</script>

<template>
  <button
    type="button"
    class="ds-chip"
    :class="[`ds-chip--${tone}`, { 'is-selected': selected }]"
    :aria-pressed="selected"
    :disabled="disabled"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>

<style scoped>
.ds-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: var(--control-h-sm);
  padding: 0 10px;
  border: 1px solid var(--rule);
  border-radius: var(--radius-pill);
  background: var(--surface);
  color: var(--ink-2);
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  transition:
    background-color var(--dur-hover) var(--ease),
    border-color var(--dur-hover) var(--ease),
    color var(--dur-hover) var(--ease);
}

.ds-chip:hover:not(:disabled) {
  border-color: var(--rule-strong);
  color: var(--ink);
}

.ds-chip.is-selected {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
}

.ds-chip--ok {
  border-color: color-mix(in srgb, var(--ok) 38%, var(--rule));
  color: var(--ok);
}

.ds-chip--warn {
  border-color: color-mix(in srgb, var(--warn) 38%, var(--rule));
  color: var(--warn);
}

.ds-chip--danger {
  border-color: color-mix(in srgb, var(--danger) 38%, var(--rule));
  color: var(--danger);
}

.ds-chip:disabled {
  color: var(--ink-3);
  opacity: 1;
}
</style>
