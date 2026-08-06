<template>
  <router-link class="primary-link focus-ring" :to="to">
    <slot />
  </router-link>
</template>

<script setup lang="ts">
defineProps<{
  to: string;
}>();
</script>

<style scoped>
.primary-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 14px 20px;
  border-radius: var(--radius-md);
  border: none;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-strong));
  color: #2a1a0f;
  font-weight: 600;
  font-size: 16px;
  box-shadow: var(--shadow-soft);
  transition: transform 160ms ease, box-shadow 160ms ease;
}

.primary-link:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(229, 139, 58, 0.25);
}
</style>
