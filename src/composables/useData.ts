import { ref } from "vue";

import * as ipc from "../lib/ipc";

/** R5 数据面：导出 / 备份 / 导入 / 诊断包 / 彻底删除。页面只渲染结果。 */
export function useData() {
  const status = ref("");
  const busy = ref(false);
  const exportPath = ref("");
  const importPath = ref("");
  const diagnosticsPath = ref("");
  const backups = ref<ipc.RecoveryBackup[]>([]);
  const backupsStatus = ref("");
  const wipeConfirm = ref("");
  const wiped = ref(false);

  async function loadBackups(): Promise<void> {
    backupsStatus.value = "读取中…";
    try {
      const current = await ipc.recoveryStatus();
      backups.value = current.backups;
      backupsStatus.value = current.backups.length
        ? ""
        : "backup 目录里还没有备份。";
    } catch (err) {
      backupsStatus.value = `读取备份失败：${String(err)}`;
    }
  }

  async function exportData(): Promise<void> {
    if (busy.value) return;
    busy.value = true;
    status.value = "";
    try {
      const result = await ipc.dataExport();
      exportPath.value = result.path;
      status.value = `已导出 ${result.sessions} 段对话 / ${result.turns} 轮 / ${result.memories} 条记忆（${formatBytes(result.bytes)}）`;
    } catch (err) {
      status.value = `导出失败：${String(err)}`;
    } finally {
      busy.value = false;
    }
  }

  async function backupNow(): Promise<void> {
    if (busy.value) return;
    busy.value = true;
    status.value = "";
    try {
      const path = await ipc.dataBackup();
      status.value = `已备份到 ${path}`;
      await loadBackups();
    } catch (err) {
      status.value = `备份失败：${String(err)}`;
    } finally {
      busy.value = false;
    }
  }

  async function importData(): Promise<void> {
    const path = importPath.value.trim();
    if (!path || busy.value) return;
    busy.value = true;
    status.value = "";
    try {
      const result = await ipc.dataImport(path);
      status.value = `已导入 ${result.sessions} 段对话 / ${result.turns} 轮 / ${result.memories} 条记忆；重新打开 Echoes 后生效。`;
      importPath.value = "";
    } catch (err) {
      status.value = `导入失败：${String(err)}`;
    } finally {
      busy.value = false;
    }
  }

  async function exportDiagnostics(): Promise<void> {
    if (busy.value) return;
    busy.value = true;
    status.value = "";
    try {
      const result = await ipc.dataDiagnostics();
      diagnosticsPath.value = result.path;
      status.value = `诊断包已导出（${formatBytes(result.bytes)}，不含对话原文与 key）`;
    } catch (err) {
      status.value = `导出诊断包失败：${String(err)}`;
    } finally {
      busy.value = false;
    }
  }

  async function wipeAll(): Promise<void> {
    if (busy.value) return;
    const confirm = wipeConfirm.value.trim();
    if (!confirm) {
      status.value = "请输入确认语后再删除。";
      return;
    }
    busy.value = true;
    status.value = "";
    try {
      const result = await ipc.dataWipe(confirm);
      wiped.value = true;
      wipeConfirm.value = "";
      status.value = `已删除 ${result.removed.length} 项个人数据${
        result.clearedKeys.length ? "，并清除了云端 key" : ""
      }。请退出并重新打开 Echoes。`;
    } catch (err) {
      status.value = `删除失败：${String(err)}`;
    } finally {
      busy.value = false;
    }
  }

  return {
    status,
    busy,
    exportPath,
    importPath,
    diagnosticsPath,
    backups,
    backupsStatus,
    wipeConfirm,
    wiped,
    loadBackups,
    exportData,
    backupNow,
    importData,
    exportDiagnostics,
    wipeAll,
  };
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
