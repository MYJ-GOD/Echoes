<template>
  <main class="family-settings-shell">
    <div class="settings-glow"></div>
    <div class="container settings-page">
      <!-- 杩斿洖鎸夐挳 -->
      <button class="back-btn" @click="goBack">
        <span class="back-arrow" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </span>
        {{ t("families.back") }}
      </button>

      <header class="page-header">
        <h1 class="title">{{ t("families.settingsTitle") }}</h1>
        <p class="subtitle">{{ t("families.settingsSubtitle", { name: familyName }) }}</p>
      </header>

      <!-- 淇敼鍚嶇О -->
      <section class="settings-section card">
        <h3>{{ t("families.updateName") }}</h3>
        <div class="form-group">
          <input
            type="text"
            v-model="editName"
            class="form-input"
            :placeholder="t('families.familyNamePlaceholder')"
            maxlength="30"
          />
          <button
            class="save-btn"
            :disabled="!editName.trim() || editName === familyName || savingName"
            @click="updateName"
          >
            <span v-if="savingName">{{ t("families.saving") }}</span>
            <span v-else>{{ t("families.save") }}</span>
          </button>
        </div>
      </section>

      <!-- 瑙ｆ暎瀹跺涵 (鍗遍櫓鎿嶄綔) -->
      <section class="settings-section danger-section card">
        <div class="danger-content">
          <div class="danger-info">
            <h3>{{ t("families.dissolveTitle") }}</h3>
            <p>{{ t("families.dissolveDesc") }}</p>
          </div>
          <button class="danger-btn" @click="showDissolveModal = true">
            {{ t("families.dissolve") }}
          </button>
        </div>
      </section>
    </div>

    <!-- 瑙ｆ暎纭寮圭獥 -->
    <div v-if="showDissolveModal" class="modal-overlay" @click.self="showDissolveModal = false">
      <div class="modal-content">
        <div class="modal-header warning">
          <div class="warning-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 9v4" />
            <circle cx="12" cy="16" r="1" />
            <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          </svg>
        </div>
          <h2>{{ t("families.dissolveWarningTitle") }}</h2>
        </div>
        <div class="modal-body">
          <p class="warning-text">{{ t("families.dissolveWarningText") }}</p>
          <div class="confirm-input">
            <label>{{ t("families.confirmNameLabel") }}</label>
            <input
              type="text"
              v-model="confirmName"
              :placeholder="familyName"
            />
          </div>
          <div class="modal-actions">
            <button class="cancel-btn" @click="showDissolveModal = false">
              {{ t("families.cancel") }}
            </button>
            <button
              class="dissolve-btn"
              :disabled="confirmName !== familyName || dissolving"
              @click="dissolveFamily"
            >
              <span v-if="dissolving">{{ t("families.dissolving") }}</span>
              <span v-else>{{ t("families.confirmDissolve") }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { getFamilyDetail, updateFamilyName, dissolveFamily as dissolveFamilyApi, type FamilyDetail } from "../../services/modules/family.api";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const familyId = computed(() => route.params.id as string);
const familyName = ref("");
const editName = ref("");
const savingName = ref(false);
const showDissolveModal = ref(false);
const confirmName = ref("");
const dissolving = ref(false);

const goBack = () => {
  router.push(`/families/${familyId.value}`);
};

const updateName = async () => {
  if (!editName.value.trim() || editName.value === familyName.value) return;
  
  try {
    savingName.value = true;
    const result = await updateFamilyName(familyId.value, editName.value.trim());
    if (result.code === 200) {
      familyName.value = editName.value.trim();
      alert(t("families.updateNameSuccess"));
    } else {
      alert(result.message || t("families.updateNameFailed"));
    }
  } catch (e) {
    console.error("鏇存柊瀹跺涵鍚嶇О澶辫触:", e);
    alert(t("families.updateNameFailed"));
  } finally {
    savingName.value = false;
  }
};

const dissolveFamily = async () => {
  if (confirmName.value !== familyName.value) return;
  
  try {
    dissolving.value = true;
    const result = await dissolveFamilyApi(familyId.value);
    if (result.code === 200) {
      alert(t("families.dissolveSuccess"));
      router.push("/families");
    } else {
      alert(result.message || t("families.dissolveFailed"));
    }
  } catch (e) {
    console.error("瑙ｆ暎瀹跺涵澶辫触:", e);
    alert(t("families.dissolveFailed"));
  } finally {
    dissolving.value = false;
  }
};

const fetchFamily = async () => {
  try {
    const result = await getFamilyDetail(familyId.value);
    if (result.code === 200 && result.data) {
      familyName.value = result.data.name;
      editName.value = result.data.name;
    } else {
      alert(t("families.loadError"));
      router.push("/families");
    }
  } catch (e) {
    console.error("鑾峰彇瀹跺涵淇℃伅澶辫触:", e);
    router.push("/families");
  }
};

onMounted(() => {
  fetchFamily();
});
</script>

<script lang="ts">
import { computed } from "vue";
</script>

<style scoped>
.family-settings-shell {
  position: relative;
  padding: var(--space-6) 0 var(--space-9);
  overflow: hidden;
}

.settings-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(720px 480px at 50% 0%, rgba(96, 165, 250, 0.1), transparent 60%);
  pointer-events: none;
}

