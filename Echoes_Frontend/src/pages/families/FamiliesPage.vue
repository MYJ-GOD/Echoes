<template>
  <main class="families-shell">
    <div class="families-glow"></div>
    <div class="container families-page">
      <header class="page-header">
        <div class="header-content">
          <p class="eyebrow">{{ t("families.eyebrow") }}</p>
          <h1 class="title">{{ t("families.title") }}</h1>
          <p class="subtitle">{{ t("families.subtitle") }}</p>
        </div>
        <button class="primary-cta" @click="showCreateModal = true">
          {{ t("families.create") }}
        </button>
      </header>

      <!-- 鍔犺浇鐘舵€?-->
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <p>{{ t("families.loading") }}</p>
      </div>

      <!-- 绌虹姸鎬?-->
      <div v-else-if="families.length === 0" class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
          </svg>
        </div>
        <h3>{{ t("families.emptyTitle") }}</h3>
        <p>{{ t("families.emptyDesc") }}</p>
        <button class="ghost-cta" @click="showCreateModal = true">
          {{ t("families.createFirst") }}
        </button>
      </div>

      <!-- 瀹跺涵鍗＄墖鍒楄〃 -->
      <div v-else class="families-grid">
        <div
          v-for="family in families"
          :key="family.familyId"
          class="family-card"
          @click="goToDetail(family.familyId)"
        >
          <div class="card-header">
            <div class="family-avatar">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
            </div>
          </div>

          <div class="card-body">
            <h3 class="family-name">{{ family.name }}</h3>
            <div class="family-meta">
              <span class="member-count">
                {{ t("families.memberCount", { count: family.memberCount || 0 }) }}
              </span>
              <span class="create-time">{{ formatTime(family.createTime) }}</span>
            </div>
          </div>

          <div class="card-actions">
            <button
              class="action-btn primary"
              @click.stop="goToDetail(family.familyId)"
            >
              {{ t("families.viewDetail") }}
            </button>
            <button
              v-if="isOwner(family)"
              class="action-btn ghost"
              @click.stop="goToSettings(family.familyId)"
            >
              {{ t("families.settings") }}
            </button>
          </div>
        </div>
      </div>

      <!-- 鍒涘缓瀹跺涵寮圭獥 -->
      <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
        <div class="modal-content">
          <div class="modal-header">
            <h2>{{ t("families.createFamily") }}</h2>
            <button class="modal-close" @click="showCreateModal = false">脳</button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label class="form-label">{{ t("families.familyName") }}</label>
              <input
                type="text"
                v-model="familyName"
                class="form-input"
                :placeholder="t('families.familyNamePlaceholder')"
                maxlength="30"
              />
            </div>
            <div class="form-actions">
              <button class="cancel-btn" @click="showCreateModal = false">
                {{ t("families.cancel") }}
              </button>
              <button
                class="confirm-btn"
                :disabled="!familyName.trim() || creating"
                @click="createFamily"
              >
                <span v-if="creating">{{ t("families.creating") }}</span>
                <span v-else>{{ t("families.confirmCreate") }}</span>
              </button>
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
import { getMyFamilies, createFamily, type Family } from "../../services/modules/family.api";
import { useUserStore } from "../../store/user";

const { t } = useI18n();
const router = useRouter();
const userStore = useUserStore();

const loading = ref(true);
const families = ref<Family[]>([]);
const showCreateModal = ref(false);
const familyName = ref("");
const creating = ref(false);

const isOwner = (family: Family): boolean => {
  return family.ownerUserId === userStore.userId;
};

const formatTime = (time: string): string => {
  const date = new Date(time);
  return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
};

const goToDetail = (familyId: string) => {
  router.push(`/families/${familyId}`);
};

const goToSettings = (familyId: string) => {
  router.push(`/families/${familyId}/settings`);
};

const createFamily = async () => {
  if (!familyName.value.trim()) return;
  
  try {
    creating.value = true;
    const result = await createFamily({ name: familyName.value.trim() });
    if (result.code === 200 && result.data) {
      showCreateModal.value = false;
      familyName.value = "";
      await fetchFamilies();
      router.push(`/families/${result.data.familyId}`);
    } else {
      alert(result.message || t("families.createFailed"));
    }
  } catch (error) {
    console.error("鍒涘缓瀹跺涵澶辫触:", error);
    alert(t("families.createFailed"));
  } finally {
    creating.value = false;
  }
};

