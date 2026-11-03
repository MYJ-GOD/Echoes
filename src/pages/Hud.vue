<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";

import * as ipc from "../lib/ipc";

type HudState = "listening" | "thinking" | "speaking" | "error";

const state = ref<HudState>("listening");
const text = ref("我在听");
/** R5：最近一句回复（迷你对话） */
const reply = ref("");
let unlisten: (() => void) | null = null;
let hideTimer: number | null = null;
/// 本轮是否已进入 turn。`ready` 也可能是「切会话/引擎分级就绪」的广播，
/// 只有 turn 跑过之后才允许用 ready 收尾，否则 HUD 会在 PTT 刚按下时自己消失。
let sawTurn = false;

function hideSoon(delay = 900): void {
  if (hideTimer !== null) window.clearTimeout(hideTimer);
  hideTimer = window.setTimeout(() => {
    hideTimer = null;
    sawTurn = false;
    reply.value = "";
    void ipc.hideHud();
  }, delay);
}

/** 回复只留一句：HUD 是提示条，不是阅读器（完整内容回主窗口看）。 */
function shorten(value: string): string {
  const clean = value.trim().replace(/\s+/g, " ");
  return clean.length > 46 ? `${clean.slice(0, 46)}…` : clean;
}

onMounted(async () => {
  try {
    unlisten = await ipc.onSidecarEvent((frame) => {
      if (frame.type === "state") {
        const next = String(frame.state);
        if (next === "generating") {
          sawTurn = true;
          reply.value = "";
          state.value = "thinking";
          text.value = "正在想…";
        } else if (next === "speaking") {
          sawTurn = true;
          state.value = "speaking";
          text.value = "正在说…";
        } else if (next === "ready") {
          if (sawTurn) hideSoon(reply.value ? 4800 : 900);
        } else if (next === "error") {
          state.value = "error";
          text.value = "出错了";
          hideSoon();
        }
      }
      if (frame.type === "assistant_text") {
        sawTurn = true;
        reply.value = shorten(String(frame.text));
        state.value = "speaking";
        text.value = "正在说…";
      }
      if (frame.type === "turn_complete") {
        hideSoon(reply.value ? 4800 : 900);
      }
    });
  } catch (err) {
    console.warn("HUD event bus unavailable:", err);
  }
});

onUnmounted(() => {
  unlisten?.();
  if (hideTimer !== null) window.clearTimeout(hideTimer);
});

function cancel(): void {
  void ipc.cancelTurn().catch(() => undefined);
  void ipc.hideHud();
}

/** R5：展开迷你对话 → 主窗口。 */
function expand(): void {
  void ipc.showMainWindow().catch(() => undefined);
}
</script>

<template>
  <div class="hud" :data-state="state">
    <div class="row">
      <span class="dot" aria-hidden="true"></span>
      <span class="hud-text">{{ text }}</span>
      <span class="wave" aria-hidden="true">
        <i v-for="n in 5" :key="n" :style="{ animationDelay: `${n * 90}ms` }"></i>
      </span>
      <button type="button" class="hud-cancel" title="停止" @click="cancel">×</button>
    </div>
    <button v-if="reply" type="button" class="reply" title="打开主窗口" @click="expand">
      <span class="reply-text">{{ reply }}</span>
      <span class="reply-open">打开 ›</span>
    </button>
  </div>
</template>

<style scoped>
:global(html),
:global(body),
:global(#app) {
  margin: 0;
  background: transparent;
  overflow: hidden;
}

.hud {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  height: 100vh;
  box-sizing: border-box;
  padding: 10px 14px;
  border: 1px solid rgb(255 255 255 / 16%);
  border-radius: 16px;
  background: rgb(30 27 23 / 92%);
  color: #f4ecdd;
  font: 13px/1.4 "Segoe UI", "Microsoft YaHei", sans-serif;
  box-shadow: 0 14px 40px rgb(0 0 0 / 30%);
  -webkit-app-region: drag;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #d8a657;
  box-shadow: 0 0 0 4px rgb(216 166 87 / 14%);
}

.hud[data-state="thinking"] .dot {
  background: #e8c77a;
}

.hud[data-state="speaking"] .dot {
  background: #8ac6a0;
}

.hud[data-state="error"] .dot {
  background: #d77b6a;
}

.hud-text {
  flex: 1;
  white-space: nowrap;
}

.wave {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 16px;
}

.wave i {
  width: 2px;
  height: 5px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.45;
  animation: pulse 900ms ease-in-out infinite;
}

.hud[data-state="listening"] .wave i {
  animation-duration: 700ms;
}

.hud[data-state="thinking"] .wave i {
  animation-duration: 1100ms;
}

@keyframes pulse {
  0%,
  100% {
    height: 4px;
    opacity: 0.35;
  }
  50% {
    height: 15px;
    opacity: 0.9;
  }
}

.hud-cancel {
  width: 24px;
  height: 24px;
  border: 0;
  border-radius: 50%;
  background: rgb(255 255 255 / 9%);
  color: inherit;
  cursor: pointer;
  -webkit-app-region: no-drag;
}

.hud-cancel:hover {
  background: rgb(255 255 255 / 18%);
}

/* R5 迷你对话：一行回复，点开主窗口 */
.reply {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 5px 8px;
  border: 0;
  border-radius: 8px;
  background: rgb(255 255 255 / 7%);
  color: inherit;
  font: inherit;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  -webkit-app-region: no-drag;
}

.reply:hover {
  background: rgb(255 255 255 / 14%);
}

.reply-text {
  flex: 1;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  opacity: 0.9;
}

.reply-open {
  color: #e3a76b;
  white-space: nowrap;
}

@media (prefers-reduced-motion: reduce) {
  .wave i {
    animation: none;
    height: 8px;
  }
}
</style>
