<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import PageHeader from "../components/layout/PageHeader.vue";
import MemoryGraph from "../components/memory/MemoryGraph.vue";
import DsButton from "../components/ui/DsButton.vue";
import DsCheckbox from "../components/ui/DsCheckbox.vue";
import DsConfirmDialog from "../components/ui/DsConfirmDialog.vue";
import DsEmptyState from "../components/ui/DsEmptyState.vue";
import DsInput from "../components/ui/DsInput.vue";
import DsSegmented from "../components/ui/DsSegmented.vue";
import DsSelect from "../components/ui/DsSelect.vue";
import DsSkeleton from "../components/ui/DsSkeleton.vue";
import DsSkin from "../components/ui/DsSkin.vue";
import DsTextarea from "../components/ui/DsTextarea.vue";
import DsTextDialog from "../components/ui/DsTextDialog.vue";
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  useMemory,
} from "../composables/useMemory";
import type { MemoryCategory } from "../composables/useMemory";
import * as ipc from "../lib/ipc";
import type { MemoryGraph as MemoryGraphData, MemoryView } from "../lib/ipc";

const {
  items,
  groups,
  status,
  loading,
  busyId,
  openId,
  usage,
  usageStatus,
  draft,
  draftCategory,
  saving,
  mergeMode,
  selected,
  bulkText,
  bulkCategory,
  bulkStatus,
  importBulk,
  load,
  toggleUsage,
  deleteFact,
  updateFact,
  mergeFacts,
  addFact,
  toggleSelect,
  toggleMergeMode,
  clock,
} = useMemory();

const route = useRoute();
const query = ref(typeof route.query.q === "string" ? route.query.q : "");
const focusId = ref(typeof route.query.focus === "string" ? route.query.focus : "");
const activeId = ref("");
const view = ref<"detail" | "create" | "bulk">("detail");
const viewMode = ref<"list" | "graph">(
  route.query.graph === "1" ? "graph" : "list",
);
const collapsed = ref<MemoryCategory[]>([]);
const graph = ref<MemoryGraphData>({ nodes: [], edges: [] });
const graphLoading = ref(false);

const filteredGroups = computed(() => {
  const needle = query.value.trim().toLowerCase();
  if (!needle) return groups.value;
  return groups.value
    .map((group) => ({
      ...group,
      rows: group.rows.filter((item) =>
        item.fact.toLowerCase().includes(needle),
      ),
    }))
    .filter((group) => group.rows.length > 0);
});

const activeItem = computed<MemoryView | null>(
  () => items.value.find((item) => item.id === activeId.value) ?? null,
);

const usageList = computed(() =>
  activeId.value ? (usage.value[activeId.value] ?? []) : [],
);

const neighbors = computed(() => {
  const current = activeItem.value;
  if (!current) return [];
  return items.value
    .filter(
      (item) => item.id !== current.id && item.category === current.category,
    )
    .sort((left, right) => right.lastSeenAt - left.lastSeenAt)
    .slice(0, 8);
});

const isDemo = import.meta.env.DEV && route.query.demo === "1";

const demoGraph = computed<MemoryGraphData>(() => {
  const nodes = items.value.map((item) => ({
    id: item.id,
    fact: item.fact,
    category: item.category,
    lastSeenAt: item.lastSeenAt,
    degree: 0,
  }));
  if (nodes.length < 3) return { nodes, edges: [] };
  const edges: MemoryGraphData["edges"] = [
    { source: "demo-1", target: "demo-2", kind: "co-used", weight: 2 },
    { source: "demo-2", target: "demo-3", kind: "same-session", weight: 0.5 },
    { source: "demo-1", target: "demo-3", kind: "co-used", weight: 1 },
  ];
  for (const edge of edges) {
    const source = nodes.find((node) => node.id === edge.source);
    const target = nodes.find((node) => node.id === edge.target);
    if (source) source.degree += 1;
    if (target) target.degree += 1;
  }
  return { nodes, edges };
});

