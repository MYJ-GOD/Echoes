<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import type { UnlistenFn } from "@tauri-apps/api/event";

import * as ipc from "../../lib/ipc";
import {
  restoreWindowGeometry,
  trackWindowGeometry,
} from "../../lib/windowState";

defineProps<{ mode: "light" | "dark" }>();

const maximized = ref(false);
let unlisten: UnlistenFn | null = null;
let stopTracking: (() => void) | null = null;

async function syncMaximized(): Promise<void> {
  maximized.value = await ipc.isWindowMaximized();
}

onMounted(async () => {
  await restoreWindowGeometry();
  await syncMaximized();
  unlisten = await ipc.onWindowResized(() => void syncMaximized());
  stopTracking = await trackWindowGeometry();
});

onUnmounted(() => {
  unlisten?.();
  unlisten = null;
  stopTracking?.();
  stopTracking = null;
});
</script>

<template>
  <header
    class="tb"
    data-skin="next"
    :data-mode="mode"
    data-tauri-drag-region="deep"
  >
    <span class="tb__brand">Echoes</span>

    <div class="tb__controls">
      <button
        type="button"
        class="tb__btn"
        aria-label="最小化"
        title="最小化"
        @click="ipc.minimizeWindow()"
      >
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
          <path d="M2 5h6" stroke="currentColor" stroke-width="1" />
        </svg>
      </button>

      <button
        type="button"
        class="tb__btn"
        :aria-label="maximized ? '还原' : '最大化'"
        :title="maximized ? '还原' : '最大化'"
        @click="ipc.toggleMaximizeWindow().then(syncMaximized)"
      >
        <svg
          v-if="!maximized"
          width="10"
          height="10"
          viewBox="0 0 10 10"
          aria-hidden="true"
        >
          <rect
            x="2.2"
            y="2.2"
            width="5.6"
            height="5.6"
            fill="none"
            stroke="currentColor"
            stroke-width="1"
          />
        </svg>
        <svg v-else width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
          <rect
            x="2"
            y="3.4"
            width="4.6"
            height="4.6"
            fill="none"
            stroke="currentColor"
            stroke-width="1"
          />
          <path
            d="M3.8 3.4V2h4.2v4.2H6.6"
            fill="none"
            stroke="currentColor"
            stroke-width="1"
          />
        </svg>
      </button>

      <button
        type="button"
        class="tb__btn tb__btn--close"
        aria-label="关闭"
        title="关闭"
        @click="ipc.closeWindow()"
      >
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
          <path
            d="M2.4 2.4l5.2 5.2M7.6 2.4L2.4 7.6"
            stroke="currentColor"
            stroke-width="1"
          />
        </svg>
      </button>
    </div>
  </header>
</template>

<style scoped>
.tb {
  display: flex;
  flex: none;
  height: var(--titlebar-h, 36px);
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--rule);
  background: var(--surface);
  color: var(--ink-3);
  user-select: none;
  -webkit-user-select: none;
}

.tb__brand {
  flex: 1;
  padding-left: 12px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  pointer-events: none;
}

.tb__controls {
  display: flex;
  align-self: stretch;
}

.tb__btn {
  display: grid;
  place-items: center;
  width: 44px;
  color: var(--ink-2);
  transition:
    background-color var(--dur-hover) var(--ease),
    color var(--dur-hover) var(--ease);
}

.tb__btn:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.tb__btn:active {
  background: var(--rule);
}

.tb__btn--close:hover {
  background: var(--danger);
  color: var(--accent-ink);
}
</style>
