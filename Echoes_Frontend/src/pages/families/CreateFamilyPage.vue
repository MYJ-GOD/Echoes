<template>
  <main class="create-family-shell">
    <div class="create-family-glow"></div>
    <div class="container create-family-page">
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
        <h1 class="title">{{ t("families.createFamily") }}</h1>
        <p class="subtitle">{{ t("families.createFamily") }}</p>
      </header>

      <section class="form-section card">
        <div class="form-group">
          <label class="form-label">{{ t("families.familyName") }}</label>
          <input
            type="text"
            v-model="familyName"
            class="form-input"
            :placeholder="t('families.familyNamePlaceholder')"
            maxlength="30"
            @keyup.enter="createFamily"
          />
        </div>

        <div class="tips-section">
          <div class="tip-item">
            <span class="tip-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            </span>
            <span class="tip-text">Create a family first, then invite your members.</span>
          </div>
          <div class="tip-item">
            <span class="tip-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            </span>
            <span class="tip-text">瀹跺涵鎴愬憳鍙互浜掔浉鍒嗕韩闊宠壊</span>
          </div>
        </div>

        <button
          class="submit-btn"
          :disabled="!familyName.trim() || submitting"
          @click="createFamily"
        >
          <span v-if="submitting">{{ t("families.creating") }}</span>
          <span v-else>{{ t("families.confirmCreate") }}</span>
        </button>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { createFamily, type Family } from "../../services/modules/family.api";

const { t } = useI18n();
const router = useRouter();

const familyName = ref("");
const submitting = ref(false);

const goBack = () => {
  router.push("/families");
};

const createFamily = async () => {
  if (!familyName.value.trim()) return;
  
  try {
    submitting.value = true;
    const result = await createFamily({ name: familyName.value.trim() });
    if (result.code === 200 && result.data) {
      alert(t("families.createSuccess") || "鍒涘缓鎴愬姛");
      router.push(`/families/${result.data.familyId}`);
    } else {
      alert(result.message || t("families.createFailed"));
    }
  } catch (error) {
    console.error("鍒涘缓瀹跺涵澶辫触:", error);
    alert(t("families.createFailed"));
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.create-family-shell {
  position: relative;
  padding: var(--space-6) 0 var(--space-9);
  overflow: hidden;
}

.create-family-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(720px 480px at 50% 0%, rgba(96, 165, 250, 0.1), transparent 60%);
  pointer-events: none;
}

.create-family-page {
  position: relative;
  z-index: 1;
  max-width: 500px;
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
  text-align: center;
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
  padding: var(--space-6);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(96, 165, 250, 0.2);
  box-shadow: var(--shadow-card);
}

.form-group {
  margin-bottom: var(--space-5);
}

.form-label {
  display: block;
  margin-bottom: var(--space-3);
  font-size: 15px;
  font-weight: 500;
}

.form-input {
  width: 100%;
  padding: 14px 18px;
  border: 1px solid rgba(229, 139, 58, 0.3);
  border-radius: 14px;
  font-size: 16px;
  outline: none;
  transition: all 0.2s ease;
}

.form-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.tips-section {
  display: grid;
  gap: var(--space-3);
  margin-bottom: var(--space-6);
  padding: var(--space-4);
  background: rgba(96, 165, 250, 0.08);
  border-radius: 14px;
}

.tip-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.tip-icon {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  color: #1e40af;
}

.tip-icon svg {
  width: 20px;
  height: 20px;
}

.tip-text {
  font-size: 14px;
  color: #1e40af;
}

.submit-btn {
  width: 100%;
  padding: 14px;
  border-radius: 14px;
  border: none;
  background: linear-gradient(135deg, #60a5fa, #3b82f6);
  color: white;
  font-weight: 600;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.submit-btn:hover:not(:disabled) {
  box-shadow: 0 12px 30px rgba(59, 130, 246, 0.35);
  transform: translateY(-2px);
}
</style>