const graphData = computed<MemoryGraphData>(() =>
  isDemo ? demoGraph.value : graph.value,
);

async function loadGraph(): Promise<void> {
  if (isDemo) return;
  graphLoading.value = true;
  try {
    graph.value = await ipc.memoryGraph();
  } catch (err) {
    status.value = `读取图谱失败：${String(err)}`;
  } finally {
    graphLoading.value = false;
  }
}

async function openFromGraph(id: string): Promise<void> {
  viewMode.value = "list";
  await selectItem(id);
}

const statusIsError = computed(() => /失败/.test(status.value));
const statusText = computed(() => {
  if (status.value === "还没有记住任何事。") return "";
  return statusIsError.value
    ? "操作没有完成。确认 sidecar 已启动后再试。"
    : status.value;
});

function rowMeta(item: MemoryView): string {
  const date = new Date(item.createdAt * 1000).toLocaleDateString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  });
  return item.sourceSessionTitle
    ? `${date} · ${item.sourceSessionTitle}`
    : date;
}

function sourceText(item: MemoryView): string {
  if (!item.sourceSessionTitle) return "手动添加 / 早期记录";
  return item.sourceTurnSeq
    ? `${item.sourceSessionTitle} · 第 ${item.sourceTurnSeq} 轮`
    : item.sourceSessionTitle;
}

function isCollapsed(category: MemoryCategory): boolean {
  return !query.value.trim() && collapsed.value.includes(category);
}

function toggleGroup(category: MemoryCategory): void {
  collapsed.value = collapsed.value.includes(category)
    ? collapsed.value.filter((item) => item !== category)
    : [...collapsed.value, category];
}

async function selectItem(id: string): Promise<void> {
  view.value = "detail";
  activeId.value = id;
  await nextTick();
  document
    .querySelector<HTMLElement>(`[data-memory-id="${CSS.escape(id)}"]`)
    ?.scrollIntoView({ block: "nearest" });
}

function pickInitial(): void {
  const preferred = focusId.value
    ? items.value.find((item) => item.id === focusId.value)
    : undefined;
  const target = preferred ?? items.value[0];
  if (target) activeId.value = target.id;
}

async function scrollToFocus(): Promise<void> {
  if (!focusId.value) return;
  await nextTick();
  document
    .querySelector<HTMLElement>(
      `[data-memory-id="${CSS.escape(focusId.value)}"]`,
    )
    ?.scrollIntoView({ block: "center" });
}

const editTarget = ref<MemoryView | null>(null);
const editOpen = ref(false);
const editText = ref("");
const editError = ref("");

const mergeOpen = ref(false);
const mergeText = ref("");
const mergeError = ref("");

const deleteTarget = ref<MemoryView | null>(null);
const deleteOpen = ref(false);

function openEdit(item: MemoryView): void {
  editTarget.value = item;
  editText.value = item.fact;
  editError.value = "";
  editOpen.value = true;
}

function editActive(): void {
  if (activeItem.value) openEdit(activeItem.value);
}

async function confirmEdit(): Promise<void> {
  if (!editTarget.value) return;
  const text = editText.value.trim();
  if (!text) {
    editError.value = "记忆不能为空。";
    return;
  }
  if (text === editTarget.value.fact) {
    editOpen.value = false;
    return;
  }
  const ok = await updateFact(editTarget.value, text);
  if (ok) {
    editOpen.value = false;
    editTarget.value = null;
  } else {
    editError.value = "没有保存成功。确认 sidecar 已启动后再试。";
  }
}

function openMerge(): void {
  if (selected.value.length < 2) return;
  const chosen = items.value.filter((item) => selected.value.includes(item.id));
  mergeText.value = chosen.map((item) => item.fact).join("；");
  mergeError.value = "";
  mergeOpen.value = true;
}

