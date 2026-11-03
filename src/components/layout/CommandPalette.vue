<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { CATEGORY_LABELS } from "../../composables/useMemory";
import { useSkinMode } from "../../composables/useSkinMode";
import * as ipc from "../../lib/ipc";
import type { MemoryView, SessionView, TurnView } from "../../lib/ipc";

const router = useRouter();
const { mode } = useSkinMode();

const open = ref(false);
const query = ref("");
const active = ref(0);
const inputEl = ref<HTMLInputElement | null>(null);
let previousActive: HTMLElement | null = null;

interface PaletteItem {
  id: string;
  section: "command" | "history" | "memory";
  label: string;
  hint: string;
  keywords: string;
  run: () => unknown;
}

const commands: PaletteItem[] = [
  {
    id: "chat",
    section: "command",
    label: "去对话",
    hint: "对话",
    keywords: "chat 对话 首页 返回",
    run: () => router.push("/"),
  },
  {
    id: "history",
    section: "command",
    label: "打开历史",
    hint: "历史",
    keywords: "history 历史 会话 搜索 原文",
    run: () => router.push("/history"),
  },
  {
    id: "memory",
    section: "command",
    label: "打开记忆",
    hint: "记忆",
    keywords: "memory 记忆 事实 来源",
    run: () => router.push("/memory"),
  },
  {
    id: "voice",
    section: "command",
    label: "打开声音",
    hint: "声音",
    keywords: "voice 声音 音色 克隆",
    run: () => router.push("/voice"),
  },
  {
    id: "about",
    section: "command",
    label: "关于 Echoes",
    hint: "关于",
    keywords: "about 关于 版本 诊断 许可",
    run: () => router.push("/about"),
  },
  {
    id: "settings",
    section: "command",
    label: "打开设置",
    hint: "设置",
    keywords: "settings 设置 引擎 密钥 设备 数据",
    run: async () => {
      try {
        await ipc.openSettingsWindow();
      } catch {
        await router.push("/settings");
      }
    },
  },
  {
    id: "stop",
    section: "command",
    label: "停止当前回复",
    hint: "打断",
    keywords: "stop 停止 打断 cancel 取消",
    run: async () => {
      try {
        await ipc.cancelTurn();
      } catch {
        // sidecar 未就绪：忽略
      }
    },
  },
];

const historyHits = ref<TurnView[]>([]);
const memoryHits = ref<MemoryView[]>([]);
const searching = ref(false);
const searchError = ref("");
const sessionCache = ref<SessionView[] | null>(null);
const memoryCache = ref<MemoryView[] | null>(null);

let searchTimer: number | null = null;
let searchSeq = 0;

function truncate(value: string, length: number): string {
  const clean = value.trim().replace(/\s+/g, " ");
  return clean.length > length ? `${clean.slice(0, length)}…` : clean;
}

function sessionTitle(sessionId: string): string {
  return (
    sessionCache.value?.find((session) => session.id === sessionId)?.title?.trim() ||
    "未命名会话"
  );
}

function day(at: number): string {
  return new Date(at * 1000).toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
}

const historyItems = computed<PaletteItem[]>(() =>
  historyHits.value.map((hit) => ({
    id: `history-${hit.turnId}`,
    section: "history" as const,
    label: `第 ${hit.seq} 轮 · ${truncate(hit.userText, 52)}`,
    hint: `${sessionTitle(hit.sessionId)} · ${day(hit.startedAt)}`,
    keywords: "",
    run: () =>
      router.push({
        path: "/history",
        query: { q: query.value.trim(), turn: hit.turnId },
      }),
  })),
);

const memoryItems = computed<PaletteItem[]>(() =>
  memoryHits.value.map((item) => ({
    id: `memory-${item.id}`,
    section: "memory" as const,
    label: truncate(item.fact, 56),
    hint: `${CATEGORY_LABELS[item.category]} · ${day(item.lastSeenAt)}`,
    keywords: "",
    run: () => router.push({ path: "/memory", query: { focus: item.id } }),
  })),
);

const groups = computed(() => {
  const needle = query.value.trim().toLowerCase();
  const commandItems = needle
    ? commands.filter((command) =>
        `${command.label} ${command.hint} ${command.keywords}`
          .toLowerCase()
          .includes(needle),
      )
    : commands;
  return [
    { label: "命令", items: commandItems },
    { label: "历史", items: historyItems.value },
    { label: "记忆", items: memoryItems.value },
  ].filter((group) => group.items.length > 0);
});

