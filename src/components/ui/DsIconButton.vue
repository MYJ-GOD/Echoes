<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    title?: string;
    size?: "sm" | "md";
    tone?: "neutral" | "danger";
    disabled?: boolean;
  }>(),
  {
    title: "",
    size: "md",
    tone: "neutral",
    disabled: false,
  },
);

defineEmits<{ click: [event: MouseEvent] }>();
</script>

<template>
  <button
    type="button"
    class="ds-icon-btn"
    :class="[`ds-icon-btn--${size}`, `ds-icon-btn--${tone}`]"
    :aria-label="label"
    :title="title || label"
    :disabled="disabled"
    @click="$emit('click', $event)"
  >
    <slot />
  </button>
</template>

<style scoped>
.ds-icon-btn {
  display: inline-grid;
  place-items: center;
  width: var(--control-h);
  height: var(--control-h);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  color: var(--ink-2);
  transition:
    background-color var(--dur-hover) var(--ease),
    border-color var(--dur-hover) var(--ease),
    color var(--dur-hover) var(--ease);
}

.ds-icon-btn--sm {
  width: var(--control-h-sm);
  height: var(--control-h-sm);
}

.ds-icon-btn:hover:not(:disabled) {
  background: var(--surface-2);
  color: var(--ink);
}

.ds-icon-btn--danger {
  color: var(--danger);
}

.ds-icon-btn--danger:hover:not(:disabled) {
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  color: var(--danger);
}

.ds-icon-btn:disabled {
  color: var(--ink-3);
  opacity: 1;
}
</style>
