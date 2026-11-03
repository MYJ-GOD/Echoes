<script setup lang="ts">
import { onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import PageHeader from "../components/layout/PageHeader.vue";
import * as ipc from "../lib/ipc";
import DsButton from "../components/ui/DsButton.vue";
import DsCheckbox from "../components/ui/DsCheckbox.vue";
import DsEmptyState from "../components/ui/DsEmptyState.vue";
import DsErrorState from "../components/ui/DsErrorState.vue";
import DsInput from "../components/ui/DsInput.vue";
import DsSkin from "../components/ui/DsSkin.vue";
import { useHistory } from "../composables/useHistory";
import type { SessionView } from "../lib/ipc";

const router = useRouter();
const route = useRoute();
const {
  groups,
  activeSessionId,
  showArchived,
  showSuperseded,
  query,
  hits,
  status,
  busy,
  preview,
  previewBusy,
  loadSessions,
  title,
  time,
  segments,
  previewSession,
  closePreview,
  reloadPreview,
  openSession,
  create,
  rename,
  archive,
  remove,
  search,
  openHit,
} = useHistory(() => {
  // D2：历史页只读；真正继续对话在 P3 接回 ChatPage 的线程加载。
});

async function applyRouteQuery(): Promise<void> {
  const initial = typeof route.query.q === "string" ? route.query.q : "";
  const turnId = typeof route.query.turn === "string" ? route.query.turn : "";
  if (initial) {
    query.value = initial;
    await search();
  }
  await loadSessions();
  if (turnId) {
    const hit = hits.value.find((item) => item.turnId === turnId);
    if (hit) {
      await openHit(hit);
    } else {
      const turn = await ipc.historyGet(turnId).catch(() => null);
      if (turn) await openHit(turn);
    }
  }
}

onMounted(() => {
  void applyRouteQuery();
});

// 命令面板在同一页面内改 query 时组件会被复用，onMounted 不会重跑。
watch(
  () => [route.query.q, route.query.turn],
  () => {
    void applyRouteQuery();
  },
);

function clock(value: number): string {
  return new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

async function continueSession(session: SessionView): Promise<void> {
  await openSession(session);
  if (status.value) return;
  try {
    // D3：让 ChatPage 回到对话页后回填这段会话的最近线程。
    sessionStorage.setItem("echoes.openSession", session.id);
  } catch {
    // 隐私模式 / 存储不可用：Chat 仍会加载当前活动会话。
  }
  await router.push("/");
}

async function continueCurrent(): Promise<void> {
  if (!preview.value) return;
  await continueSession(preview.value.session);
}
</script>

<template>
  <DsSkin class="history-skin">
      <PageHeader
        title="历史"
        description="原文一字不差地保存在本机。点会话先只读回看；要继续聊，再显式点「继续对话」。"
      >
        <template #actions>
          <DsButton :loading="busy" @click="create">新建对话</DsButton>
        </template>
      </PageHeader>

      <div class="history">
        <section class="history__list" aria-label="会话列表">
          <div class="history__tools">
            <DsInput
              v-model="query"
              placeholder="搜索原话…"
              aria-label="搜索原话"
              @keyup.enter="search"
            />
            <DsButton size="sm" @click="search">搜索</DsButton>
          </div>
          <DsCheckbox
            v-model="showArchived"
            label="显示已归档"
            @update:model-value="loadSessions"
          />

          <DsErrorState
            v-if="status"
            title="读取历史失败。"
            description="确认 sidecar 已启动，然后重试。"
          >
            <DsButton size="sm" @click="loadSessions">重试</DsButton>
          </DsErrorState>

          <div v-if="hits.length" class="hits">
            <p class="group-label">搜索结果</p>
            <button
              v-for="hit in hits"
              :key="hit.turnId"
              type="button"
              class="hit"
              @click="openHit(hit)"
            >
              <span class="hit__seq">第 {{ hit.seq }} 轮</span>
              <span class="hit__text">
                <template v-for="(seg, index) in segments(hit.userText)" :key="index">
                  <mark v-if="seg.hit">{{ seg.text }}</mark>
                  <template v-else>{{ seg.text }}</template>
                </template>
              </span>
            </button>
          </div>

          <template v-else>
            <div v-for="group in groups" :key="group.label" class="group">
              <p class="group-label">{{ group.label }}</p>
              <div
                v-for="session in group.rows"
                :key="session.id"
                class="srow"
                :class="{ 'is-active': session.id === activeSessionId }"
              >
                <button
                  type="button"
                  class="srow__main"
                  :disabled="previewBusy"
                  @click="previewSession(session)"
                >
                  <span class="srow__title">
                    {{ title(session) }}
                    <span v-if="session.archivedAt !== null" class="srow__tag">已归档</span>
                  </span>
                  <span class="srow__meta">{{ time(session.lastActiveAt) }}</span>
                </button>
                <span class="srow__actions">
                  <template v-if="session.archivedAt === null">
                    <DsButton variant="ghost" size="sm" @click="rename(session)">改名</DsButton>
                    <DsButton variant="ghost" size="sm" @click="archive(session)">归档</DsButton>
                  </template>
                  <DsButton variant="ghost" size="sm" @click="remove(session)">删除</DsButton>
                </span>
              </div>
            </div>

            <DsEmptyState
              v-if="groups.length === 0 && !status"
              title="对话会自动保存在本机。"
              description="开始第一段对话后，这里会按今天 / 本周 / 更早分组。"
            >
              <DsButton variant="primary" size="sm" @click="router.push('/')">
                去对话
              </DsButton>
            </DsEmptyState>
          </template>
        </section>

        <aside class="history__preview" aria-label="会话预览">
          <template v-if="preview">
            <header class="preview__head">
              <div>
                <p class="preview__eyebrow">只读回看</p>
                <h2 class="preview__title">{{ title(preview.session) }}</h2>
              </div>
              <div class="preview__actions">
                <DsCheckbox
                  v-model="showSuperseded"
                  label="显示被取代"
                  @update:model-value="reloadPreview"
                />
                <DsButton variant="ghost" size="sm" @click="closePreview">返回列表</DsButton>
                <DsButton size="sm" :loading="busy" @click="continueCurrent">
                  继续对话
                </DsButton>
              </div>
            </header>

            <div class="preview__thread">
              <div
                v-for="(row, index) in preview.rows"
                :key="index"
                class="msg"
                :class="[row.role, { 'is-superseded': row.superseded }]"
              >
                <div class="msg__meta">
                  <time>{{ clock(row.at) }}</time>
                  <span>{{ row.role === "assistant" ? "她" : "你" }}</span>
                </div>
                <div class="msg__body">
                  <p>{{ row.text }}</p>
                  <p v-if="row.interrupted" class="msg__note">已打断</p>
                  <p v-if="row.superseded" class="msg__note">已被取代</p>
                </div>
              </div>
              <p v-if="preview.rows.length === 0" class="preview__empty">
                这段对话还没有原文。
              </p>
            </div>
          </template>

          <div v-else class="preview__placeholder">
            <p class="preview__eyebrow">只读回看</p>
            <p class="preview__title">选一段对话。</p>
            <p class="preview__desc">
              点左侧任意会话查看原文；继续对话必须显式点按钮，不会自动切走当前会话。
            </p>
          </div>
        </aside>
      </div>
  </DsSkin>
</template>

<style scoped>
.history-skin {
  flex: 1;
  min-height: 0;
}

.history {
  display: grid;
  flex: 1;
  grid-template-columns: 320px minmax(0, 1fr);
  min-height: 0;
}

.history__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-height: 0;
  padding: var(--space-4);
  overflow-y: auto;
  border-right: 1px solid var(--rule);
}

.history__tools {
  display: flex;
  gap: var(--space-2);
}

.history__tools :deep(.ds-input) {
  flex: 1;
}

.group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.group-label {
  padding: var(--space-2) 2px 4px;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  line-height: 14px;
  text-transform: uppercase;
}

.srow {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  border-radius: var(--radius-control);
  transition: background-color var(--dur-hover) var(--ease);
}

.srow:hover {
  background: var(--surface-2);
}

.srow.is-active {
  background: var(--accent-soft);
}

.srow__main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding: 7px 8px;
  text-align: left;
}