async function confirmMerge(): Promise<void> {
  const text = mergeText.value.trim();
  if (!text) {
    mergeError.value = "合并后的记忆不能为空。";
    return;
  }
  const ok = await mergeFacts(selected.value, text);
  if (ok) {
    mergeOpen.value = false;
    view.value = "detail";
    activeId.value = "";
  } else {
    mergeError.value = "没有合并成功。确认 sidecar 已启动后再试。";
  }
}

function askDelete(item: MemoryView): void {
  deleteTarget.value = item;
  deleteOpen.value = true;
}

function deleteActive(): void {
  if (activeItem.value) askDelete(activeItem.value);
}

async function confirmDelete(): Promise<void> {
  if (!deleteTarget.value) return;
  const ok = await deleteFact(deleteTarget.value);
  if (ok) {
    deleteOpen.value = false;
    deleteTarget.value = null;
  }
}

function startCreate(): void {
  view.value = "create";
  activeId.value = "";
}

function startBulk(): void {
  view.value = "bulk";
  activeId.value = "";
}

async function submitCreate(): Promise<void> {
  if (!draft.value.trim()) return;
  await addFact();
  if (status.value === "已添加一条记忆") {
    view.value = "detail";
  }
}

async function submitBulk(): Promise<void> {
  await importBulk();
  if (!bulkStatus.value.includes("失败")) {
    view.value = "detail";
  }
}

watch(activeId, (id) => {
  usageStatus.value = "";
  if (!id) return;
  const item = items.value.find((entry) => entry.id === id);
  if (item && openId.value !== id) void toggleUsage(item);
});

watch(items, (list) => {
  if (viewMode.value === "graph" && !isDemo) void loadGraph();
  if (list.length === 0) {
    activeId.value = "";
    return;
  }
  if (!list.some((item) => item.id === activeId.value)) {
    activeId.value = list[0].id;
  }
});

watch(
  viewMode,
  (mode) => {
    if (mode === "graph") void loadGraph();
  },
  { immediate: true },
);

watch(
  () => [route.query.q, route.query.focus],
  ([nextQuery, nextFocus]) => {
    if (typeof nextQuery === "string") query.value = nextQuery;
    focusId.value = typeof nextFocus === "string" ? nextFocus : "";
    if (focusId.value) {
      activeId.value = focusId.value;
      void scrollToFocus();
    }
  },
);

onMounted(async () => {
  if (import.meta.env.DEV && route.query.demo === "1") {
    const now = Math.floor(Date.now() / 1000);
    items.value = [
      {
        id: "demo-1",
        fact: "用户喜欢在雨天听爵士，尤其是钢琴三重奏。",
        category: "preference",
        createdAt: now - 86_400 * 3,
        lastSeenAt: now - 3600,
        sourceSessionId: "demo-session",
        sourceSessionTitle: "雨天和爵士",
        sourceTurnSeq: 3,
      },
      {
        id: "demo-2",
        fact: "用户养了一只叫豆豆的猫，怕打雷。",
        category: "identity",
        createdAt: now - 86_400 * 10,
        lastSeenAt: now - 7200,
        sourceSessionId: "demo-session",
        sourceSessionTitle: "关于搬家",
        sourceTurnSeq: 8,
      },
      {
        id: "demo-3",
        fact: "用户下周三要搬去杭州，正在找房子。",
        category: "event",
        createdAt: now - 86_400,
        lastSeenAt: now - 1800,
        sourceSessionId: null,
        sourceSessionTitle: null,
        sourceTurnSeq: null,
      },
    ];
    usage.value = {
      "demo-1": [
        {
          turnId: "demo-turn-1",
          sessionId: "demo-session",
          sessionTitle: "雨天和爵士",
          seq: 3,
          userText: "今天下雨了，想听点安静的音乐。",
          usedAt: now - 3600,
        },
        {
          turnId: "demo-turn-2",
          sessionId: "demo-session",
          sessionTitle: "周末闲聊",
          seq: 5,
          userText: "推荐一张适合晚上写东西的专辑。",
          usedAt: now - 86_400,
        },
      ],
      "demo-2": [],
      "demo-3": [],
    };
    loading.value = false;
    pickInitial();
    void scrollToFocus();
    return;
  }
  await load();
  pickInitial();
  void scrollToFocus();
});
</script>

