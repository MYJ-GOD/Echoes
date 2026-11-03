<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    description?: string;
  }>(),
  {
    description: "",
  },
);
</script>

<template>
  <div class="ds-error" role="alert">
    <div class="ds-error__head">
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v5M12 16h.01" />
      </svg>
      <p class="ds-error__title">{{ title }}</p>
    </div>
    <p v-if="description" class="ds-error__desc">{{ description }}</p>
    <div v-if="$slots.default" class="ds-error__actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.ds-error {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border: 1px solid color-mix(in srgb, var(--danger) 38%, var(--rule));
  border-radius: var(--radius-card);
  background: color-mix(in srgb, var(--danger) 7%, var(--surface));
  color: var(--danger);
}

.ds-error__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.ds-error__title {
  font-size: 13px;
  font-weight: 600;
  line-height: 18px;
}

.ds-error__desc {
  color: var(--ink-2);
  font-size: 12px;
  line-height: 18px;
}

.ds-error__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-1);
}
</style>
