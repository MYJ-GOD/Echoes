<script setup lang="ts">
import { useDensity } from "../../composables/useDensity";
import { useSkinMode } from "../../composables/useSkinMode";

const { mode } = useSkinMode();
const { density } = useDensity();
</script>

<template>
  <div class="ds-skin" data-skin="next" :data-mode="mode" :data-density="density">
    <slot />
  </div>
</template>

<style scoped>
.ds-skin {
  min-height: 0;
}
</style>