<template>
  <DsSkin class="memory-skin">
    <PageHeader
      title="记忆"
      description="只显示仍在生效的事实；被取代或删除的不再参与检索，原文与历史对话不受影响。"
    >
      <template #actions>
        <DsButton :disabled="loading" @click="load">
          {{ loading ? "读取中…" : "刷新" }}
        </DsButton>
      </template>
    </PageHeader>

    <div class="memory" :class="{ 'memory--graph': viewMode === 'graph' }">
      <aside class="memory__rail" aria-label="记忆库">
        <div class="memory__rail-search">
          <DsInput
            v-model="query"
            type="search"
            placeholder="搜索记忆…"
            aria-label="搜索记忆"
          />
          <DsSegmented
            v-model="viewMode"
            class="memory__view-switch"
            label="记忆视图"
            :options="[
              { value: 'list', label: '列表' },
              { value: 'graph', label: '图谱' },
            ]"
          />
        </div>

        <nav class="memory__tree" aria-label="记忆分类">
          <div v-if="loading && items.length === 0" class="memory__loading">
            <DsSkeleton width="38%" height="12px" />
            <DsSkeleton width="100%" height="30px" rounded="card" />
            <DsSkeleton width="100%" height="30px" rounded="card" />
            <DsSkeleton width="100%" height="30px" rounded="card" />
          </div>

          <template v-else>
            <section
              v-for="group in filteredGroups"
              :key="group.category"
              class="mem-group"
            >
              <button
                type="button"
                class="mem-group__head"
                :aria-expanded="!isCollapsed(group.category)"
                @click="toggleGroup(group.category)"
              >
                <span
                  class="mem-group__chevron"
                  :class="{ 'is-open': !isCollapsed(group.category) }"
                  aria-hidden="true"
                >
                  ›
                </span>
                <span class="mem-group__label">{{ group.label }}</span>
                <span class="mem-group__count">{{ group.rows.length }}</span>
              </button>

              <ul v-show="!isCollapsed(group.category)" class="mem-list">
                <li v-for="item in group.rows" :key="item.id">
                  <div
                    class="mem-item"
                    :class="{ 'is-active': activeId === item.id }"
                    :data-memory-id="item.id"
                  >
                    <DsCheckbox
                      v-if="mergeMode"
                      class="mem-item__check"
                      :model-value="selected.includes(item.id)"
                      label=""
                      @update:model-value="toggleSelect(item.id)"
                    />
                    <button
                      type="button"
                      class="mem-item__main"
                      :aria-current="activeId === item.id ? 'true' : undefined"
                      @click="selectItem(item.id)"
                    >
                      <span class="mem-item__fact">{{ item.fact }}</span>
                      <span class="mem-item__meta">{{ rowMeta(item) }}</span>
                    </button>
                  </div>
                </li>
              </ul>
            </section>

            <p
              v-if="filteredGroups.length === 0 && items.length > 0"
              class="memory__note memory__note--rail"
            >
              没有匹配的记忆。
              <button type="button" class="memory__link" @click="query = ''">
                清除搜索
              </button>
            </p>
          </template>
        </nav>

        <div class="memory__rail-foot">
          <DsButton size="sm" @click="startCreate">新建</DsButton>
          <DsButton size="sm" variant="ghost" @click="startBulk">
            批量
          </DsButton>
          <DsButton
            size="sm"
            variant="ghost"
            :aria-pressed="mergeMode"
            @click="toggleMergeMode"
          >
            {{ mergeMode ? "退出合并" : "合并" }}
          </DsButton>
        </div>

        <div v-if="mergeMode" class="memory__merge">
          <span>已选 {{ selected.length }} 条</span>
          <DsButton
            size="sm"
            variant="primary"
            :disabled="saving || selected.length < 2"
            @click="openMerge"
          >
            合并所选
          </DsButton>
        </div>
      </aside>

      <MemoryGraph
        v-if="viewMode === 'graph'"
        class="memory__graph"
        :nodes="graphData.nodes"
        :edges="graphData.edges"
        :selected-id="activeId"
        :loading="graphLoading"
        @select="openFromGraph"
      />

      <template v-else>
      <section class="memory__detail" aria-label="记忆详情">
        <header class="mem-detail__bar">
          <p class="mem-detail__crumb">
            <span>记忆库</span>
            <template v-if="activeItem">
              <span aria-hidden="true">/</span>
              <span>{{ CATEGORY_LABELS[activeItem.category] }}</span>
            </template>
          </p>
          <div v-if="view === 'detail' && activeItem" class="mem-detail__actions">
            <DsButton size="sm" :disabled="saving" @click="editActive">
              编辑
            </DsButton>
            <DsButton
              size="sm"
              variant="danger"
              :disabled="busyId === activeId"
              @click="deleteActive"
            >
              {{ busyId === activeId ? "删除中…" : "删除" }}
            </DsButton>
          </div>
        </header>

        <p
          v-if="statusText"
          class="memory__status"
          :data-tone="statusIsError ? 'error' : 'ok'"
        >
          {{ statusText }}
        </p>

        <div class="mem-detail__scroll">
          <form
            v-if="view === 'create'"
            class="mem-form"
            @submit.prevent="submitCreate"
          >
            <h2 class="mem-form__title">新建记忆</h2>
            <p class="mem-form__hint">
              写成一句陈述句，检索时更容易命中。旧版本会保留在历史里。
            </p>
            <DsTextarea
              v-model="draft"
              :rows="4"
              maxlength="500"
              placeholder="例如：用户喜欢在雨天听爵士"
              aria-label="记忆内容"
            />
            <DsSelect v-model="draftCategory" label="记忆类别">
              <option v-for="key in CATEGORY_ORDER" :key="key" :value="key">
                {{ CATEGORY_LABELS[key] }}
              </option>
            </DsSelect>
            <div class="mem-form__actions">
              <DsButton
                type="submit"
                variant="primary"
                :disabled="saving || draft.trim() === ''"
              >
                {{ saving ? "保存中…" : "保存" }}
              </DsButton>
              <DsButton variant="ghost" @click="view = 'detail'">
                取消
              </DsButton>
            </div>
          </form>

          <form
            v-else-if="view === 'bulk'"
            class="mem-form"
            @submit.prevent="submitBulk"
          >
            <h2 class="mem-form__title">批量导入</h2>
            <p class="mem-form__hint">
              每行一条；也可写「事实|类别」。类别：preference / identity /
              event / other。
            </p>
            <DsTextarea
              v-model="bulkText"
              :rows="7"
              placeholder="用户喜欢在雨天听爵士&#10;用户养了一只叫豆豆的猫|identity"
              aria-label="批量记忆"
            />
            <DsSelect v-model="bulkCategory" label="默认类别">
              <option v-for="key in CATEGORY_ORDER" :key="key" :value="key">
                {{ CATEGORY_LABELS[key] }}（默认）
              </option>
            </DsSelect>
            <p v-if="bulkStatus" class="memory__note">{{ bulkStatus }}</p>
            <div class="mem-form__actions">
              <DsButton
                type="submit"
                variant="primary"
                :disabled="saving || bulkText.trim() === ''"
              >
                {{ saving ? "导入中…" : "导入" }}
              </DsButton>
              <DsButton variant="ghost" @click="view = 'detail'">
                取消
              </DsButton>
            </div>
          </form>

          <template v-else-if="activeItem">
            <p class="mem-detail__fact">{{ activeItem.fact }}</p>

            <dl class="mem-props">
              <div>
                <dt>类别</dt>
                <dd>{{ CATEGORY_LABELS[activeItem.category] }}</dd>
              </div>
              <div>
                <dt>创建</dt>
                <dd>{{ clock(activeItem.createdAt) }}</dd>
              </div>
              <div>
                <dt>最近</dt>
                <dd>{{ clock(activeItem.lastSeenAt) }}</dd>
              </div>
              <div>
                <dt>来源</dt>
                <dd>{{ sourceText(activeItem) }}</dd>
              </div>
              <div>
                <dt>使用</dt>
                <dd>
                  {{
                    usageList.length
                      ? `${usageList.length} 轮引用`
                      : "还没有被引用"
                  }}
                </dd>
              </div>
            </dl>

            <p class="memory__hint">
              写入会重新生成向量（需要 bge 权重），首次保存可能要几秒。
            </p>
          </template>

          <DsEmptyState
            v-else-if="items.length === 0 && !loading"
            title="聊得越多，这里越丰富。"
            description="她记住的事会自动出现在这里；也可以点左下角「新建」手动添加一条。"
          />

          <DsEmptyState
            v-else
            title="选一条记忆。"
            description="左侧是记忆库；选中后这里显示全文、属性和来源。"
          />
        </div>
      </section>

      <aside class="memory__related" aria-label="关联">
        <h2 class="related__title">关联</h2>

        <template v-if="view === 'detail' && activeItem">
          <section class="related__group">
            <h3 class="related__heading">
              被回复用过 <span>{{ usageList.length }}</span>
            </h3>
            <p v-if="usageStatus" class="related__note">{{ usageStatus }}</p>
            <p v-else-if="usageList.length === 0" class="related__note">
              还没有回复用过这条记忆。
            </p>
            <ul v-else class="related__list">
              <li v-for="hit in usageList" :key="hit.turnId">
                <div class="related__item">
                  <span class="related__item-title">
                    {{ hit.sessionTitle || "未命名会话" }} · 第 {{ hit.seq }} 轮
                  </span>
                  <span class="related__item-meta">{{ clock(hit.usedAt) }}</span>
                  <span class="related__item-said">{{ hit.userText }}</span>
                </div>
              </li>
            </ul>
          </section>

          <section v-if="activeItem.sourceSessionTitle" class="related__group">
            <h3 class="related__heading">来源</h3>
            <div class="related__item">
              <span class="related__item-title">
                {{ activeItem.sourceSessionTitle }}
              </span>
              <span v-if="activeItem.sourceTurnSeq" class="related__item-meta">
                第 {{ activeItem.sourceTurnSeq }} 轮
              </span>
            </div>
          </section>

          <section class="related__group">
            <h3 class="related__heading">
              同类别 <span>{{ neighbors.length }}</span>
            </h3>
            <ul v-if="neighbors.length" class="related__list">
              <li v-for="neighbor in neighbors" :key="neighbor.id">
                <button
                  type="button"
                  class="related__link"
                  @click="selectItem(neighbor.id)"
                >
                  <span class="related__link-fact">{{ neighbor.fact }}</span>
                  <span class="related__link-meta">
                    {{ clock(neighbor.lastSeenAt) }}
                  </span>
                </button>
              </li>
            </ul>
            <p v-else class="related__note">同类别里还没有别的记忆。</p>
          </section>
        </template>

        <p v-else class="related__note">
          选中一条记忆后，这里会显示它被哪些回复用过。
        </p>
      </aside>
      </template>
    </div>

    <DsTextDialog
      v-model="editText"
      :open="editOpen"
      title="编辑这条记忆"
      description="旧版本会被取代，不再参与检索；原文与历史对话不受影响。"
      label="记忆内容"
      :rows="4"
      :maxlength="500"
      :busy="saving"
      :error="editError"
      confirm-label="保存修改"
      @confirm="confirmEdit"
      @cancel="editOpen = false"
    />

    <DsTextDialog
      v-model="mergeText"
      :open="mergeOpen"
      title="合并所选记忆"
      :description="`会把选中的 ${selected.length} 条合并成一条，旧条目被取代。`"
      label="合并后的记忆"
      :rows="5"
      :maxlength="1000"
      :busy="saving"
      :error="mergeError"
      confirm-label="合并"
      @confirm="confirmMerge"
      @cancel="mergeOpen = false"
    />

    <DsConfirmDialog
      :open="deleteOpen"
      title="删除这条记忆？"
      :description="`「${deleteTarget?.fact ?? ''}」删除后不再参与检索；原文与历史对话不受影响。`"
      confirm-label="删除"
      danger
      :busy="deleteTarget !== null && busyId === deleteTarget.id"
      @confirm="confirmDelete"
      @cancel="deleteOpen = false"
    />
  </DsSkin>
