<template>
  <main class="shared-shell">
    <div class="shared-glow"></div>
    <div class="container shared-page">
      <header class="page-header">
        <button class="back-btn" @click="goBack">
          <span class="back-arrow">←</span>
          {{ t("voices.back") }}
        </button>
        <div class="header-content">
          <p class="eyebrow">{{ t("voices.sharedEyebrow") }}</p>
          <h1 class="title">{{ t("voices.sharedTitle") }}</h1>
          <p class="subtitle">{{ t("voices.sharedSubtitle") }}</p>
        </div>
      </header>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <p>{{ t("voices.loading") }}</p>
      </div>

      <!-- 空状态 -->
      <div v-else-if="receivedGrants.length === 0" class="empty-state">
        <div class="empty-icon">🎁</div>
        <h3>{{ t("voices.noSharedTitle") }}</h3>
        <p>{{ t("voices.noSharedDesc") }}</p>
        <router-link class="ghost-cta" to="/voices">
          {{ t("voices.goToVoices") }}
        </router-link>
      </div>

      <!-- 分享列表 -->
      <div v-else class="shared-grid">
        <div
          v-for="grant in receivedGrants"
          :key="grant.grantId"
          class="shared-card"
          @click="goToVoice(grant.voiceAssetId)"
        >
          <div class="card-header">
            <div class="voice-icon">🎧</div>
            <div v-if="isExpired(grant.expiresAt)" class="expired-badge">
              {{ t("voices.expired") }}
            </div>
          </div>

          <div class="card-body">
            <h3 class="voice-name">{{ grant.voiceAssetName || t("voices.unknownVoice") }}</h3>
            <p class="from-info">
              {{ t("voices.sharedFrom", { name: grant.grantorName || t("voices.unknown") }) }}
            </p>
            <div class="grant-meta">
              <span class="permission-tag">
                {{ getPermissionText(grant.permission) }}
              </span>
              <span v-if="grant.expiresAt" class="expire-time">
                {{ t("voices.expireAt", { date: formatDate(grant.expiresAt) }) }}
              </span>
            </div>
          </div>

          <div class="card-actions">
            <button
              v-if="!isExpired(grant.expiresAt)"
              class="action-btn primary"
              @click.stop="startChat(grant.voiceAssetId)"
            >
              {{ t("voices.useVoice") }}
            </button>
            <button
              class="action-btn ghost"
              @click.stop="showDetail(grant)"
            >
              {{ t("voices.viewDetail") }}
            </button>
          </div>
        </div>
      </div>

      <!-- 详情弹窗 -->
      <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
        <div class="modal-content">
          <div class="modal-header">
            <h2>{{ t("voices.grantDetail") }}</h2>
            <button class="modal-close" @click="showModal = false">×</button>
          </div>
          <div class="modal-body" v-if="selectedGrant">
            <div class="detail-section">
              <h4>{{ t("voices.voiceInfo") }}</h4>
              <div class="detail-row">
                <span class="label">{{ t("voices.voiceName") }}</span>
                <span class="value">{{ selectedGrant.voiceAssetName || "-" }}</span>
              </div>
            </div>
            <div class="detail-section">
              <h4>{{ t("voices.grantorInfo") }}</h4>
              <div class="detail-row">
                <span class="label">{{ t("voices.grantorName") }}</span>
                <span class="value">{{ selectedGrant.grantorName || "-" }}</span>
              </div>
            </div>
            <div class="detail-section">
              <h4>{{ t("voices.permissionInfo") }}</h4>
              <div class="detail-row">
                <span class="label">{{ t("voices.permission") }}</span>
                <span class="value">{{ getPermissionText(selectedGrant.permission) }}</span>
              </div>
              <div class="detail-row">
                <span class="label">{{ t("voices.expireTime") }}</span>
                <span class="value">{{ selectedGrant.expiresAt ? formatDate(selectedGrant.expiresAt) : t("voices.neverExpire") }}</span>
              </div>
            </div>
            <div class="detail-section">
              <h4>{{ t("voices.shareTime") }}</h4>
              <div class="detail-row">
                <span class="label">{{ t("voices.sharedAt") }}</span>
                <span class="value">{{ formatDateTime(selectedGrant.createTime) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { getReceivedGrants, type ReceivedGrant } from "../../services/modules/voice.api";

const { t } = useI18n();
const router = useRouter();

const loading = ref(true);
const receivedGrants = ref<ReceivedGrant[]>([]);
const showModal = ref(false);
const selectedGrant = ref<ReceivedGrant | null>(null);

const goBack = () => {
  router.push("/voices");
};

const goToVoice = (voiceAssetId: string) => {
  router.push(`/voices/${voiceAssetId}`);
};

const startChat = (voiceAssetId: string) => {
  router.push(`/chat?voiceAssetId=${voiceAssetId}`);
};

const showDetail = (grant: ReceivedGrant) => {
  selectedGrant.value = grant;
  showModal.value = true;
};

const isExpired = (expiresAt?: string): boolean => {
  if (!expiresAt) return false;
  return new Date(expiresAt) < new Date();
};

const getPermissionText = (permission: string): string => {
  const map: Record<string, string> = {
    USE: t("voices.permissionUse"),
    FULL: t("voices.permissionFull"),
  };
  return map[permission] || permission;
};

const formatDate = (date: string): string => {
  return new Date(date).toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
};

const formatDateTime = (date: string): string => {
  return new Date(date).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const fetchReceivedGrants = async () => {
  try {
    loading.value = true;
    const result = await getReceivedGrants();
    if (result.code === 200 && result.data) {
      receivedGrants.value = result.data;
    }
  } catch (error) {
    console.error("获取收到的分享失败:", error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchReceivedGrants();
});
</script>

<style scoped>
.shared-shell {
  position: relative;
  padding: var(--space-6) 0 var(--space-9);
  overflow: hidden;
}

.shared-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(720px 480px at 50% 0%, rgba(251, 191, 36, 0.1), transparent 60%),
    radial-gradient(680px 420px at 30% 40%, rgba(253, 186, 116, 0.08), transparent 60%);
  pointer-events: none;
}

.shared-page {
  position: relative;
  z-index: 1;
}

.page-header {
  margin-bottom: var(--space-6);
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 0;
  border: none;
  background: transparent;
  color: var(--color-muted);
  font-size: 14px;
  cursor: pointer;
  transition: color 0.2s ease;
  margin-bottom: var(--space-4);
}

.back-btn:hover {
  color: var(--color-text);
}

.back-arrow {
  font-size: 18px;
}

.header-content {
  display: grid;
  gap: var(--space-2);
}

.eyebrow {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: #f59e0b;
  margin: 0;
}

.title {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(28px, 4vw, 36px);
}

.subtitle {
  margin: 0;
  color: var(--color-muted);
  max-width: 400px;
}

/* 加载状态 */
.loading-state {
  display: grid;
  gap: var(--space-3);
  justify-items: center;
  padding: var(--space-9) 0;
  color: var(--color-muted);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(251, 191, 36, 0.2);
  border-top-color: #f59e0b;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 空状态 */
.empty-state {
  display: grid;
  gap: var(--space-3);
  justify-items: center;
  padding: var(--space-9) var(--space-5);
  text-align: center;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 20px;
  border: 1px dashed rgba(251, 191, 36, 0.4);
}

.empty-icon {
  font-size: 56px;
}

.empty-state h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 20px;
}

.empty-state p {
  margin: 0;
  color: var(--color-muted);
}

.ghost-cta {
  padding: 10px 18px;
  border-radius: 999px;
  border: 1px solid rgba(251, 191, 36, 0.3);
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.8);
  font-weight: 600;
  font-size: 14px;
  text-decoration: none;
  transition: all 0.2s ease;
}

.ghost-cta:hover {
  border-color: rgba(251, 191, 36, 0.6);
  background: rgba(251, 191, 36, 0.1);
}

/* 分享卡片网格 */
.shared-grid {
  display: grid;
  gap: var(--space-4);
}

@media (min-width: 600px) {
  .shared-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1000px) {
  .shared-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* 分享卡片 */
.shared-card {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
  border-radius: 18px;
  border: 1px solid rgba(251, 191, 36, 0.3);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: all 0.2s ease;
}

.shared-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 20px 40px rgba(77, 48, 20, 0.12);
  border-color: rgba(251, 191, 36, 0.5);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.voice-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.3), rgba(245, 158, 11, 0.2));
  display: grid;
  place-items: center;
  font-size: 24px;
}

