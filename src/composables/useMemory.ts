/**
 * R3a 3.7 记忆管理页状态：列表 / 分组 / 来源回溯 / 删除。
 *
 * 只读 + 软删走壳侧（Rust `memory.rs`）；编辑、合并、手动添加需要重新生成
 * bge 向量，归 sidecar 的写接口（R3b），这里不伪造「存了但不生效」的记忆。
 */
import { computed, ref } from "vue";

import * as ipc from "../lib/ipc";

export type MemoryCategory = ipc.MemoryView["category"];

/** 分类展示顺序与中文标签（§4.4：偏好 / 人物 / 事件 / 属性）。 */
export const CATEGORY_ORDER: MemoryCategory[] = [
  "preference",
  "identity",
  "event",
  "other",
];

export const CATEGORY_LABELS: Record<MemoryCategory, string> = {
  preference: "偏好",
  identity: "人物 / 属性",
  event: "事件",
  other: "其他",
};

export interface MemoryGroup {
  category: MemoryCategory;
  label: string;
  rows: ipc.MemoryView[];
}

export function useMemory() {
  const items = ref<ipc.MemoryView[]>([]);
  const status = ref("");
  const loading = ref(false);
  const busyId = ref<string | null>(null);
  /** 展开来源回溯的 fact id → 使用它的 turn 列表 */
  const openId = ref<string | null>(null);
  const usage = ref<Record<string, ipc.MemoryUsage[]>>({});
  const usageStatus = ref("");
  // R3b 写接口（一次性 sidecar 进程，会加载一次 bge，按钮期间置忙）
  const draft = ref("");
  const draftCategory = ref<MemoryCategory>("other");
  const saving = ref(false);
  const mergeMode = ref(false);
  const selected = ref<string[]>([]);
  /** R5 批量导入：每行一条，可写 `事实|类别` */
  const bulkMode = ref(false);
  const bulkText = ref("");
  const bulkCategory = ref<MemoryCategory>("other");
  const bulkStatus = ref("");

  async function load(): Promise<void> {
    loading.value = true;
    status.value = "";
    try {
      items.value = await ipc.listMemories();
      if (items.value.length === 0) status.value = "还没有记住任何事。";
    } catch (err) {
      status.value = `读取记忆失败：${String(err)}`;
    } finally {
      loading.value = false;
    }
  }

  const groups = computed<MemoryGroup[]>(() => {
    const buckets = new Map<MemoryCategory, ipc.MemoryView[]>();
    for (const item of items.value) {
      const list = buckets.get(item.category) ?? [];
      list.push(item);
      buckets.set(item.category, list);
    }
    return CATEGORY_ORDER.filter((category) => buckets.has(category)).map(
      (category) => ({
        category,
        label: CATEGORY_LABELS[category],
        rows: buckets.get(category) ?? [],
      }),
    );
  });

  async function toggleUsage(item: ipc.MemoryView): Promise<void> {
    if (openId.value === item.id) {
      openId.value = null;
      return;
    }
    openId.value = item.id;
    if (usage.value[item.id] !== undefined) return;
    usageStatus.value = "";
    try {
      usage.value = {
        ...usage.value,
        [item.id]: await ipc.memoryUsage(item.id),
      };
    } catch (err) {
      usageStatus.value = `读取来源失败：${String(err)}`;
    }
  }

  /** 无 UI 的删除：确认交给页面里的 DsConfirmDialog。 */
  async function deleteFact(item: ipc.MemoryView): Promise<boolean> {
    if (busyId.value !== null) return false;
    busyId.value = item.id;
    try {
      await ipc.deleteMemory(item.id);
      if (openId.value === item.id) openId.value = null;
      await load();
      status.value = "已删除（向量在下次 sidecar 启动时清理）";
      return true;
    } catch (err) {
      status.value = `删除失败：${String(err)}`;
      return false;
    } finally {
      busyId.value = null;
    }
  }

  /** 兼容旧调用：确认仍在原生 confirm，MemoryPage 已改用对话框。 */
  async function remove(item: ipc.MemoryView): Promise<void> {
    if (
      !window.confirm(
        `删除这条记忆？\n\n「${item.fact}」\n\n删除后不再参与检索；原文与历史对话不受影响。`,
      )
    ) {
      return;
    }
    await deleteFact(item);
  }

  async function addFact(): Promise<void> {
    const text = draft.value.trim();
    if (!text || saving.value) return;
    saving.value = true;
    status.value = "";
    try {
      await ipc.addMemory(text, draftCategory.value);
      draft.value = "";
      await load();
      status.value = "已添加一条记忆";
    } catch (err) {
      status.value = `添加失败：${String(err)}`;
    } finally {
      saving.value = false;
    }
  }

  /** 无 UI 的更新：对话框负责取文本与校验。 */
  async function updateFact(
    item: ipc.MemoryView,
    text: string,
  ): Promise<boolean> {
    const value = text.trim();
    if (!value || saving.value) return false;
    saving.value = true;
    status.value = "";
    try {
      await ipc.updateMemory(item.id, value, item.category);
      await load();
      status.value = "已更新（旧版本被取代，不再参与检索）";
      return true;
    } catch (err) {
      status.value = `更新失败：${String(err)}`;
      return false;
    } finally {
      saving.value = false;
    }
  }

  /** 兼容旧调用：prompt 版本，MemoryPage 已改用 DsTextDialog。 */
  async function editItem(item: ipc.MemoryView): Promise<void> {
    const next = window.prompt("修改这条记忆（旧版本保留在历史里）", item.fact);
    if (next === null) return;
    await updateFact(item, next);
  }

  function toggleSelect(id: string): void {
    selected.value = selected.value.includes(id)
      ? selected.value.filter((item) => item !== id)
      : [...selected.value, id];
  }

  function toggleMergeMode(): void {
    mergeMode.value = !mergeMode.value;
    if (!mergeMode.value) selected.value = [];
  }

  /** R5 批量导入：一次嵌入，逐条落库；同文（含批内重复）跳过。 */
  async function importBulk(): Promise<void> {
    const text = bulkText.value.trim();
    if (!text || saving.value) return;
    saving.value = true;
    bulkStatus.value = "";
    try {
      const result = await ipc.importMemories(text);
      bulkText.value = "";
      bulkStatus.value = `已添加 ${result.added} 条，跳过重复 ${result.skipped} 条`;
      await load();
    } catch (err) {
      bulkStatus.value = `批量导入失败：${String(err)}`;
    } finally {
      saving.value = false;
    }
  }

  function toggleBulkMode(): void {
    bulkMode.value = !bulkMode.value;
    bulkStatus.value = "";
  }

  /** 无 UI 的合并：ids 与文本由对话框提供。 */
  async function mergeFacts(ids: string[], text: string): Promise<boolean> {
    const value = text.trim();
    if (ids.length < 2 || !value || saving.value) return false;
    const chosen = items.value.filter((item) => ids.includes(item.id));
    const category = chosen[0]?.category ?? "other";
    saving.value = true;
    status.value = "";
    try {
      await ipc.mergeMemories(ids, value, category);
      selected.value = [];
      mergeMode.value = false;
      await load();
      status.value = "已合并";
      return true;
    } catch (err) {
      status.value = `合并失败：${String(err)}`;
      return false;
    } finally {
      saving.value = false;
    }
  }

  /** 兼容旧调用：prompt 版本，MemoryPage 已改用 DsTextDialog。 */
  async function mergeSelected(): Promise<void> {
    if (selected.value.length < 2 || saving.value) return;
    const chosen = items.value.filter((item) => selected.value.includes(item.id));
    const joined = chosen.map((item) => item.fact).join("；");
    const next = window.prompt("合并后的记忆（会取代所选条目）", joined);
    if (next === null) return;
    await mergeFacts(selected.value, next);
  }

  function noteFor(item: ipc.MemoryView): string {
    const created = new Date(item.createdAt * 1000).toLocaleDateString("zh-CN");
    const source = item.sourceSessionTitle
      ? `来源：${item.sourceSessionTitle}${
          item.sourceTurnSeq ? ` · 第 ${item.sourceTurnSeq} 轮` : ""
        }`
      : "来源：手动/早期记录";
    return `${source} · ${created}`;
  }

  function clock(value: number): string {
    return new Date(value * 1000).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return {
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
    bulkMode,
    bulkText,
    bulkCategory,
    bulkStatus,
    importBulk,
    toggleBulkMode,
    load,
    toggleUsage,
    remove,
    deleteFact,
    updateFact,
    mergeFacts,
    addFact,
    editItem,
    toggleSelect,
    toggleMergeMode,
    mergeSelected,
    noteFor,
    clock,
  };
}