</template>

<style scoped>
.memory-skin {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.memory {
  display: grid;
  grid-template-columns: 248px minmax(0, 1fr) 276px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* ---- 左栏：记忆库 ------------------------------------------------ */

.memory__rail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border-right: 1px solid var(--rule);
  background: var(--bg);
}

.memory__rail-search {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-3) var(--space-2);
}

.memory__view-switch {
  width: 100%;
}

.memory__view-switch :deep(.ds-segmented__item) {
  flex: 1;
}

.memory--graph {
  grid-template-columns: 248px minmax(0, 1fr);
}

.memory__graph {
  grid-column: 2;
}

.memory__tree {
  flex: 1;
  min-height: 0;
  padding: 0 var(--space-2) var(--space-3);
  overflow-y: auto;
}

.mem-group {
  margin-bottom: var(--space-2);
}

.mem-group__head {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  height: 28px;
  padding: 0 6px;
  border: 0;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  line-height: 16px;
  text-align: left;
  text-transform: uppercase;
}

.mem-group__head:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.mem-group__chevron {
  display: inline-block;
  width: 10px;
  font-size: 13px;
  line-height: 1;
  transition: transform var(--dur-hover) var(--ease);
}

.mem-group__chevron.is-open {
  transform: rotate(90deg);
}

