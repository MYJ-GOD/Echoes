<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: string;
    placeholder?: string;
    disabled?: boolean;
    readonly?: boolean;
    invalid?: boolean;
  }>(),
  {
    type: "text",
    placeholder: "",
    disabled: false,
    readonly: false,
    invalid: false,
  },
);

const model = defineModel<string>({ default: "" });
</script>

<template>
  <input
    v-model="model"
    class="ds-input"
    :class="{ 'is-invalid': invalid }"
    :type="type"
    :placeholder="placeholder"
    :disabled="disabled"
    :readonly="readonly"
    :aria-invalid="invalid || undefined"
  />
</template>

<style scoped>
.ds-input {
  width: 100%;
  min-width: 0;
  height: var(--control-h);
  padding: 0 10px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-control);
  background: var(--raised);
  color: var(--ink);
  font-size: 13px;
  line-height: 1;
  transition:
    border-color var(--dur-hover) var(--ease),
    background-color var(--dur-hover) var(--ease);
}

.ds-input::placeholder {
  color: var(--ink-3);
}

.ds-input:hover:not(:disabled):not(:read-only) {
  border-color: var(--ink-3);
}

.ds-input:focus {
  border-color: var(--accent);
  outline: 2px solid var(--accent-soft);
  outline-offset: 0;
}

.ds-input.is-invalid {
  border-color: var(--danger);
}

.ds-input:disabled {
  background: var(--surface-2);
  color: var(--ink-3);
}

.ds-input:read-only {
  background: var(--surface);
}
</style>