const visibleItems = computed(() => groups.value.flatMap((group) => group.items));

function indexOf(item: PaletteItem): number {
  return visibleItems.value.indexOf(item);
}

watch(visibleItems, () => {
  if (active.value >= visibleItems.value.length) active.value = 0;
});

function resetSearch(): void {
  historyHits.value = [];
  memoryHits.value = [];
  searching.value = false;
  searchError.value = "";
  sessionCache.value = null;
  memoryCache.value = null;
}

function scheduleSearch(): void {
  if (!open.value) return;
  const text = query.value.trim();
  searchSeq += 1;
  const requestId = searchSeq;
  if (searchTimer !== null) window.clearTimeout(searchTimer);
  if (!text) {
    historyHits.value = [];
    memoryHits.value = [];
    searching.value = false;
    searchError.value = "";
    return;
  }
  searching.value = true;
  searchError.value = "";
  searchTimer = window.setTimeout(() => {
    void runSearch(text, requestId);
  }, 200);
}

async function runSearch(text: string, requestId: number): Promise<void> {
  if (import.meta.env.DEV && window.location.hash.includes("palette-demo=1")) {
    const now = Math.floor(Date.now() / 1000);
    sessionCache.value = [
      {
        id: "demo-session",
        title: "雨天和爵士",
        startedAt: now - 86_400,
        lastActiveAt: now - 3600,
        archivedAt: null,
      },
    ];
    memoryCache.value = [
      {
        id: "demo-fact",
        fact: "用户喜欢在雨天听爵士，尤其是钢琴三重奏。",
        category: "preference",
        createdAt: now - 86_400 * 3,
        lastSeenAt: now - 3600,
        sourceSessionId: "demo-session",
        sourceSessionTitle: "雨天和爵士",
        sourceTurnSeq: 3,
      },
    ];
    historyHits.value = [
      {
        turnId: "demo-turn",
        sessionId: "demo-session",
        seq: 3,
        userText: "你上次说雨天喜欢听爵士。",
        assistantText: "记得。要我从第二首开始放吗？",
        status: "complete",
        failReason: null,
        startedAt: now - 86_400,
        endedAt: now - 86_000,
        supersededBy: null,
        groundingVerdict: null,
        groundingScore: null,
        groundingClaims: null,
      },
    ];
    memoryHits.value = memoryCache.value;
    searching.value = false;
    searchError.value = "";
    return;
  }
  try {
    if (memoryCache.value === null) {
      memoryCache.value = await ipc.listMemories(200);
    }
    if (sessionCache.value === null) {
      sessionCache.value = await ipc.sessionList();
    }
    const hits = await ipc.historySearch(text, undefined, 6, 0);
    if (requestId !== searchSeq) return;
    historyHits.value = hits;
    const needle = text.toLowerCase();
    memoryHits.value = (memoryCache.value ?? [])
      .filter((item) => item.fact.toLowerCase().includes(needle))
      .slice(0, 6);
  } catch {
    if (requestId === searchSeq) {
      searchError.value = "搜索失败。确认 sidecar 已启动后再试。";
    }
  } finally {
    if (requestId === searchSeq) searching.value = false;
  }
}

watch(query, () => {
  active.value = 0;
  scheduleSearch();
});

function show(): void {
  previousActive = document.activeElement as HTMLElement | null;
  open.value = true;
  query.value = "";
  active.value = 0;
  resetSearch();
  void nextTick(() => inputEl.value?.focus());
}

function hide(): void {
  open.value = false;
  query.value = "";
  active.value = 0;
  resetSearch();
  if (searchTimer !== null) window.clearTimeout(searchTimer);
  const target = previousActive;
  previousActive = null;
  void nextTick(() => target?.focus?.());
}

async function run(item: PaletteItem): Promise<void> {
  hide();
  await item.run();
}

function onInputKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") {
    event.preventDefault();
    hide();
    return;
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    active.value = (active.value + 1) % Math.max(1, visibleItems.value.length);
    return;
  }
  if (event.key === "ArrowUp") {
    event.preventDefault();
    active.value =
      (active.value - 1 + Math.max(1, visibleItems.value.length)) %
      Math.max(1, visibleItems.value.length);
    return;
  }
  if (event.key === "Enter") {
    event.preventDefault();
    const item = visibleItems.value[active.value];
    if (item) void run(item);
    return;
  }
  if (event.key === "Tab") {
    event.preventDefault();
  }
}