.mem-group__label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mem-group__count {
  color: var(--ink-3);
  font-size: 10px;
}

.mem-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin-top: 2px;
}

.mem-item {
  display: flex;
  align-items: center;
  gap: 4px;
  border-radius: var(--radius-control);
  box-shadow: inset 2px 0 0 transparent;
}

.mem-item:hover {
  background: var(--surface-2);
}

.mem-item.is-active {
  background: var(--accent-soft);
  box-shadow: inset 2px 0 0 var(--accent);
}

.mem-item__check {
  flex: none;
  margin-left: 6px;
}

.mem-item__check :deep(.ds-check__text) {
  display: none;
}

.mem-item__main {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
  padding: 5px 8px;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
}

.mem-item__fact,
.mem-item__meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mem-item__fact {
  color: var(--ink);
  font-size: 13px;
  line-height: 18px;
}

.mem-item.is-active .mem-item__fact {
  color: var(--ink);
  font-weight: 500;
}

.mem-item.is-active .mem-item__meta {
  color: var(--ink-2);
}

.mem-item__meta {
  color: var(--ink-3);
  font-size: 10px;
  line-height: 14px;
}

.memory__rail-foot {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-2);
  border-top: 1px solid var(--rule);
}

.memory__merge {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-top: 1px solid var(--accent);
  background: var(--accent-soft);
  color: var(--ink-2);
  font-size: 11px;
  line-height: 16px;
}

