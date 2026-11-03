<script setup lang="ts">
withDefaults(
  defineProps<{
    width?: string;
    height?: string;
    rounded?: "control" | "card" | "pill";
  }>(),
  {
    width: "100%",
    height: "14px",
    rounded: "control",
  },
);
</script>

<template>
  <span
    class="ds-skeleton"
    :class="`ds-skeleton--${rounded}`"
    :style="{ width, height }"
    aria-hidden="true"
  ></span>
</template>

<style scoped>
.ds-skeleton {
  display: block;
  max-width: 100%;
  background: linear-gradient(
    90deg,
    var(--surface-2) 0%,
    color-mix(in srgb, var(--surface-2) 55%, var(--ink-3)) 50%,
    var(--surface-2) 100%
  );
  background-size: 200% 100%;
  animation: ds-skeleton 1.4s ease-in-out infinite;
}

.ds-skeleton--control {
  border-radius: var(--radius-control);
}

.ds-skeleton--card {
  border-radius: var(--radius-card);
}

.ds-skeleton--pill {
  border-radius: var(--radius-pill);
}

@keyframes ds-skeleton {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
