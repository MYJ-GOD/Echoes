<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    description?: string;
    eyebrow?: string;
  }>(),
  {
    description: "",
    eyebrow: "",
  },
);
</script>

<template>
  <header class="page-head">
    <div class="page-head__copy">
      <p v-if="eyebrow" class="page-head__eyebrow">{{ eyebrow }}</p>
      <h1 class="page-head__title">{{ title }}</h1>
      <p v-if="description" class="page-head__desc">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="page-head__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-head {
  display: flex;
  flex: none;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-6);
  padding: var(--space-5) var(--space-6) var(--space-4);
  border-bottom: 1px solid var(--rule);
}

.page-head__copy {
  min-width: 0;
}

.page-head__eyebrow {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  line-height: 14px;
  text-transform: uppercase;
}

.page-head__title {
  margin-top: 2px;
  color: var(--ink);
  font-size: var(--text-title);
  font-weight: 600;
  line-height: var(--text-title-line);
}

.page-head__desc {
  max-width: 68ch;
  margin-top: var(--space-1);
  color: var(--ink-2);
  font-size: 13px;
  line-height: 20px;
}

.page-head__actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--space-2);
  padding-top: 2px;
}
</style>
