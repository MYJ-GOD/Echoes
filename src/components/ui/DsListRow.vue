<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    meta?: string;
    selected?: boolean;
    clickable?: boolean;
    disabled?: boolean;
  }>(),
  {
    meta: "",
    selected: false,
    clickable: false,
    disabled: false,
  },
);

defineEmits<{ click: [event: MouseEvent] }>();
</script>

<template>
  <button
    v-if="clickable"
    type="button"
    class="ds-row"
    :class="{ 'is-selected': selected }"
    :disabled="disabled"
    @click="$emit('click', $event)"
  >
    <span class="ds-row__leading"><slot name="leading" /></span>
    <span class="ds-row__text">
      <span class="ds-row__title">{{ title }}</span>
      <span v-if="meta" class="ds-row__meta">{{ meta }}</span>
    </span>
    <span class="ds-row__actions"><slot name="actions" /></span>
  </button>

  <div v-else class="ds-row" :class="{ 'is-selected': selected }">
    <span class="ds-row__leading"><slot name="leading" /></span>
    <span class="ds-row__text">
      <span class="ds-row__title">{{ title }}</span>
      <span v-if="meta" class="ds-row__meta">{{ meta }}</span>
    </span>
    <span class="ds-row__actions"><slot name="actions" /></span>
  </div>
</template>

<style scoped>
.ds-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  min-height: var(--row-h);
  padding: 0 var(--space-2);
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--ink);
  text-align: left;
  transition:
    background-color var(--dur-hover) var(--ease),
    border-color var(--dur-hover) var(--ease);
}

button.ds-row:hover:not(:disabled) {
  background: var(--surface-2);
}

.ds-row.is-selected {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.ds-row__leading:empty,
.ds-row__actions:empty {
  display: none;
}

.ds-row__leading {
  display: flex;
  flex: none;
  color: var(--ink-2);
}

.ds-row__text {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.ds-row__title,
.ds-row__meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ds-row__title {
  font-size: 13px;
  line-height: 18px;
}

.ds-row__meta {
  color: var(--ink-3);
  font-size: 12px;
  line-height: 16px;
}

.ds-row__actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--space-1);
  color: var(--ink-3);
}

button.ds-row:disabled {
  color: var(--ink-3);
}
</style>
