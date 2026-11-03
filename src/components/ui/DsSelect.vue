<script setup lang="ts">
withDefaults(
  defineProps<{
    disabled?: boolean;
    invalid?: boolean;
    label?: string;
  }>(),
  {
    disabled: false,
    invalid: false,
    label: "",
  },
);

const model = defineModel<string>({ default: "" });
</script>

<template>
  <span class="ds-select-wrap" :class="{ 'is-disabled': disabled, 'is-invalid': invalid }">
    <select
      v-model="model"
      class="ds-select"
      :disabled="disabled"
      :aria-label="label || undefined"
      :aria-invalid="invalid || undefined"
    >
      <slot />
    </select>
    <svg
      class="ds-select__chevron"
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  </span>
</template>

<style scoped>
.ds-select-wrap {
  position: relative;
  display: block;
  width: 100%;
  min-width: 0;
  color: var(--ink-2);
}

.ds-select-wrap.is-invalid {
  color: var(--danger);
}

.ds-select {
  width: 100%;
  min-width: 0;
  height: var(--control-h);
  padding: 0 30px 0 10px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-control);
  background: var(--raised);
  color: var(--ink);
  font-size: 13px;
  appearance: none;
  transition: border-color var(--dur-hover) var(--ease);
}

.ds-select:hover:not(:disabled) {
  border-color: var(--ink-3);
}

.ds-select:focus {
  border-color: var(--accent);
  outline: 2px solid var(--accent-soft);
  outline-offset: 0;
}

.ds-select-wrap.is-invalid .ds-select {
  border-color: var(--danger);
}

.ds-select:disabled {
  background: var(--surface-2);
  color: var(--ink-3);
}

.ds-select__chevron {
  position: absolute;
  top: 50%;
  right: 10px;
  pointer-events: none;
  transform: translateY(-50%);
}

.ds-select-wrap.is-disabled .ds-select__chevron {
  color: var(--ink-3);
}
</style>
