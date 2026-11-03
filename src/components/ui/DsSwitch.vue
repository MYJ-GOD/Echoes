<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    hint?: string;
    disabled?: boolean;
  }>(),
  {
    hint: "",
    disabled: false,
  },
);

const model = defineModel<boolean>({ default: false });
</script>

<template>
  <div class="ds-switch-row" :class="{ 'is-disabled': disabled }">
    <span class="ds-switch__text">
      <span class="ds-switch__label">{{ label }}</span>
      <span v-if="hint" class="ds-switch__hint">{{ hint }}</span>
    </span>
    <button
      type="button"
      class="ds-switch"
      role="switch"
      :aria-checked="model"
      :aria-label="label"
      :disabled="disabled"
      @click="model = !model"
    >
      <span class="ds-switch__thumb" aria-hidden="true"></span>
    </button>
  </div>
</template>

<style scoped>
.ds-switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.ds-switch__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ds-switch__label {
  color: var(--ink);
  font-size: 13px;
  line-height: 18px;
}

.ds-switch__hint {
  color: var(--ink-3);
  font-size: 12px;
  line-height: 16px;
}

.ds-switch {
  position: relative;
  width: 36px;
  height: 20px;
  flex: none;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-pill);
  background: var(--surface-2);
  transition:
    background-color var(--dur-hover) var(--ease),
    border-color var(--dur-hover) var(--ease);
}

.ds-switch[aria-checked="true"] {
  border-color: var(--accent);
  background: var(--accent);
}

.ds-switch__thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--raised);
  box-shadow: var(--shadow-1);
  transition: transform var(--dur-enter) var(--ease);
}

.ds-switch[aria-checked="true"] .ds-switch__thumb {
  transform: translateX(16px);
}

.ds-switch:disabled {
  border-color: var(--rule);
  background: var(--surface-2);
}

.ds-switch-row.is-disabled .ds-switch__label,
.ds-switch-row.is-disabled .ds-switch__hint {
  color: var(--ink-3);
}
</style>