const fetchFamilies = async () => {
  try {
    loading.value = true;
    const result = await getMyFamilies();
    if (result.code === 200 && result.data) {
      families.value = result.data;
    }
  } catch (error) {
    console.error("鑾峰彇瀹跺涵鍒楄〃澶辫触:", error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchFamilies();
});
</script>

<style scoped>
.families-shell {
  position: relative;
  padding: var(--space-8) 0 var(--space-9);
  overflow: hidden;
}

.families-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(720px 480px at 20% 10%, rgba(96, 165, 250, 0.08), transparent 60%),
    radial-gradient(680px 420px at 80% 20%, rgba(147, 197, 253, 0.06), transparent 60%);
  pointer-events: none;
}

.families-page {
  position: relative;
  z-index: 1;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
  flex-wrap: wrap;
  gap: var(--space-4);
}

.header-content {
  display: grid;
  gap: var(--space-2);
}

.eyebrow {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: #3b82f6;
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

.primary-cta {
  padding: 10px 18px;
  border-radius: 999px;
  border: none;
  font-weight: 600;
  font-size: 14px;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: white;
  box-shadow: 0 12px 25px rgba(59, 130, 246, 0.28);
  cursor: pointer;
  transition: all 0.2s ease;
}

.primary-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 30px rgba(59, 130, 246, 0.35);
}

/* 鍔犺浇鐘舵€?*/
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
  border: 3px solid rgba(96, 165, 250, 0.2);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 绌虹姸鎬?*/
.empty-state {
  display: grid;
  gap: var(--space-3);
  justify-items: center;
  padding: var(--space-9) var(--space-5);
  text-align: center;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 20px;
  border: 1px dashed rgba(96, 165, 250, 0.4);
}

.empty-icon {
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
}

.empty-icon svg {
  width: 48px;
  height: 48px;
  stroke: #3b82f6;
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
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.8);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ghost-cta:hover {
  border-color: rgba(59, 130, 246, 0.6);
  background: rgba(96, 165, 250, 0.1);
}

/* 瀹跺涵鍗＄墖缃戞牸 */
.families-grid {
  display: grid;
  gap: var(--space-4);
}

@media (min-width: 600px) {
  .families-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1000px) {
  .families-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* 瀹跺涵鍗＄墖 */
.family-card {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
  border-radius: 18px;
  border: 1px solid rgba(96, 165, 250, 0.25);
  background: rgba(255, 255, 255, 0.75);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: all 0.2s ease;
}

.family-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 20px 40px rgba(59, 130, 246, 0.12);
  border-color: rgba(96, 165, 250, 0.5);
  background: rgba(255, 255, 255, 0.85);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.family-avatar {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.3), rgba(59, 130, 246, 0.2));
  display: grid;
  place-items: center;
}

.family-avatar svg {
  width: 30px;
  height: 30px;
  stroke: #1d4ed8;
}

.owner-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: white;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.card-body {
  display: grid;
  gap: var(--space-2);
}

.family-name {
  margin: 0;
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 600;
}

.family-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.member-count {
  font-size: 14px;
  color: var(--color-muted);
}

.create-time {
  font-size: 12px;
  color: var(--color-muted);
}

.card-actions {
  display: flex;
  gap: var(--space-2);
  padding-top: var(--space-3);
  border-top: 1px solid rgba(96, 165, 250, 0.2);
}

.action-btn {
  flex: 1;
  padding: 10px 12px;
  border-radius: 10px;
  border: none;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn.primary {
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: white;
}

.action-btn.primary:hover {
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.3);
}

.action-btn.ghost {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(96, 165, 250, 0.25);
  color: var(--color-text);
}

.action-btn.ghost:hover {
  background: rgba(96, 165, 250, 0.1);
}

/* 寮圭獥 */
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
  max-width: 440px;
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
  background: rgba(96, 165, 250, 0.2);
  border-radius: 50%;
  font-size: 20px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.2s ease;
}

.modal-close:hover {
  background: rgba(96, 165, 250, 0.4);
}

.modal-body {
  padding: var(--space-5);
}

.form-group {
  margin-bottom: var(--space-5);
}

.form-label {
  display: block;
  margin-bottom: var(--space-2);
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
}

.form-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid rgba(229, 139, 58, 0.3);
  border-radius: 12px;
  font-size: 15px;
  outline: none;
  transition: all 0.2s ease;
}

.form-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-input::placeholder {
  color: var(--color-muted);
}

.form-actions {
  display: flex;
  gap: var(--space-3);
}

.cancel-btn,
.confirm-btn {
  flex: 1;
  padding: 12px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cancel-btn {
  border: 1px solid rgba(229, 139, 58, 0.3);
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-text);
}

.cancel-btn:hover {
  background: rgba(253, 186, 116, 0.1);
}

.confirm-btn {
  border: none;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: white;
}

.confirm-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>