.settings-page {
  position: relative;
  z-index: 1;
  max-width: 600px;
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
  margin-bottom: var(--space-5);
}

.back-btn:hover {
  color: var(--color-text);
}

.back-arrow {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
}

.back-arrow svg {
  width: 18px;
  height: 18px;
}

.page-header {
  margin-bottom: var(--space-6);
}

.title {
  margin: 0 0 var(--space-2);
  font-family: var(--font-display);
  font-size: 28px;
}

.subtitle {
  margin: 0;
  color: var(--color-muted);
}

.card {
  padding: var(--space-5);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(96, 165, 250, 0.2);
  box-shadow: var(--shadow-card);
  margin-bottom: var(--space-4);
}

.settings-section h3 {
  margin: 0 0 var(--space-4);
  font-family: var(--font-display);
  font-size: 18px;
}

.form-group {
  display: flex;
  gap: var(--space-3);
}

.form-input {
  flex: 1;
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

.save-btn {
  padding: 12px 24px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: white;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.save-btn:hover:not(:disabled) {
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.3);
}

/* 鍗遍櫓鎿嶄綔 */
.danger-section {
  border-color: rgba(248, 113, 113, 0.3);
}

.danger-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.danger-info h3 {
  margin: 0 0 var(--space-1);
  font-family: var(--font-display);
  font-size: 16px;
  color: #b91c1c;
}

.danger-info p {
  margin: 0;
  font-size: 13px;
  color: var(--color-muted);
}

.danger-btn {
  padding: 10px 20px;
  border-radius: 12px;
  border: 1px solid rgba(248, 113, 113, 0.5);
  background: rgba(248, 113, 113, 0.1);
  color: #b91c1c;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.danger-btn:hover {
  background: rgba(248, 113, 113, 0.2);
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
  max-width: 420px;
  background: white;
  border-radius: 20px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5);
  background: rgba(248, 113, 113, 0.1);
}

.modal-header.warning {
  background: rgba(248, 113, 113, 0.08);
}

.warning-icon {
  width: 28px;
  height: 28px;
  color: #b91c1c;
  display: grid;
  place-items: center;
}

.warning-icon svg {
  width: 28px;
  height: 28px;
}

.modal-header h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 20px;
  color: #b91c1c;
}

.modal-body {
  padding: var(--space-5);
}

.warning-text {
  margin: 0 0 var(--space-5);
  color: var(--color-muted);
  line-height: 1.6;
}

.confirm-input {
  margin-bottom: var(--space-5);
}

.confirm-input label {
  display: block;
  margin-bottom: var(--space-2);
  font-size: 14px;
  font-weight: 500;
}

.confirm-input input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 12px;
  font-size: 15px;
  outline: none;
}

.confirm-input input:focus {
  border-color: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
}

.modal-actions {
  display: flex;
  gap: var(--space-3);
}

.cancel-btn,
.dissolve-btn {
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

.dissolve-btn {
  border: none;
  background: #ef4444;
  color: white;
}

.dissolve-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>



