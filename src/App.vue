<script setup lang="ts">
import { computed } from "vue";
import { RouterView, useRoute } from "vue-router";

import AppShell from "./components/layout/AppShell.vue";
import CommandPalette from "./components/layout/CommandPalette.vue";

const route = useRoute();
// 首帧 route.name 还没解析时，用 hash 兜住，避免 HUD/设置窗口/沙盒先闪一下主壳。
const bareByHash =
  typeof window !== "undefined" &&
  (window.location.hash.startsWith("#/hud") ||
    window.location.hash.startsWith("#/design") ||
    window.location.hash.startsWith("#/settings"));

/** HUD、设置窗口、设计沙盒自己画完整页面；其余都套主壳。 */
const isBare = computed(
  () =>
    bareByHash ||
    route.name === "hud" ||
    route.name === "design" ||
    route.name === "settings",
);
</script>

<template>
  <RouterView v-if="isBare" />
  <AppShell v-else>
    <RouterView />
  </AppShell>
  <CommandPalette v-if="!isBare" />
</template>
