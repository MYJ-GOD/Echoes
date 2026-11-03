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
  <div class="ds-empty">
    <div class="ds-empty__mark" aria-hidden="true">
      <span></span><span></span><span></span>
    </div>
    <p class="ds-empty__title">{{ title }}</p>
    <p v-if="description" class="ds-empty__desc">{{ description }}</p>
    <div v-if="$slots.default" class="ds-empty__actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.ds-empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-2);
  max-width: 360px;
  padding: var(--space-8) 0;
}

.ds-empty__mark {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 22px;
  margin-bottom: var(--space-2);
}

.ds-empty__mark span {
  display: block;
  width: 2px;
  border-radius: 2px;
  background: var(--accent);
  opacity: 0.55;
}

.ds-empty__mark span:nth-child(1) {
  height: 9px;
}

.ds-empty__mark span:nth-child(2) {
  height: 20px;
  opacity: 0.8;
}

.ds-empty__mark span:nth-child(3) {
  height: 13px;
}

.ds-empty__title {
  color: var(--ink);
  font-family: var(--font-voice);
  font-size: var(--text-display);
  line-height: var(--text-display-line);
}

.ds-empty__desc {
  color: var(--ink-2);
  font-size: var(--text-body);
  line-height: var(--text-body-line);
}

.ds-empty__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
</style>
