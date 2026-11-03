<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    state?: "idle" | "listening" | "thinking" | "speaking";
    bars?: number;
    height?: number;
    label?: string;
  }>(),
  {
    state: "idle",
    bars: 28,
    height: 28,
    label: "",
  },
);

const heights = [0.32, 0.58, 0.86, 0.46, 0.7, 1, 0.62, 0.38, 0.78, 0.5, 0.92, 0.44];

const items = computed(() =>
  Array.from({ length: props.bars }, (_, index) => ({
    height: heights[index % heights.length] ?? 0.5,
    delay: (index % 7) * 70,
  })),
);

const ariaLabel = computed(() => {
  if (props.label) return props.label;
  switch (props.state) {
    case "listening":
      return "正在听";
    case "thinking":
      return "正在想";
    case "speaking":
      return "正在说";
    default:
      return "静默";
  }
});
</script>

<template>
  <div
    class="ds-wave"
    :class="`ds-wave--${state}`"
    :style="{ height: `${height}px` }"
    role="img"
    :aria-label="ariaLabel"
  >
    <i
      v-for="(item, index) in items"
      :key="index"
      :style="{
        height: `${Math.round(item.height * height)}px`,
        animationDelay: `${item.delay}ms`,
      }"
    ></i>
  </div>
</template>

<style scoped>
.ds-wave {
  display: flex;
  align-items: center;
  gap: 2px;
  color: var(--accent);
}

.ds-wave i {
  display: block;
  width: 2px;
  min-height: 2px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.45;
  transform-origin: center;
}

.ds-wave--listening i {
  animation: ds-wave 900ms ease-in-out infinite;
}

.ds-wave--thinking i {
  animation: ds-wave 1400ms ease-in-out infinite;
}

.ds-wave--speaking i {
  animation: ds-wave 620ms ease-in-out infinite;
}

.ds-wave--listening {
  color: var(--accent);
}

.ds-wave--speaking {
  color: var(--signal);
}

@keyframes ds-wave {
  0%,
  100% {
    transform: scaleY(0.55);
    opacity: 0.35;
  }
  50% {
    transform: scaleY(1);
    opacity: 0.95;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ds-wave i {
    animation: none;
    opacity: 0.6;
  }
}
</style>
