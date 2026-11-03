<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";

import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  useMemory,
} from "../composables/useMemory";

const router = useRouter();
const {
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
  bulkMode,
  bulkText,
  bulkCategory,
  bulkStatus,
  importBulk,
  toggleBulkMode,
  load,
  toggleUsage,
  remove,
  addFact,
  editItem,
  toggleSelect,
  toggleMergeMode,
  mergeSelected,
  noteFor,
  clock,
} = useMemory();

onMounted(() => {
  void load();
});
</script>

<template>
  <main class="memory">
    <header class="head">
      <div>
        <p class="eyebrow">记忆</p>
        <h1>她记得的事</h1>
        <p class="lede">
          只显示仍在生效的事实；被取代或删除的不再参与检索，原文与历史对话不受影响。
        </p>
      </div>
      <div class="actions">
        <button type="button" class="quiet" :disabled="loading" @click="load">
          {{ loading ? "读取中…" : "刷新" }}
        </button>
        <button type="button" class="ghost" @click="router.push('/')">
          回到对话
        </button>
      </div>
    </header>

    <p v-if="status" class="status">{{ status }}</p>

    <section class="compose">
      <input
        v-model="draft"
        type="text"
        maxlength="500"
        placeholder="手动添加一条记忆（例如：用户喜欢在雨天听爵士）"
        @keydown.enter="addFact"
      />
      <select v-model="draftCategory">
        <option
          v-for="category in CATEGORY_ORDER"
          :key="category"
          :value="category"
        >
          {{ CATEGORY_LABELS[category] }}
        </option>
      </select>
      <button
        type="button"
        class="ghost"
        :disabled="saving || draft.trim() === ''"
        @click="addFact"
      >
        {{ saving ? "保存中…" : "添加" }}
      </button>
    </section>
    <p class="hint">
      写入会重新生成向量（需要 bge 权重），首次保存可能要几秒。
    </p>

    <div class="merge-bar">
      <button type="button" class="quiet" @click="toggleMergeMode">
        {{ mergeMode ? "退出合并" : "合并重复" }}
      </button>
      <button type="button" class="quiet" @click="toggleBulkMode">
        {{ bulkMode ? "收起批量导入" : "批量导入" }}
      </button>
      <template v-if="mergeMode">
        <span class="hint">已选 {{ selected.length }} 条</span>
        <button
          type="button"
          class="ghost"
          :disabled="saving || selected.length < 2"
          @click="mergeSelected"
        >
          {{ saving ? "合并中…" : "合并所选" }}
        </button>
      </template>
    </div>

    <section v-if="bulkMode" class="compose bulk">
      <textarea
        v-model="bulkText"
        rows="6"
        placeholder="每行一条；也可写「事实|类别」。类别：preference / identity / event / other"
      ></textarea>
      <div class="bulk-row">
        <select v-model="bulkCategory">
          <option
            v-for="category in CATEGORY_ORDER"
            :key="category"
            :value="category"
          >
            {{ CATEGORY_LABELS[category] }}（默认）
          </option>
        </select>
        <button
          type="button"
          class="ghost"
          :disabled="saving || bulkText.trim() === ''"
          @click="importBulk"
        >
          {{ saving ? "导入中…" : "批量导入" }}
        </button>
      </div>
    </section>
    <p v-if="bulkStatus" class="hint">{{ bulkStatus }}</p>

    <section v-for="group in groups" :key="group.category" class="group">
      <h2>
        {{ group.label }}
        <span class="count">{{ group.rows.length }}</span>
      </h2>
      <ul class="facts">
        <li v-for="item in group.rows" :key="item.id" class="fact-card">
          <p class="fact">{{ item.fact }}</p>
          <p class="meta">{{ noteFor(item) }}</p>
          <div class="row-actions">
            <label v-if="mergeMode" class="select">
              <input
                type="checkbox"
                :checked="selected.includes(item.id)"
                @change="toggleSelect(item.id)"
              />
              <span>选中</span>
            </label>
            <button
              type="button"
              class="quiet"
              :disabled="saving"
              @click="editItem(item)"
            >
              编辑
            </button>
            <button type="button" class="quiet" @click="toggleUsage(item)">
              {{ openId === item.id ? "收起来源" : "看过它的回复" }}
            </button>
            <button
              type="button"
              class="quiet danger"
              :disabled="busyId === item.id"
              @click="remove(item)"
            >
              {{ busyId === item.id ? "删除中…" : "删除" }}
            </button>
          </div>

          <div v-if="openId === item.id" class="usage">
            <p v-if="usageStatus" class="status">{{ usageStatus }}</p>
            <ul v-if="(usage[item.id] ?? []).length">
              <li v-for="hit in usage[item.id]" :key="hit.turnId">
                <span class="when">
                  {{ hit.sessionTitle || "未命名会话" }} · 第 {{ hit.seq }} 轮 ·
                  {{ clock(hit.usedAt) }}
                </span>
                <span class="said">{{ hit.userText }}</span>
              </li>
            </ul>
            <p v-else class="meta">还没有回复用过这条记忆。</p>
          </div>
        </li>
      </ul>
    </section>

    <p v-if="!loading && groups.length === 0 && !status" class="status">
      还没有记住任何事。
    </p>
  </main>
</template>

<style scoped>
.memory {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 28px clamp(20px, 6vw, 72px) 64px;
  color: var(--ink);
}

.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--rule);
}

.eyebrow {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--ink-3);
}

h1 {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 600;
}

.lede {
  margin-top: 6px;
  max-width: 46ch;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--ink-2);
}

.actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.status {
  margin-top: 14px;
  font-size: 12.5px;
  color: var(--ink-3);
}

.group {
  margin-top: 26px;
}

.group h2 {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-2);
}

.count {
  font-size: 10px;
  color: var(--ink-3);
}

.facts {
  display: grid;
  gap: 10px;
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}

.fact-card {
  padding: 12px 14px;
  border: 1px solid var(--rule);
  border-radius: 10px;
  background: var(--paper-hi, #fffdf9);
}

.fact {
  font-size: 14px;
  line-height: 1.65;
}

.meta {
  margin-top: 4px;
  font-size: 11.5px;
  color: var(--ink-3);
}

.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.compose {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.compose input {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: var(--paper-hi, #fffdf9);
  color: var(--ink);
  font: inherit;
}

.compose select {
  padding: 8px;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: var(--paper-hi, #fffdf9);
  color: var(--ink);
}

/* R5 批量导入：textarea 独占一行，类别与按钮在下一行 */
.compose.bulk {
  flex-direction: column;
}

.compose.bulk textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--rule);
  border-radius: 8px;
  background: var(--paper-hi, #fffdf9);
  color: var(--ink);
  font: inherit;
  line-height: 1.6;
  resize: vertical;
}

.bulk-row {
  display: flex;
  gap: 8px;
}

.hint {
  margin-top: 6px;
  font-size: 11.5px;
  color: var(--ink-3);
}

.merge-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.merge-bar .hint {
  margin-top: 0;
}

.select {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11.5px;
  color: var(--ink-2);
}

.row-actions .danger {
  color: var(--danger);
}

.usage {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--rule);
}

.usage ul {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.usage li {
  display: grid;
  gap: 2px;
}

.when {
  font-size: 11px;
  color: var(--ink-3);
}

.said {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--ink-2);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