function onGlobalKeydown(event: KeyboardEvent): void {
  if (
    (event.ctrlKey || event.metaKey) &&
    event.shiftKey &&
    event.key.toLowerCase() === "p"
  ) {
    event.preventDefault();
    if (open.value) hide();
    else show();
  }
}

onMounted(() => {
  window.addEventListener("keydown", onGlobalKeydown);
});

onUnmounted(() => {
  window.removeEventListener("keydown", onGlobalKeydown);
  if (searchTimer !== null) window.clearTimeout(searchTimer);
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="palette"
      data-skin="next"
      :data-mode="mode"
      @mousedown.self="hide"
    >
      <section
        class="palette__panel"
        role="dialog"
        aria-modal="true"
        aria-label="命令面板"
        @keydown.tab.prevent
      >
        <input
          ref="inputEl"
          v-model="query"
          class="palette__input"
          type="text"
          placeholder="搜索命令、历史、记忆…"
          aria-label="搜索命令、历史与记忆"
          autocomplete="off"
          @keydown="onInputKeydown"
        />

        <div class="palette__body">
          <template v-for="group in groups" :key="group.label">
            <p class="palette__group">{{ group.label }}</p>
            <button
              v-for="item in group.items"
              :key="item.id"
              type="button"
              class="palette__item"
              :class="{ 'is-active': active === indexOf(item) }"
              role="option"
              :aria-selected="active === indexOf(item)"
              @mouseenter="active = indexOf(item)"
              @click="run(item)"
            >
              <span class="palette__label">{{ item.label }}</span>
              <span class="palette__hint">{{ item.hint }}</span>
            </button>
          </template>

          <p v-if="searching" class="palette__status">搜索中…</p>
          <p v-if="searchError" class="palette__status" data-tone="error">
            {{ searchError }}
          </p>
          <p
            v-if="!searching && !searchError && groups.length === 0"
            class="palette__status"
          >
            没有匹配的命令或记忆。
          </p>
        </div>

        <footer class="palette__footer">
          <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
          <span><kbd>Enter</kbd> 执行</span>
          <span><kbd>Esc</kbd> 关闭</span>
          <span class="palette__shortcut">Ctrl+Shift+P</span>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.palette {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 12vh 20px 20px;
  background: color-mix(in srgb, var(--ink) 30%, transparent);
}

.palette__panel {
  display: flex;
  flex-direction: column;
  width: min(560px, 100%);
  max-height: min(560px, 74vh);
  overflow: hidden;
  border: 1px solid var(--rule);
  border-radius: var(--radius-overlay);
  background: var(--raised);
  box-shadow: var(--shadow-3);
}

.palette__input {
  flex: none;
  height: 48px;
  padding: 0 16px;
  border: 0;
  border-bottom: 1px solid var(--rule);
  background: transparent;
  color: var(--ink);
  font: inherit;
  font-size: 14px;
}

.palette__input::placeholder {
  color: var(--ink-3);
}

.palette__input:focus {
  outline: none;
}

.palette__body {
  min-height: 0;
  padding: 4px 6px 6px;
  overflow-y: auto;
}

.palette__group {
  padding: 8px 10px 4px;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  line-height: 14px;
  text-transform: uppercase;
}

.palette__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  width: 100%;
  min-height: 38px;
  padding: 0 10px;
  border-radius: var(--radius-control);
  color: var(--ink-2);
  text-align: left;
}

.palette__item:hover,
.palette__item.is-active {
  background: var(--accent-soft);
  color: var(--accent);
}

.palette__label {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.palette__hint {
  flex: none;
  max-width: 42%;
  overflow: hidden;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.palette__status {
  padding: 10px;
  color: var(--ink-3);
  font-size: 12px;
  line-height: 18px;
}

.palette__status[data-tone="error"] {
  color: var(--danger);
}

.palette__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
  padding: 8px 12px;
  border-top: 1px solid var(--rule);
  color: var(--ink-3);
  font-size: 11px;
}

.palette__footer span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.palette__shortcut {
  margin-left: auto;
  font-family: var(--font-mono);
}
</style>