.memory__loading {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2) 6px;
}

/* ---- 中栏：详情 -------------------------------------------------- */

.memory__detail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--surface);
}

.mem-detail__bar {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  min-height: 40px;
  padding: var(--space-2) var(--space-5);
  border-bottom: 1px solid var(--rule);
}

.mem-detail__crumb {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  line-height: 16px;
}

.mem-detail__actions {
  display: flex;
  flex: none;
  gap: var(--space-2);
}

.mem-detail__scroll {
  flex: 1;
  min-height: 0;
  padding: var(--space-6) var(--space-8) var(--space-10);
  overflow-y: auto;
}

.mem-detail__fact {
  max-width: 36em;
  color: var(--ink);
  font-family: var(--font-voice);
  font-size: 20px;
  line-height: 33px;
  overflow-wrap: anywhere;
}

.mem-props {
  display: flex;
  flex-direction: column;
  gap: 7px;
  max-width: 36em;
  margin-top: var(--space-8);
  padding-top: var(--space-4);
  border-top: 1px solid var(--rule);
}

.mem-props > div {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}

.mem-props dt {
  flex: none;
  width: 48px;
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  line-height: 18px;
}

.mem-props dd {
  min-width: 0;
  color: var(--ink-2);
  font-size: 12px;
  line-height: 18px;
  overflow-wrap: anywhere;
}

