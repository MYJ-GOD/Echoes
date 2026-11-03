<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string;
    hint?: string;
    error?: string;
    required?: boolean;
  }>(),
  {
    hint: "",
    error: "",
    required: false,
  },
);
</script>

<template>
  <label class="ds-field">
    <span class="ds-field__label">
      {{ label }}
      <span v-if="required" class="ds-field__required" aria-hidden="true">*</span>
    </span>
    <slot />
    <span v-if="error" class="ds-field__error" role="alert">{{ error }}</span>
    <span v-else-if="hint" class="ds-field__hint">{{ hint }}</span>
  </label>
</template>

<style scoped>
.ds-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.ds-field__label {
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 500;
  line-height: 16px;
}

.ds-field__required {
  color: var(--danger);
}

.ds-field__hint,
.ds-field__error {
  font-size: 12px;
  line-height: 16px;
}

.ds-field__hint {
  color: var(--ink-3);
}

.ds-field__error {
  color: var(--danger);
}
</style>
