<script setup lang="ts">
import { onMounted, ref } from "vue";

import PageHeader from "../components/layout/PageHeader.vue";
import DsButton from "../components/ui/DsButton.vue";
import DsCard from "../components/ui/DsCard.vue";
import DsSkin from "../components/ui/DsSkin.vue";
import * as ipc from "../lib/ipc";

const version = ref("0.1.0");
const busy = ref("");
const status = ref("");
const failed = ref(false);

onMounted(async () => {
  try {
    const { getVersion } = await import("@tauri-apps/api/app");
    version.value = await getVersion();
  } catch {
    // 浏览器预览 / 非 Tauri 环境：保留 package.json 的基线版本。
  }
});

async function backup(): Promise<void> {
  busy.value = "backup";
  status.value = "";
  failed.value = false;
  try {
    const path = await ipc.dataBackup();
    status.value = `备份已生成：${path}`;
  } catch {
    failed.value = true;
    status.value = "备份失败。确认 sidecar 已启动后再试。";
  } finally {
    busy.value = "";
  }
}

async function diagnostics(): Promise<void> {
  busy.value = "diagnostics";
  status.value = "";
  failed.value = false;
  try {
    const result = await ipc.dataDiagnostics();
    status.value = `诊断包已生成：${result.path}`;
  } catch {
    failed.value = true;
    status.value = "诊断包导出失败。确认 sidecar 已启动后再试。";
  } finally {
    busy.value = "";
  }
}
</script>

<template>
  <DsSkin class="about-skin">
      <PageHeader
        eyebrow="About"
        title="关于 Echoes"
        description="本机优先的声音伴侣。原文、记忆与音色都留在本机；云端推理只做无状态请求。"
      />

      <main class="about">
        <DsCard padding="lg">
          <div class="about__row">
            <div>
              <p class="about__label">版本</p>
              <p class="about__value">{{ version }}</p>
            </div>
            <span class="about__badge">本机运行</span>
          </div>
          <p class="about__note">
            侧栏里的「设置」会打开独立窗口；这里只放版本、备份与诊断，不重复引擎配置。
          </p>
        </DsCard>

        <DsCard padding="lg">
          <p class="about__title">数据与诊断</p>
          <p class="about__note">
            备份包含数据库；诊断包包含脱敏设置、日志与版本信息，不包含云端 key。
          </p>
          <div class="about__actions">
            <DsButton
              :loading="busy === 'backup'"
              :disabled="busy !== ''"
              @click="backup"
            >
              立即备份
            </DsButton>
            <DsButton
              :loading="busy === 'diagnostics'"
              :disabled="busy !== ''"
              @click="diagnostics"
            >
              导出诊断包
            </DsButton>
          </div>
          <p v-if="status" class="about__status" :data-tone="failed ? 'error' : 'ok'">
            {{ status }}
          </p>
        </DsCard>

        <DsCard padding="lg">
          <p class="about__title">隐私</p>
          <ul class="about__list">
            <li>对话原文、记忆与音色只存在本机；没有账号、云同步或分享链接。</li>
            <li>云端引擎只做无状态推理；选了云端才会出网，失败时报错，不静默降级。</li>
            <li>隐私模式会阻断任何公网端点；本机环回地址不受影响。</li>
          </ul>
        </DsCard>

        <p class="about__foot">
          Echoes · MIT 许可的第三方组件与模型许可见安装目录的 MODEL-LICENSES.md。
        </p>
      </main>
  </DsSkin>
</template>

<style scoped>
.about-skin {
  flex: 1;
  min-height: 0;
}

.about {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  width: min(720px, 100%);
  padding: var(--space-6);
}

.about__row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
}

.about__label {
  color: var(--ink-3);
  font-size: 12px;
  line-height: 16px;
}

.about__value {
  margin-top: 2px;
  color: var(--ink);
  font-family: var(--font-mono);
  font-size: 20px;
  line-height: 28px;
}

.about__badge {
  padding: 3px 8px;
  border: 1px solid var(--rule);
  border-radius: var(--radius-pill);
  color: var(--ink-3);
  font-size: 11px;
}

.about__title {
  color: var(--ink);
  font-size: 14px;
  font-weight: 600;
  line-height: 20px;
}

.about__note {
  margin-top: var(--space-2);
  color: var(--ink-2);
  font-size: 13px;
  line-height: 20px;
}

.about__actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.about__status {
  margin-top: var(--space-3);
  color: var(--ok);
  font-size: 12px;
  line-height: 18px;
  overflow-wrap: anywhere;
}

.about__status[data-tone="error"] {
  color: var(--danger);
}

.about__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-2);
  color: var(--ink-2);
  font-size: 13px;
  line-height: 20px;
}

.about__list li {
  position: relative;
  padding-left: 14px;
}

.about__list li::before {
  content: "";
  position: absolute;
  top: 9px;
  left: 2px;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--accent);
}

.about__foot {
  color: var(--ink-3);
  font-size: 12px;
  line-height: 18px;
}
</style>