.srow__title,
.srow__meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.srow__title {
  color: var(--ink);
  font-size: 13px;
  line-height: 18px;
}

.srow__meta {
  color: var(--ink-3);
  font-size: 11px;
  line-height: 15px;
}

.srow__tag {
  margin-left: 4px;
  color: var(--ink-3);
  font-size: 10px;
}

.srow__actions {
  display: flex;
  flex: none;
  gap: 0;
  opacity: 0;
  transition: opacity var(--dur-hover) var(--ease);
}

.srow:hover .srow__actions,
.srow:focus-within .srow__actions {
  opacity: 1;
}

.hits {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hit {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 7px 8px;
  border-radius: var(--radius-control);
  text-align: left;
}

.hit:hover {
  background: var(--surface-2);
}

.hit__seq,
.hit__text {
  overflow: hidden;
  text-overflow: ellipsis;
}

.hit__seq {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
}

.hit__text {
  color: var(--ink-2);
  font-size: 12px;
  line-height: 18px;
}

.hit mark {
  background: var(--accent-soft);
  color: var(--ink);
}

.history__preview {
  min-height: 0;
  padding: var(--space-5) var(--space-6);
  overflow-y: auto;
}

.preview__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--rule);
}

.preview__eyebrow {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  line-height: 14px;
  text-transform: uppercase;
}

.preview__title {
  margin-top: 2px;
  color: var(--ink);
  font-size: var(--text-title);
  font-weight: 600;
  line-height: var(--text-title-line);
}

.preview__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
}

.preview__thread {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  max-width: 780px;
  padding-top: var(--space-5);
}

.msg {
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr);
  gap: var(--space-3);
}

.msg__meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 3px;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 15px;
}

.msg__meta span {
  color: var(--ink-2);
}

.msg__body p:first-child {
  color: var(--ink);
  font-size: var(--text-body);
  line-height: var(--text-body-line);
  white-space: pre-wrap;
}

.msg.assistant .msg__body {
  padding-left: var(--space-3);
  border-left: 2px solid var(--accent);
}

.msg.assistant .msg__body p:first-child {
  font-family: var(--font-voice);
  font-size: var(--text-voice);
  line-height: var(--text-voice-line);
}

.msg.user .msg__body {
  padding: 8px 10px;
  border-radius: var(--radius-control);
  background: var(--surface-2);
}

.msg.is-superseded {
  opacity: 0.55;
}

.msg__note {
  margin-top: 4px;
  color: var(--ink-3);
  font-size: 11px;
  line-height: 15px;
}

.preview__placeholder {
  max-width: 420px;
  padding-top: var(--space-8);
}

.preview__desc {
  margin-top: var(--space-2);
  color: var(--ink-2);
  font-size: 13px;
  line-height: 20px;
}

.preview__empty {
  color: var(--ink-3);
  font-size: 13px;
}

@media (max-width: 900px) {
  .history {
    grid-template-columns: 1fr;
    overflow-y: auto;
  }

  .history__list {
    min-height: 40vh;
    border-right: none;
    border-bottom: 1px solid var(--rule);
  }

  .history__preview {
    min-height: 40vh;
  }

  .srow__actions {
    opacity: 1;
  }
}
</style>
