<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    value: number;
    max?: number;
    label?: string;
    tone?: "accent" | "signal" | "ok" | "danger";
    showValue?: boolean;
  }>(),
  {
    max: 100,
    label: "",
    tone: "accent",
    showValue: false,
  },
);

const pct = computed(() => {
  if (props.max <= 0) return 0;
  return Math.min(100, Math.max(0, (props.value / props.max) * 100));
});

const rounded = computed(() => Math.round(pct.value));
</script>

<template>
  <div class="ds-meter">
    <div class="ds-meter__head">
      <span v-if="label" class="ds-meter__label">{{ label }}</span>
      <span v-if="showValue" class="ds-meter__value">{{ rounded }}%</span>
    </div>
    <div
      class="ds-meter__track"
      role="progressbar"
      :aria-label="label || undefined"
      :aria-valuemin="0"
      :aria-valuemax="max"
      :aria-valuenow="value"
    >
      <span
        class="ds-meter__fill"
        :class="`ds-meter__fill--${tone}`"
        :style="{ width: `${pct}%` }"
      ></span>
    </div>
  </div>
</template>

<style scoped>
.ds-meter {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.ds-meter__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.ds-meter__label,
.ds-meter__value {
  color: var(--ink-3);
  font-size: 12px;
  line-height: 16px;
}

.ds-meter__value {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

.ds-meter__track {
  height: 4px;
  overflow: hidden;
  border-radius: var(--radius-pill);
  background: var(--surface-2);
}

.ds-meter__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
  transition: width var(--dur-enter) var(--ease);
}

.ds-meter__fill--signal {
  background: var(--signal);
}

.ds-meter__fill--ok {
  background: var(--ok);
}

.ds-meter__fill--danger {
  background: var(--danger);
}
</style>
