<script setup lang="ts">
withDefaults(
  defineProps<{
    options: { value: string; label: string }[];
    label?: string;
  }>(),
  {
    label: "",
  },
);

const model = defineModel<string>({ required: true });
</script>

<template>
  <div class="ds-segmented" role="group" :aria-label="label || undefined">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      class="ds-segmented__item"
      :class="{ 'is-on': model === option.value }"
      :aria-pressed="model === option.value"
      @click="model = option.value"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
.ds-segmented {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--rule);
  border-radius: var(--radius-control);
  background: var(--surface-2);
}

.ds-segmented__item {
  height: calc(var(--control-h) - 6px);
  padding: 0 10px;
  border-radius: 3px;
  color: var(--ink-2);
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  transition:
    background-color var(--dur-hover) var(--ease),
    color var(--dur-hover) var(--ease);
}

.ds-segmented__item:hover {
  color: var(--ink);
}

.ds-segmented__item.is-on {
  background: var(--raised);
  color: var(--ink);
  box-shadow: var(--shadow-1);
}
</style>
