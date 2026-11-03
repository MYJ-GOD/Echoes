<script setup lang="ts">
withDefaults(
  defineProps<{
    placeholder?: string;
    rows?: number;
    disabled?: boolean;
    invalid?: boolean;
  }>(),
  {
    placeholder: "",
    rows: 3,
    disabled: false,
    invalid: false,
  },
);

const model = defineModel<string>({ default: "" });
</script>

<template>
  <textarea
    v-model="model"
    class="ds-textarea"
    :class="{ 'is-invalid': invalid }"
    :rows="rows"
    :placeholder="placeholder"
    :disabled="disabled"
    :aria-invalid="invalid || undefined"
  ></textarea>
</template>

<style scoped>
.ds-textarea {
  width: 100%;
  min-height: 76px;
  padding: 8px 10px;
  border: 1px solid var(--rule-strong);
  border-radius: var(--radius-control);
  background: var(--raised);
  color: var(--ink);
  font-size: 13px;
  line-height: 1.65;
  resize: vertical;
  transition:
    border-color var(--dur-hover) var(--ease),
    background-color var(--dur-hover) var(--ease);
}

.ds-textarea::placeholder {
  color: var(--ink-3);
}

.ds-textarea:hover:not(:disabled) {
  border-color: var(--ink-3);
}

.ds-textarea:focus {
  border-color: var(--accent);
  outline: 2px solid var(--accent-soft);
  outline-offset: 0;
}

.ds-textarea.is-invalid {
  border-color: var(--danger);
}

.ds-textarea:disabled {
  background: var(--surface-2);
  color: var(--ink-3);
}
</style>
