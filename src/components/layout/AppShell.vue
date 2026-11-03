<script setup lang="ts">
import { useRouter } from "vue-router";

import * as ipc from "../../lib/ipc";
import { useSkinMode } from "../../composables/useSkinMode";
import AppSideRail from "./AppSideRail.vue";
import AppTitleBar from "./AppTitleBar.vue";

const { mode } = useSkinMode();
const router = useRouter();

async function openSettings(): Promise<void> {
  try {
    await ipc.openSettingsWindow();
  } catch {
    // 独立窗口建不出来时退回主窗口的整页设置，不再用抽屉。
    await router.push({ path: "/settings", query: { inline: "1" } });
  }
}
</script>

<template>
  <div class="shell" :data-mode="mode">
    <AppTitleBar :mode="mode" />
    <div class="shell__body">
      <AppSideRail :mode="mode" @settings="openSettings" />
      <main class="shell__main">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  min-height: 0;
  background: var(--shell-bg);
}

.shell[data-mode="light"] {
  --shell-bg: #f1f1ec;
}

.shell[data-mode="dark"] {
  --shell-bg: #101413;
}

.shell__body {
  display: flex;
  flex: 1;
  min-height: 0;
}

.shell__main {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.shell__main > :deep(.ds-skin) {
  flex: 1;
  min-height: 0;
}
</style>
