<template>
  <main class="retry-voice-shell">
    <div class="retry-voice-glow"></div>
    <div class="container retry-voice-page">
      <!-- 返回按钮 -->
      <button class="back-btn" @click="goBack">
        <span class="back-arrow" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </span>
        {{ t("voices.back") }}
      </button>

      <header class="page-header">
        <h1 class="title">{{ t("voices.retryTitle") }}</h1>
        <p class="subtitle">{{ t("voices.retrySubtitle") }}</p>
      </header>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>{{ t("voices.loading") }}</p>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="error-state card">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        <p>{{ error }}</p>
        <button class="primary-cta" @click="goBack">
          {{ t("voices.back") }}
        </button>
      </div>

      <!-- 重试表单 -->
      <div v-else class="retry-form">
        <!-- 失败信息 -->
        <section class="failure-info card">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            {{ t("voices.previousFailure") }}
          </h3>
          <div class="failure-details">
            <div class="detail-row">
              <span class="label">{{ t("voices.errorMessage") }}:</span>
              <span class="value error">{{ lastTask?.errorMessage || t("voices.unknownError") }}</span>
            </div>
            <div v-if="lastTask?.retryCount" class="detail-row">
              <span class="label">{{ t("voices.retryCount") }}:</span>
              <span class="value">{{ lastTask.retryCount }}</span>
            </div>
          </div>
        </section>

        <!-- 音色信息 -->
        <section class="voice-info card">
          <h3>{{ t("voices.voiceInfo") }}</h3>
          <div class="info-grid">
            <div class="info-item">
              <span class="label">{{ t("voices.name") }}:</span>
              <span class="value">{{ voiceAsset?.name }}</span>
            </div>
            <div class="info-item">
              <span class="label">{{ t("voices.refAudio") }}:</span>
              <span class="value">{{ voiceAsset?.refId?.substring(0, 8) }}...</span>
            </div>
          </div>
        </section>

        <!-- 可选参数 -->
        <section class="options-section card">
          <h3>{{ t("voices.advancedOptions") }}</h3>
          
          <div class="form-group">
            <label>{{ t("voices.modelVersion") }}</label>
            <select v-model="modelVersion">
              <option :value="1">v1</option>
              <option :value="2">v2</option>
            </select>
          </div>

          <div class="form-group">
            <label>{{ t("voices.customPrompt") }}</label>
            <textarea 
              v-model="prompt" 
              :placeholder="t('voices.promptPlaceholder')"
              rows="3"
            ></textarea>
            <p class="hint">{{ t("voices.promptHint") }}</p>
          </div>
        </section>

        <!-- 提交按钮 -->
        <div class="action-buttons">
          <button 
            class="primary-cta" 
            :disabled="submitting"
            @click="handleRetry"
          >
            <span v-if="submitting" class="spinner-small"></span>
            {{ submitting ? t("voices.submitting") : t("voices.startRetry") }}
          </button>
          <button class="ghost-cta" @click="goBack">
            {{ t("voices.cancel") }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { getVoiceDetail, retryTrainingTask, type VoiceAssetDetail, type TrainingTask } from "../../services/modules/voice.api";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const voiceId = ref(route.params.id as string);
const loading = ref(true);
const error = ref("");
const submitting = ref(false);

const voiceAsset = ref<VoiceAssetDetail | null>(null);
const lastTask = ref<TrainingTask | null>(null);

const modelVersion = ref(1);
const prompt = ref("");

onMounted(async () => {
  await fetchVoiceDetails();
});

const fetchVoiceDetails = async () => {
  try {
    loading.value = true;
    const result = await getVoiceDetail(voiceId.value);
    
    if (result.code === 200 && result.data) {
      voiceAsset.value = result.data;
      
      // 获取最后一个训练任务
      if (result.data.tasks && result.data.tasks.length > 0) {
        // 找到失败的任务
        const failedTask = result.data.tasks.find(t => t.status === "FAILED");
        if (failedTask) {
          lastTask.value = failedTask;
        } else {
          // 如果没有失败的任务，使用最后一个任务
          lastTask.value = result.data.tasks[result.data.tasks.length - 1];
        }
      }
      
      // 如果不是失败状态，不允许重试
      if (result.data.status !== "FAILED") {
        error.value = t("voices.canOnlyRetryFailed");
        return;
      }
    } else {
      error.value = result.message || t("voices.loadError");
    }
  } catch (e: any) {
    error.value = e.message || t("voices.loadError");
  } finally {
    loading.value = false;
  }
};

const goBack = () => {
  router.push(`/voices/${voiceId.value}`);
};

const handleRetry = async () => {
  if (!lastTask.value) {
    error.value = t("voices.noTaskToRetry");
    return;
  }

  try {
    submitting.value = true;
    
    const result = await retryTrainingTask(lastTask.value.taskId, {
      modelVersion: modelVersion.value,
      prompt: prompt.value || undefined
    });

    if (result.code === 200 && result.data) {
      // 跳转到详情页查看进度
      router.push(`/voices/${voiceId.value}`);
    } else {
      error.value = result.message || t("voices.retryFailed");
    }
  } catch (e: any) {
    error.value = e.message || t("voices.retryFailed");
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
.retry-voice-shell {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
}

.retry-voice-glow {
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: radial-gradient(circle at 30% 20%, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
              radial-gradient(circle at 70% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 50%);
  pointer-events: none;
}

.retry-voice-page {
  position: relative;
  padding: 2rem;
  max-width: 640px;
  margin: 0 auto;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 0.9rem;
  cursor: pointer;
  padding: 0.5rem;
  margin-bottom: 1rem;
  transition: color 0.2s;
}

.back-btn:hover {
  color: var(--text-primary);
}

.back-arrow svg {
  width: 18px;
  height: 18px;
}

.page-header {
  text-align: center;
  margin-bottom: 2rem;
}

.title {
  font-size: 1.75rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
  margin-right: 0.5rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-state svg {
  width: 48px;
  height: 48px;
  color: var(--error-color);
  margin-bottom: 1rem;
}

.retry-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.card {
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 1.5rem;
}

.card h3 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 1rem;
}

.card h3 svg {
  width: 20px;
  height: 20px;
}

.failure-info h3 svg {
  color: var(--error-color);
}

.failure-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.detail-row {
  display: flex;
  gap: 0.5rem;
}

.detail-row .label {
  color: var(--text-secondary);
  font-size: 0.9rem;
  min-width: 100px;
}

.detail-row .value {
  font-size: 0.9rem;
}

.detail-row .value.error {
  color: var(--error-color);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.info-item .label {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.info-item .value {
  font-size: 0.95rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  font-size: 0.9rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
}

.form-group select,
.form-group textarea {
  width: 100%;
  padding: 0.75rem;
  background: var(--input-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 0.95rem;
}

.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: var(--primary-color);
}

.form-group .hint {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
}

.action-buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 1rem;
}

.primary-cta,
.ghost-cta {
  padding: 0.75rem 2rem;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.primary-cta {
  background: var(--primary-color);
  color: white;
  border: none;
}

.primary-cta:hover:not(:disabled) {
  background: var(--primary-hover);
}

.primary-cta:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ghost-cta {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
}

.ghost-cta:hover {
  border-color: var(--text-secondary);
  color: var(--text-primary);
}
</style>

