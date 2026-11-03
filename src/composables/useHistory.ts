import { computed, ref } from "vue";

import * as ipc from "../lib/ipc";

export interface HistoryMessage {
  role: "user" | "assistant";
  text: string;
  at: number;
  interrupted?: boolean;
  /** R4 4.4：被新版本取代（只在「查看完整历史」里出现） */
  superseded?: boolean;
  /** R4 4.3：质检判定「无记忆支撑」的说法（未质检为空） */
  unsupported?: string[];
}

/** 会话列表分组（1c.1）：今天 / 本周 / 更早。 */
export interface SessionGroup {
  label: string;
  rows: ipc.SessionView[];
}

/** 搜索/预览里的一小段文本：`hit` 为命中的高亮片段（1c.2）。 */
export interface TextSegment {
  text: string;
  hit: boolean;
}

const DAY_SECONDS = 86_400;

export function historyTurnRows(turn: ipc.TurnView): HistoryMessage[] {
  const at = turn.startedAt * 1000;
  const superseded = turn.supersededBy !== null;
  const unsupported = parseClaims(turn);
  const rows: HistoryMessage[] = [
    { role: "user", text: turn.userText, at, superseded },
  ];
  if (turn.assistantText) {
    rows.push({
      role: "assistant",
      text: turn.assistantText,
      at: (turn.endedAt ?? turn.startedAt) * 1000,
      interrupted: turn.status === "cancelled",
      superseded,
      unsupported,
    });
  }
  return rows;
}