.mem-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-width: 520px;
}

.mem-form__title {
  color: var(--ink);
  font-size: var(--text-title);
  font-weight: 600;
  line-height: var(--text-title-line);
}

.mem-form__hint {
  margin-top: calc(var(--space-3) * -1);
  color: var(--ink-3);
  font-size: 12px;
  line-height: 18px;
}

.mem-form__actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

/* ---- 右栏：关联 -------------------------------------------------- */

.memory__related {
  min-height: 0;
  padding: var(--space-4) var(--space-4) var(--space-8);
  border-left: 1px solid var(--rule);
  background: var(--bg);
  overflow-y: auto;
}

.related__title {
  margin-bottom: var(--space-3);
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.16em;
  line-height: 16px;
  text-transform: uppercase;
}

.related__group + .related__group {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--rule);
}

.related__heading {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: var(--space-2);
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
}

.related__heading span {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
}

.related__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.related__item {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 6px 8px;
  border-left: 2px solid var(--rule);
}

.related__item-title {
  color: var(--ink-2);
  font-size: 12px;
  line-height: 17px;
}

.related__item-meta {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 15px;
}

.related__item-said {
  display: -webkit-box;
  margin-top: 2px;
  overflow: hidden;
  color: var(--ink-3);
  font-size: 11px;
  line-height: 16px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.related__link {
  display: flex;
  flex-direction: column;
  gap: 1px;
  width: 100%;
  padding: 5px 8px;
  border: 0;
  border-left: 2px solid var(--rule);
  background: transparent;
  color: inherit;
  text-align: left;
}

.related__link:hover {
  border-left-color: var(--accent);
  background: var(--surface-2);
}

.related__link-fact {
  display: -webkit-box;
  overflow: hidden;
  color: var(--ink-2);
  font-size: 12px;
  line-height: 17px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.related__link-meta {
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 15px;
}

.related__note {
  color: var(--ink-3);
  font-size: 11px;
  line-height: 17px;
}

/* ---- 通用 -------------------------------------------------------- */

.memory__status {
  flex: none;
  margin: 0;
  padding: 6px var(--space-5);
  border-bottom: 1px solid var(--rule);
  background: var(--surface-2);
  color: var(--ok);
  font-size: 11px;
  line-height: 17px;
}

.memory__status[data-tone="error"] {
  color: var(--danger);
}

.memory__note,
.memory__hint {
  color: var(--ink-3);
  font-size: 12px;
  line-height: 18px;
}

.memory__note--rail {
  padding: var(--space-3) 6px;
}

.memory__link {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--accent);
  font-size: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.memory__hint {
  max-width: 36em;
  margin-top: var(--space-6);
}

@media (max-width: 1080px) {
  .memory,
  .memory--graph {
    grid-template-columns: 232px minmax(0, 1fr);
  }

  .memory__related {
    display: none;
  }
}

@media (max-width: 760px) {
  .memory,
  .memory--graph {
    grid-template-columns: 200px minmax(0, 1fr);
  }

  .mem-detail__scroll {
    padding: var(--space-4);
  }

  .mem-detail__bar {
    padding: var(--space-2) var(--space-4);
  }

  .mem-detail__fact {
    font-size: 18px;
    line-height: 29px;
  }
}
</style>