.expired-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(107, 114, 128, 0.15);
  color: #6b7280;
  font-size: 11px;
  font-weight: 600;
}

.card-body {
  display: grid;
  gap: var(--space-2);
}

.voice-name {
  margin: 0;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
}

.from-info {
  margin: 0;
  color: var(--color-muted);
  font-size: 13px;
}

.grant-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.permission-tag {
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(251, 191, 36, 0.2);
  color: #b45309;
  font-size: 12px;
  font-weight: 500;
}

.expire-time {
  font-size: 12px;
  color: var(--color-muted);
}

.card-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid rgba(251, 191, 36, 0.2);
}

.action-btn {
  flex: 1;
  padding: 8px 12px;
  border-radius: 10px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn.primary {
  background: linear-gradient(135deg, #fb923c, #f97316);
  color: white;
}

.action-btn.primary:hover {
  box-shadow: 0 8px 20px rgba(249, 115, 22, 0.3);
}

.action-btn.ghost {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(251, 191, 36, 0.25);
  color: var(--color-text);
}

.action-btn.ghost:hover {
  background: rgba(251, 191, 36, 0.1);
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: grid;
  place-items: center;
  z-index: 100;
  padding: var(--space-4);
}

.modal-content {
  width: 100%;
  max-width: 480px;
  background: white;
  border-radius: 20px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-5);
  border-bottom: 1px solid rgba(239, 227, 215, 0.9);
}

.modal-header h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 20px;
}

.modal-close {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(251, 191, 36, 0.2);
  border-radius: 50%;
  font-size: 20px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.2s ease;
}

.modal-close:hover {
  background: rgba(251, 191, 36, 0.4);
}

.modal-body {
  padding: var(--space-5);
  max-height: 60vh;
  overflow-y: auto;
}

.detail-section {
  margin-bottom: var(--space-5);
}

.detail-section:last-child {
  margin-bottom: 0;
}

.detail-section h4 {
  margin: 0 0 var(--space-3);
  font-size: 14px;
  color: var(--color-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) 0;
  border-bottom: 1px solid rgba(239, 227, 215, 0.6);
}

.detail-row:last-child {
  border-bottom: none;
}

.detail-row .label {
  color: var(--color-muted);
  font-size: 14px;
}

.detail-row .value {
  font-weight: 500;
  font-size: 14px;
}
</style>

