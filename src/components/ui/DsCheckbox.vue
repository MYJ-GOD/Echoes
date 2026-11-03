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
  <label class="ds-check" :class="{ 'is-disabled': disabled }">
    <input v-model="model" type="checkbox" :disabled="disabled" />
    <span class="ds-check__box" aria-hidden="true">
      <svg
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="m5 12 5 5L20 7" />
      </svg>
    </span>
    <span class="ds-check__text">
      <span class="ds-check__label">{{ label }}</span>
      <span v-if="hint" class="ds-check__hint">{{ hint }}</span>
    </span>
  </label>
</template>

<style scoped>
.ds-check {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
}

.ds-check input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.ds-check__box {
  display: grid;
  place-items: center;
  width: 16px;
  height: 16px;
  flex: none;
  margin-top: 2px;
  border: 1px solid var(--rule-strong);
  border-radius: 3px;
  background: var(--raised);
  color: var(--accent-ink);
  transition:
    background-color var(--dur-hover) var(--ease),
    border-color var(--dur-hover) var(--ease);
}

.ds-check__box svg {
  opacity: 0;
  transform: scale(0.8);
  transition:
    opacity var(--dur-hover) var(--ease),
    transform var(--dur-hover) var(--ease);
}

.ds-check input:checked + .ds-check__box {
  border-color: var(--accent);
  background: var(--accent);
}

.ds-check input:checked + .ds-check__box svg {
  opacity: 1;
  transform: scale(1);
}

.ds-check input:focus-visible + .ds-check__box {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}

.ds-check__text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.ds-check__label {
  color: var(--ink);
  font-size: 13px;
  line-height: 18px;
}

.ds-check__hint {
  color: var(--ink-3);
  font-size: 12px;
  line-height: 16px;
}

.ds-check.is-disabled {
  cursor: default;
}

.ds-check.is-disabled .ds-check__box,
.ds-check.is-disabled .ds-check__label {
  color: var(--ink-3);
}

.ds-check.is-disabled .ds-check__box {
  background: var(--surface-2);
  border-color: var(--rule);
}
</style>
