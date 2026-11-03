import { ref } from "vue";

import * as ipc from "../lib/ipc";

/** R1a 恢复面：marker 存在时才显示；还原必须由用户显式触发。 */
export function useRecovery() {
  const recovery = ref<ipc.RecoveryStatus | null>(null);
  const choice = ref("");
  const busy = ref(false);
  const notice = ref("");
  /** 手动打开（错误态入口）：即使没有迁移 marker 也能查看备份 */
  const showManual = ref(false);

  async function load(): Promise<void> {
    try {
      const status = await ipc.recoveryStatus();
      // 启动时只在迁移失败才弹；用户从错误态手动打开时无条件列出可用备份
      if (status.failed || showManual.value) {
        recovery.value = status;
        choice.value = status.backups[0]?.path ?? "";
      }
    } catch (err) {
      console.warn("recovery status unavailable:", err);
    }
  }

  function open(): void {
    showManual.value = true;
    void load();
  }

  function close(): void {
    showManual.value = false;
  }

  async function restore(): Promise<void> {
    if (!choice.value || busy.value) return;
    busy.value = true;
    notice.value = "";
    try {
      await ipc.recoveryRestore(choice.value);
      notice.value = "备份已还原。请退出并重新打开 Echoes。";
    } catch (err) {
      notice.value = `还原失败：${String(err)}`;
    } finally {
      busy.value = false;
    }
  }

  return { recovery, choice, busy, notice, showManual, load, open, close, restore };
}