/** 质检说法清单（坏 JSON 当作「没有结论」，不阻塞历史显示）。 */
function parseClaims(turn: ipc.TurnView): string[] {
  if (turn.groundingVerdict !== "unfaithful" || !turn.groundingClaims) return [];
  try {
    const parsed: unknown = JSON.parse(turn.groundingClaims);
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

/**
 * R1c 历史 / 会话切换。UI 只做渲染；写入与活跃会话切换由 sidecar/Rust 负责。
 * `replaceMessages` 由页面提供，避免 composable 直接持有聊天状态。
 *
 * 1c.7：「查看历史」与「继续对话」分离——点会话只进只读预览（`preview`），
 * 真正切换活跃会话必须显式点「继续对话」。
 */
export function useHistory(
  replaceMessages: (rows: HistoryMessage[]) => void,
) {
  const showHistory = ref(false);
  const sessions = ref<ipc.SessionView[]>([]);
  const activeSessionId = ref("");
  const showArchived = ref(false);
  /** R4 4.4：只读回看里是否包含被取代的轮次（活跃会话线程永远只显示当前版本） */
  const showSuperseded = ref(false);
  const query = ref("");
  const hits = ref<ipc.TurnView[]>([]);
  const status = ref("");
  const busy = ref(false);
  const preview = ref<{ session: ipc.SessionView; rows: HistoryMessage[] } | null>(null);
  const previewBusy = ref(false);

  async function loadSessions(): Promise<void> {
    try {
      sessions.value = await ipc.sessionList(showArchived.value);
      const current = sessions.value.find((item) => item.id === activeSessionId.value);
      const firstActive = sessions.value.find((item) => item.archivedAt === null);
      if (!current && firstActive) {
        activeSessionId.value = firstActive.id;
      }
      if (preview.value) {
        // 改名/归档后预览头衔要跟着更新；被删掉则退出预览
        const found = sessions.value.find((item) => item.id === preview.value?.session.id);
        if (!found) preview.value = null;
        else preview.value = { ...preview.value, session: found };
      }
    } catch (err) {
      status.value = `读取会话失败：${String(err)}`;
    }
  }

  async function open(): Promise<void> {
    showHistory.value = true;
    query.value = "";
    hits.value = [];
    preview.value = null;
    await loadSessions();
  }

  function title(session: ipc.SessionView): string {
    return session.title?.trim() || "未命名对话";
  }

  function time(value: number): string {
    return new Date(value * 1000).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /** 今天 / 本周（近 7 天）/ 更早。空组不渲染。 */
  const groups = computed<SessionGroup[]>(() => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000;
    const week = today - 6 * DAY_SECONDS;
    const buckets: SessionGroup[] = [
      { label: "今天", rows: [] },
      { label: "本周", rows: [] },
      { label: "更早", rows: [] },
    ];
    for (const session of sessions.value) {
      // 排序口径与列表一致：最近活跃优先
      const at = session.lastActiveAt;
      if (at >= today) buckets[0].rows.push(session);
      else if (at >= week) buckets[1].rows.push(session);
      else buckets[2].rows.push(session);
    }
    return buckets.filter((bucket) => bucket.rows.length > 0);
  });

  /** 高亮片段：按当前搜索词切分，无命中时返回整段原文。 */
  function segments(text: string): TextSegment[] {
    const needle = query.value.trim();
    if (!needle) return [{ text, hit: false }];
    const lower = text.toLowerCase();
    const target = needle.toLowerCase();
    const out: TextSegment[] = [];
    let from = 0;
    for (;;) {
      const at = lower.indexOf(target, from);
      if (at < 0) break;
      if (at > from) out.push({ text: text.slice(from, at), hit: false });
      out.push({ text: text.slice(at, at + needle.length), hit: true });
      from = at + needle.length;
    }
    if (out.length === 0) return [{ text, hit: false }];
    if (from < text.length) out.push({ text: text.slice(from), hit: false });
    return out;
  }

  async function loadTurns(sessionId: string): Promise<void> {
    const turns = await ipc.historyList(sessionId, 100, 0);
    replaceMessages(turns.slice().reverse().flatMap(historyTurnRows));
    activeSessionId.value = sessionId;
  }

  /** 只读预览：不切活跃会话，不写库（1c.3）。 */
  async function previewSession(session: ipc.SessionView): Promise<void> {
    if (previewBusy.value) return;
    previewBusy.value = true;
    status.value = "";
    try {
      const turns = await ipc.historyList(
        session.id,
        100,
        0,
        showSuperseded.value
      );
      preview.value = {
        session,
        rows: turns.slice().reverse().flatMap(historyTurnRows),
      };
    } catch (err) {
      status.value = `读取会话失败：${String(err)}`;
    } finally {
      previewBusy.value = false;
    }
  }

  function closePreview(): void {
    preview.value = null;
  }

  /** 勾选「显示被取代」后重载当前只读预览（活跃线程不受影响）。 */
  async function reloadPreview(): Promise<void> {
    if (!preview.value) return;
    await previewSession(preview.value.session);
  }

  /** 显式「继续对话」：此时才切活跃会话并回填上下文（1c.7）。 */
  async function openSession(session: ipc.SessionView): Promise<void> {
    if (busy.value) return;
    busy.value = true;
    status.value = "";
    try {
      await ipc.sessionOpen(session.id);
      await loadTurns(session.id);
      preview.value = null;
      showHistory.value = false;
    } catch (err) {
      status.value = `切换会话失败：${String(err)}`;
    } finally {
      busy.value = false;
    }
  }

  async function continuePreview(): Promise<void> {
    if (preview.value) await openSession(preview.value.session);
  }

  async function create(): Promise<void> {
    if (busy.value) return;
    busy.value = true;
    status.value = "";
    try {
      const created = await ipc.sessionCreate();
      await ipc.sessionOpen(created.id);
      activeSessionId.value = created.id;
      replaceMessages([]);
      preview.value = null;
      showHistory.value = false;
      await loadSessions();
    } catch (err) {
      status.value = `新建会话失败：${String(err)}`;
    } finally {
      busy.value = false;
    }
  }

  async function rename(session: ipc.SessionView): Promise<void> {
    const next = window.prompt("会话标题", title(session));
    if (!next || !next.trim()) return;
    try {
      await ipc.sessionRename(session.id, next.trim());
      await loadSessions();
    } catch (err) {
      status.value = `改名失败：${String(err)}`;
    }
  }

  async function archive(session: ipc.SessionView): Promise<void> {
    if (!window.confirm(`归档「${title(session)}」？归档不会删除原文。`)) return;
    try {
      await ipc.sessionArchive(session.id);
      if (activeSessionId.value === session.id) {
        await pickActiveAfterRemoval();
      } else {
        await loadSessions();
      }
    } catch (err) {
      status.value = `归档失败：${String(err)}`;
    }
  }

  async function remove(session: ipc.SessionView): Promise<void> {
    if (!window.confirm(`彻底删除「${title(session)}」？原文与摘要会一起删除。`)) return;
    try {
      await ipc.sessionDelete(session.id);
      if (activeSessionId.value === session.id) {
        await pickActiveAfterRemoval();
      } else {
        await loadSessions();
      }
    } catch (err) {
      status.value = `删除失败：${String(err)}`;
    }
  }

  async function pickActiveAfterRemoval(): Promise<void> {
    activeSessionId.value = "";
    replaceMessages([]);
    preview.value = null;
    await loadSessions();
    const firstActive = sessions.value.find((item) => item.archivedAt === null);
    if (firstActive) {
      await ipc.sessionOpen(firstActive.id);
      await loadTurns(firstActive.id);
      return;
    }
    const created = await ipc.sessionCreate();
    await ipc.sessionOpen(created.id);
    activeSessionId.value = created.id;
    await loadSessions();
  }

  async function search(): Promise<void> {
    const text = query.value.trim();
    if (!text) {
      hits.value = [];
      return;
    }
    try {
      hits.value = await ipc.historySearch(text, undefined, 50, 0);
    } catch (err) {
      status.value = `搜索失败：${String(err)}`;
    }
  }

  /** 搜索命中 → 只读预览对应会话（再显式「继续对话」才切换）。 */
  async function openHit(hit: ipc.TurnView): Promise<void> {
    const known = sessions.value.find((item) => item.id === hit.sessionId);
    const session: ipc.SessionView = known ?? {
      id: hit.sessionId,
      title: null,
      startedAt: hit.startedAt,
      lastActiveAt: hit.startedAt,
      archivedAt: null,
    };
    await previewSession(session);
  }

  return {
    showHistory,
    sessions,
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
    open,
    title,
    time,
    segments,
    loadSessions,
    previewSession,
    closePreview,
    reloadPreview,
    continuePreview,
    openSession,
    create,
    rename,
    archive,
    remove,
    search,
    openHit,
  };
}
