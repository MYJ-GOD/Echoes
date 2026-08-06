<template>
  <button class="primary-button focus-ring" :type="type" :disabled="disabled">
    <slot />
  </button>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    type?: "button" | "submit" | "reset";
    disabled?: boolean;
  }>(),
  { type: "button", disabled: false }
);
</script>

<style scoped>
.primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  width: 100%;
  padding: 14px 20px;
  border-radius: var(--radius-md);
  border: none;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-strong));
  color: #2a1a0f;
  font-weight: 600;
  font-size: 16px;
  box-shadow: var(--shadow-soft);
  cursor: pointer;
  transition: transform 160ms ease, box-shadow 160ms ease, opacity 160ms ease;
}

.primary-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  box-shadow: none;
}

.primary-button:not(:disabled):hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(229, 139, 58, 0.25);
}
</style>
