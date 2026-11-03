<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: "primary" | "secondary" | "ghost" | "danger";
    size?: "sm" | "md" | "lg";
    type?: "button" | "submit" | "reset";
    disabled?: boolean;
    loading?: boolean;
  }>(),
  {
    variant: "secondary",
    size: "md",
    type: "button",
    disabled: false,
    loading: false,
  },
);
</script>

<template>
  <button
    :type="type"
    class="ds-btn"
    :class="[`ds-btn--${variant}`, `ds-btn--${size}`, { 'is-loading': loading }]"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
  >
    <span v-if="loading" class="ds-btn__spinner" aria-hidden="true"></span>
    <span class="ds-btn__label"><slot /></span>
  </button>
</template>

<style scoped>
.ds-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  height: var(--control-h);
  padding: 0 var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
  transition:
    background-color var(--dur-hover) var(--ease),
    border-color var(--dur-hover) var(--ease),
    color var(--dur-hover) var(--ease);
}

.ds-btn--sm {
  height: var(--control-h-sm);
  padding: 0 var(--space-2);
  font-size: 12px;
}

.ds-btn--lg {
  height: var(--control-h-lg);
  padding: 0 var(--space-4);
  font-size: 14px;
}

.ds-btn--primary {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--accent-ink);
}

.ds-btn--primary:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent) 88%, #000);
  border-color: color-mix(in srgb, var(--accent) 88%, #000);
}

.ds-btn--secondary {
  background: var(--raised);
  border-color: var(--rule-strong);
  color: var(--ink);
}

.ds-btn--secondary:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.ds-btn--ghost {
  background: transparent;
  border-color: transparent;
  color: var(--ink-2);
}

.ds-btn--ghost:hover:not(:disabled) {
  background: var(--surface-2);
  color: var(--ink);
}

.ds-btn--danger {
  background: transparent;
  border-color: color-mix(in srgb, var(--danger) 42%, var(--rule));
  color: var(--danger);
}

.ds-btn--danger:hover:not(:disabled) {
  background: color-mix(in srgb, var(--danger) 10%, transparent);
  border-color: var(--danger);
}

.ds-btn:disabled {
  background: var(--surface-2);
  border-color: var(--rule);
  color: var(--ink-3);
  opacity: 1;
}

.ds-btn--ghost:disabled,
.ds-btn--danger:disabled {
  background: transparent;
}

.ds-btn__spinner {
  width: 12px;
  height: 12px;
  border: 1.5px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: ds-spin 700ms linear infinite;
}

@keyframes ds-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
