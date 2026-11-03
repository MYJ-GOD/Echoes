<script setup lang="ts">
/**
 * 自绘标题栏（tauri.conf.json → decorations:false）。
 *
 * - 拖拽靠 `data-tauri-drag-region`（Tauri 2 原生处理，双击即最大化）；
 * - 窗口按钮走 ipc 门面，浏览器预览里静默失效，不炸 UI；
 * - 高度由主题 token `--titlebar-h` 决定（信笺/夜灯 40，台面 32）。
 */
import { onMounted, onUnmounted, ref } from "vue";
import type { UnlistenFn } from "@tauri-apps/api/event";

import * as ipc from "../lib/ipc";
import {
  restoreWindowGeometry,
  trackWindowGeometry,
} from "../lib/windowState";

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
  <header class="titlebar" data-tauri-drag-region="deep">
    <div class="tb-left">
      <span class="tb-mark">Echoes</span>
    </div>

    <div class="tb-controls">
      <button
        type="button"
        class="tb-btn"
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
        class="tb-btn"
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
        class="tb-btn close"
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

<style>
/* 非 scoped：高度/配色跟随主题 token，与 App.vue 的全局样式同层 */
.titlebar {
  flex: none;
  height: var(--titlebar-h, 40px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-left: 16px;
  position: relative;
  z-index: 50;
  background: var(--paper-hi);
  border-bottom: 1px solid var(--rule);
  user-select: none;
  -webkit-user-select: none;
}

.tb-left {
  display: flex;
  align-items: center;
  align-self: stretch;
  flex: 1;
}

.tb-mark {
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.34em;
  text-transform: uppercase;
  color: var(--ink-3);
  pointer-events: none;
}

.tb-controls {
  display: flex;
  align-items: stretch;
  align-self: stretch;
}

.tb-btn {
  display: grid;
  place-items: center;
  width: 46px;
  color: var(--ink-2);
  transition:
    background 0.14s ease,
    color 0.14s ease;
}

.tb-btn:hover {
  background: var(--paper-lo);
  color: var(--ink);
}

.tb-btn:active {
  background: var(--rule);
}

.tb-btn.close:hover {
  background: #c42b1c;
  color: #fff;
}

.tb-btn.close:active {
  background: #a82417;
}

[data-theme="desktop"] .titlebar {
  padding-left: 12px;
  background: var(--paper-hi);
}

[data-theme="desktop"] .tb-mark {
  letter-spacing: 0.02em;
  text-transform: none;
  font-family: var(--font-ui);
  font-size: 11.5px;
  color: var(--ink-2);
}

[data-theme="nocturne"] .tb-btn:hover {
  background: var(--paper-lo);
}

@media (prefers-reduced-motion: reduce) {
  .tb-btn {
    transition: none;
  }
}
</style>
