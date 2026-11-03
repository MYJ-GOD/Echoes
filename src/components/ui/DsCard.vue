<script setup lang="ts">
withDefaults(
  defineProps<{
    padding?: "sm" | "md" | "lg";
    tone?: "default" | "raised";
  }>(),
  {
    padding: "md",
    tone: "default",
  },
);
</script>

<template>
  <section class="ds-card" :class="[`ds-card--${padding}`, `ds-card--${tone}`]">
    <slot />
  </section>
</template>

<style scoped>
.ds-card {
  border: 1px solid var(--rule);
  border-radius: var(--radius-card);
  background: var(--surface);
}

.ds-card--sm {
  padding: var(--space-3);
}

.ds-card--md {
  padding: var(--space-4);
}

.ds-card--lg {
  padding: var(--space-5);
}

.ds-card--raised {
  background: var(--raised);
  box-shadow: var(--shadow-1);
}
</style>
