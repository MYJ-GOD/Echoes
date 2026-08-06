<template>
  <main class="create-voice-shell">
    <div class="create-voice-glow"></div>
    <div class="container create-voice-page">
      <!-- 杩斿洖鎸夐挳 -->
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
        <h1 class="title">{{ t("voices.createTitle") }}</h1>
        <p class="subtitle">{{ t("voices.createSubtitle") }}</p>
      </header>

      <!-- 姝ラ鎸囩ず鍣?-->
      <div class="steps">
        <div
          v-for="(step, index) in steps"
          :key="step.id"
          class="step"
          :class="{ active: currentStep === index, completed: currentStep > index }"
        >
          <div class="step-number">
            <svg
              v-if="currentStep > index"
              class="step-check"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
            <span v-else>{{ index + 1 }}</span>
          </div>
          <span class="step-label">{{ step.label }}</span>
        </div>
      </div>

      <!-- 姝ラ 1: 涓婁紶鍙傝€冮煶棰?-->
      <div v-if="currentStep === 0" class="step-content">
        <section class="upload-section card">
          <h3>{{ t("voices.uploadAudio") }}</h3>
          
          <div
            class="upload-area"
            :class="{ 'drag-over': isDragOver, 'has-file': audioFile }"
            @dragover.prevent="isDragOver = true"
            @dragleave.prevent="isDragOver = false"
            @drop.prevent="handleDrop"
            @click="triggerFileInput"
          >
            <input
              ref="fileInput"
              type="file"
              accept="audio/*"
              hidden
              @change="handleFileSelect"
            />
            
            <template v-if="!audioFile">
              <div class="upload-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M9 18V5l12-2v13" />
                  <circle cx="6" cy="18" r="3" />
                  <circle cx="18" cy="16" r="3" />
                </svg>
              </div>
              <p class="upload-hint">{{ t("voices.uploadHint") }}</p>
              <p class="upload-tip">{{ t("voices.uploadTip") }}</p>
            </template>
            
            <template v-else>
              <div class="file-preview">
                <div class="file-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z" />
                    <path d="M14 2v5h5" />
                    <path d="M9 15h6" />
                  </svg>
                </div>
                <div class="file-info">
                  <span class="file-name">{{ audioFile.name }}</span>
                  <span class="file-size">{{ formatFileSize(audioFile.size) }}</span>
                </div>
                <button class="remove-btn" @click.stop="removeAudio">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                </button>
              </div>
              <audio v-if="audioUrl" :src="audioUrl" controls class="audio-player"></audio>
            </template>
          </div>
        </section>
      </div>

      <!-- 姝ラ 2: 璁剧疆闊宠壊淇℃伅 -->
      <div v-if="currentStep === 1" class="step-content">
        <section class="form-section card">
          <h3>{{ t("voices.voiceInfo") }}</h3>
          
          <div class="form-group">
            <label class="form-label">{{ t("voices.voiceName") }}</label>
            <input
              type="text"
              v-model="voiceName"
              class="form-input"
              :placeholder="t('voices.voiceNamePlaceholder')"
              maxlength="50"
            />
          </div>

          <div class="form-group">
            <label class="form-label">{{ t("voices.description") }}</label>
            <textarea
              v-model="description"
              class="form-textarea"
              :placeholder="t('voices.descriptionPlaceholder')"
              rows="3"
              maxlength="200"
            ></textarea>
          </div>

          <div class="form-group">
            <div class="form-label-row">
              <label class="form-label">
                {{ t("voices.prompt") }}
                <span class="asr-badge" :class="{ loading: promptLoading, error: promptError }">
                  <template v-if="promptLoading">
                    <svg class="spinner" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10" stroke-dasharray="60" stroke-dashoffset="20" />
                    </svg>
                    {{ t("voices.asrRecognizing") }}
                  </template>
                  <template v-else-if="promptError">
                    {{ t("voices.asrFailed") }}
                  </template>
                  <template v-else>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    {{ t("voices.asrCompleted") }}
                  </template>
                </span>
              </label>
              <button
                type="button"
                class="retry-asr-btn"
                :disabled="promptLoading || !audioFile"
                @click="recognizeAudio"
              >
                {{ promptLoading ? t("voices.asrRecognizing") : t("voices.retryAsr") }}
              </button>
            </div>
            <textarea
              v-model="prompt"
              class="form-textarea"
              :placeholder="promptLoading ? t('voices.asrRecognizing') : t('voices.promptPlaceholder')"
              rows="4"
              :disabled="promptLoading"
            ></textarea>
            <p v-if="promptError" class="form-hint error">{{ promptError }}</p>
            <p v-else class="form-hint">{{ t("voices.promptHint") }}</p>
          </div>

          <div class="form-group">
            <label class="form-label-checkbox">
              <input
                type="checkbox"
                v-model="setAsDefault"
                class="checkbox-input"
              />
              <span class="checkbox-label">
                {{ t("voices.setAsDefault") }}
                <span class="checkbox-hint">{{ t("voices.setAsDefaultHint") }}</span>
              </span>
            </label>
          </div>
        </section>
      </div>

      <!-- 姝ラ 3: 纭鎻愪氦 -->
      <div v-if="currentStep === 2" class="step-content">
        <section class="confirm-section card">
          <h3>{{ t("voices.confirmInfo") }}</h3>
          
          <div class="confirm-list">
            <div class="confirm-item">
              <span class="confirm-label">{{ t("voices.voiceName") }}</span>
              <span class="confirm-value">{{ voiceName }}</span>
            </div>
            <div class="confirm-item">
              <span class="confirm-label">{{ t("voices.description") }}</span>
              <span class="confirm-value">{{ description || "-" }}</span>
            </div>
            <div class="confirm-item">
              <span class="confirm-label">{{ t("voices.prompt") }}</span>
              <span class="confirm-value">{{ prompt || "-" }}</span>
            </div>
            <div class="confirm-item">
              <span class="confirm-label">{{ t("voices.audioFile") }}</span>
              <span class="confirm-value">{{ audioFile?.name || "-" }}</span>
            </div>
          </div>

          <div class="notice-box">
            <span class="notice-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9" />
                <path d="M12 8v4" />
                <circle cx="12" cy="16" r="1" />
              </svg>
            </span>
            <p>{{ t("voices.createNotice") }}</p>
          </div>
        </section>
      </div>

      <!-- 姝ラ瀵艰埅 -->
      <div class="step-actions">
        <button
          v-if="currentStep > 0"
          class="nav-btn ghost"
          @click="prevStep"
        >
          {{ t("voices.prev") }}
        </button>
        <div class="spacer"></div>
        <button
          v-if="currentStep < steps.length - 1"
          class="nav-btn primary"
          :disabled="!canProceed"
          @click="nextStep"
        >
          {{ t("voices.next") }}
        </button>
        <button
          v-if="currentStep === steps.length - 1"
          class="nav-btn primary"
          :disabled="!canSubmit || submitting"
          @click="submit"
        >
          <span v-if="submitting">{{ t("voices.creating") }}</span>
          <span v-else>{{ t("voices.startCreate") }}</span>
        </button>
      </div>
    </div>

    <!-- 成功对话框 -->
    <ConfirmDialog
      :visible="showSuccessDialog"
      :title="t('voices.success')"
      :message="t('voices.createSuccess')"
      :confirmText="t('voices.viewDetail')"
      :cancelText="t('voices.backToList')"
      @confirm="goToVoiceDetail"
      @cancel="goToVoiceList"
    />

    <!-- 错误对话框 -->
    <ConfirmDialog
      :visible="showErrorDialog"
      :title="t('voices.error')"
      :message="errorMessage"
      :confirmText="t('voices.confirm')"
      :danger="true"
      @confirm="showErrorDialog = false"
    />
  </main>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { createVoiceAsset } from "../../services/modules/voice.api";
import { getToken } from "../../utils/token";
import ConfirmDialog from "../../components/ConfirmDialog.vue";

const { t } = useI18n();
const router = useRouter();

const currentStep = ref(0);
const steps = [
  { id: "upload", label: t("voices.stepUpload") },
  { id: "info", label: t("voices.stepInfo") },
  { id: "confirm", label: t("voices.stepConfirm") },
];

const fileInput = ref<HTMLInputElement | null>(null);
const isDragOver = ref(false);
const audioFile = ref<File | null>(null);
const audioUrl = ref("");

const voiceName = ref("");
const description = ref("");
const prompt = ref("");
const setAsDefault = ref(false); // 设为默认音色
const promptLoading = ref(false); // ASR 识别中
const promptError = ref(""); // ASR 识别错误
const recognizedRefId = ref(""); // ASR 识别成功后返回的 refId
const submitting = ref(false);

// 对话框状态
const showSuccessDialog = ref(false);
const showErrorDialog = ref(false);
const errorMessage = ref("");
const successVoiceAssetId = ref("");

const canProceed = computed(() => {
  if (currentStep.value === 0) return !!audioFile.value;
  if (currentStep.value === 1) return !!voiceName.value.trim();
  return true;
});

const canSubmit = computed(() => {
  return voiceName.value.trim() && audioFile.value;
});

const goBack = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
  } else {
    router.push("/voices");
  }
};

const triggerFileInput = () => {
  fileInput.value?.click();
};

const handleFileSelect = (event: Event) => {
  const input = event.target as HTMLInputElement;
  if (input.files && input.files[0]) {
    setAudioFile(input.files[0]);
  }
};

const handleDrop = (event: DragEvent) => {
  isDragOver.value = false;
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    const file = event.dataTransfer.files[0];
    if (file.type.startsWith("audio/")) {
      setAudioFile(file);
    } else {
      alert(t("voices.invalidFileType"));
    }
  }
};

const setAudioFile = (file: File) => {
  audioFile.value = file;
  audioUrl.value = URL.createObjectURL(file);
  // 上传后自动调用 ASR 识别
  recognizeAudio();
};

// 调用 ASR 识别音频文本
const recognizeAudio = async () => {
  if (!audioFile.value) return;
  
  const token = getToken();
  console.log("ASR Token:", token ? "exists" : "null");
  
  promptLoading.value = true;
  promptError.value = "";
  
  try {
    // 直接上传到 voice-service，会自动 ASR 识别
    const formData = new FormData();
    formData.append("audio_file", audioFile.value);
    
    const base = import.meta.env.VITE_API_BASE || "/api";
    
    const response = await fetch(`${base}/conversation/voice-ref/upload`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${getToken()}`,
      },
      body: formData,
    });
    
    const result = await response.json();
    console.log("ASR response:", result);
    
    if (result.code === 1 && result.data?.refText) {
      prompt.value = result.data.refText;
      recognizedRefId.value = result.data.refId || ""; // 保存 refId
    } else {
      // ASR 识别失败，使用空文本让用户手动输入
      prompt.value = "";
      promptError.value = result.msg || result.message || "ASR识别失败，请手动输入文本";
    }
  } catch (error) {
    console.error("ASR 识别失败:", error);
    prompt.value = "";
    promptError.value = "ASR识别失败，请手动输入文本";
  } finally {
    promptLoading.value = false;
  }
};

const removeAudio = () => {
  audioFile.value = null;
  audioUrl.value = "";
  if (fileInput.value) {
    fileInput.value.value = "";
  }
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
};

const nextStep = () => {
  if (currentStep.value < steps.length - 1) {
    currentStep.value++;
  }
};

const prevStep = () => {
  if (currentStep.value > 0) {
    currentStep.value--;
  }
};

const submit = async () => {
  if (!audioFile.value || !voiceName.value.trim()) return;
  
  try {
    submitting.value = true;
    const base = import.meta.env.VITE_API_BASE || "/api";
    
    // 1. 如果已有 ASR 识别的 refId，复用它；否则重新上传
    let refId = recognizedRefId.value;
    console.log("Current refId:", refId);
    
    if (!refId) {
      console.log("Uploading new audio file...");
      const formData = new FormData();
      formData.append("audio_file", audioFile.value);
      
      const uploadResponse = await fetch(`${base}/conversation/voice-ref/upload`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
        },
        body: formData,
      });
      
      console.log("Upload response status:", uploadResponse.status);
      const uploadResult = await uploadResponse.json();
      console.log("Upload result:", uploadResult);
      
      if (uploadResult.code !== 1 || !uploadResult.data?.refId) {
        throw new Error(uploadResult.msg || uploadResult.message || "上传音频失败");
      }
      refId = uploadResult.data.refId;
      console.log("New refId:", refId);
    }
    
    // 2. 创建音色资产 (RESTful 规范: POST /voice/assets)
    console.log("Creating voice asset with refId:", refId);
    const token = getToken();
    console.log("Token exists:", !!token);
    
    const createResponse = await fetch(`${base}/voice/assets`, {
      method: "POST",
      headers: {
        Authorization: token ? `Bearer ${token}` : "",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        refId: refId,
        name: voiceName.value.trim(),
        role: "other",
        description: description.value.trim() || undefined,
        prompt: prompt.value.trim() || undefined,
        setAsDefault: setAsDefault.value || undefined,
      }),
    });
    
    console.log("Create response status:", createResponse.status);
    const result = await createResponse.json();
    console.log("Create voice asset result:", result);
    
    if (result.code === 200 && result.data) {
      successVoiceAssetId.value = result.data.voiceAssetId;
      showSuccessDialog.value = true;
    } else {
      errorMessage.value = result.message || t("voices.createFailed");
      showErrorDialog.value = true;
    }
  } catch (error) {
    console.error("创建音色失败:", error);
    errorMessage.value = t("voices.createFailed");
    showErrorDialog.value = true;
  } finally {
    submitting.value = false;
  }
};

const goToVoiceDetail = () => {
  showSuccessDialog.value = false;
  router.push(`/voices/${successVoiceAssetId.value}`);
};

const goToVoiceList = () => {
  showSuccessDialog.value = false;
  router.push("/voices");
};
</script>

<style scoped>
.create-voice-shell {
  position: relative;
  padding: var(--space-6) 0 var(--space-9);
  overflow: hidden;
}

.create-voice-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(720px 480px at 50% 0%, rgba(253, 186, 116, 0.12), transparent 60%);
  pointer-events: none;
}

.create-voice-page {
  position: relative;
  z-index: 1;
  max-width: 640px;
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
  margin-bottom: var(--space-7);
  text-align: center;
}

.title {
  margin: 0 0 var(--space-2);
  font-family: var(--font-display);
  font-size: clamp(26px, 4vw, 32px);
  color: var(--color-text);
}

.subtitle {
  margin: 0;
  color: var(--color-muted-soft);
  font-size: 15px;
}

/* 姝ラ鎸囩ず鍣?*/
.steps {
  display: flex;
  justify-content: center;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.step {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  opacity: 0.5;
  transition: opacity 0.2s ease;
}

.step.active,
.step.completed {
  opacity: 1;
}

.step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(253, 186, 116, 0.2);
  display: grid;
  place-items: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-accent);
}

.step-check {
  width: 16px;
  height: 16px;
}

.step.completed .step-number {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(253, 186, 116, 0.2);
  display: grid;
  place-items: center;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-accent);
}

.step-check {
  width: 16px;
  height: 16px;
}

.step-label {
  font-size: 14px;
  color: var(--color-muted);
}

.step.active .step-label {
  color: var(--color-text);
  font-weight: 500;
}

/* 鍗＄墖鏍峰紡 */
.card {
  padding: var(--space-5);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(239, 227, 215, 0.9);
  box-shadow: var(--shadow-card);
  margin-bottom: var(--space-5);
}

.card h3 {
  margin: 0 0 var(--space-4);
  font-family: var(--font-display);
  font-size: 18px;
}

/* 涓婁紶鍖哄煙 */
.upload-area {
  border: 2px dashed rgba(229, 139, 58, 0.3);
  border-radius: 16px;
  padding: var(--space-8) var(--space-5);
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.upload-area:hover,
.upload-area.drag-over {
  border-color: var(--color-accent);
  background: rgba(253, 186, 116, 0.05);
}

.upload-area.has-file {
  padding: var(--space-5);
}

.upload-icon {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  margin: 0 auto var(--space-3);
  color: #c2410c;
}

.upload-icon svg {
  width: 44px;
  height: 44px;
}

.upload-hint {
  margin: 0 0 var(--space-2);
  font-weight: 500;
  font-size: 16px;
}

.upload-tip {
  margin: 0;
  font-size: 13px;
  color: var(--color-muted);
}

/* 鏂囦欢棰勮 */
.file-preview {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.file-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(253, 186, 116, 0.3), rgba(251, 146, 60, 0.2));
  display: grid;
  place-items: center;
  color: #9a3412;
}

.file-icon svg {
  width: 22px;
  height: 22px;
}

.file-info {
  flex: 1;
  display: grid;
  gap: 2px;
}

.file-name {
  font-weight: 500;
  font-size: 14px;
}

.file-size {
  font-size: 12px;
  color: var(--color-muted);
}

.remove-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(248, 113, 113, 0.2);
  border-radius: 50%;
  color: #b91c1c;
  cursor: pointer;
  display: grid;
  place-items: center;
  padding: 0;
}

.remove-btn svg {
  width: 16px;
  height: 16px;
}

.audio-player {
  width: 100%;
  border-radius: 12px;
}

/* 琛ㄥ崟 */
.form-group {
  margin-bottom: var(--space-5);
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-label-checkbox {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  cursor: pointer;
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  transition: background-color 0.2s ease;
}

.form-label-checkbox:hover {
  background: rgba(253, 186, 116, 0.08);
}

.checkbox-input {
  width: 18px;
  height: 18px;
  margin: 0;
  cursor: pointer;
  accent-color: #f97316;
}

.checkbox-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
}

.checkbox-hint {
  font-size: 12px;
  color: var(--color-muted);
  font-weight: normal;
}

.form-label {
  display: block;
  margin-bottom: var(--space-2);
  font-size: 14px;
  font-weight: 500;
}

.form-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.form-label-row .form-label {
  margin-bottom: 0;
}

.retry-asr-btn {
  border: 1px solid rgba(229, 139, 58, 0.35);
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-text);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.retry-asr-btn:hover:not(:disabled) {
  border-color: rgba(229, 139, 58, 0.6);
  background: rgba(253, 186, 116, 0.08);
}

.retry-asr-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid rgba(229, 139, 58, 0.3);
  border-radius: 12px;
  font-size: 15px;
  outline: none;
  transition: all 0.2s ease;
  font-family: inherit;
}

.form-input:focus,
.form-textarea:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1);
}

.form-textarea {
  resize: vertical;
  min-height: 100px;
}

.form-hint {
  margin: var(--space-2) 0 0;
  font-size: 12px;
  color: var(--color-muted);
}

.form-hint.error {
  color: #dc2626;
}

.asr-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: normal;
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.asr-badge svg {
  width: 12px;
  height: 12px;
}

.asr-badge.loading {
  background: rgba(251, 191, 36, 0.1);
  color: #d97706;
}

.asr-badge.loading .spinner {
  animation: spin 1s linear infinite;
}

.asr-badge.error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 纭淇℃伅 */
.confirm-list {
  display: grid;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.confirm-item {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: var(--space-3) 0;
  border-bottom: 1px solid rgba(239, 227, 215, 0.6);
}

.confirm-item:last-child {
  border-bottom: none;
}

.confirm-label {
  color: var(--color-muted);
  font-size: 14px;
}

.confirm-value {
  flex: 1;
  text-align: right;
  font-size: 14px;
  margin-left: var(--space-4);
}

.notice-box {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4);
  background: rgba(251, 191, 36, 0.1);
  border-radius: 12px;
}

.notice-icon {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  color: #92400e;
}

.notice-icon svg {
  width: 20px;
  height: 20px;
}

.notice-box p {
  margin: 0;
  font-size: 13px;
  color: #92400e;
  line-height: 1.5;
}

/* 姝ラ瀵艰埅 */
.step-actions {
  display: flex;
  gap: var(--space-3);
  padding-top: var(--space-4);
}

.spacer {
  flex: 1;
}

.nav-btn {
  padding: 12px 24px;
  border-radius: 12px;
  border: none;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-btn.primary {
  background: linear-gradient(135deg, #fb923c, #f97316);
  color: white;
  box-shadow: 0 12px 25px rgba(249, 115, 22, 0.28);
}

.nav-btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.nav-btn.primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 16px 30px rgba(249, 115, 22, 0.35);
}

.nav-btn.ghost {
  border: 1px solid rgba(229, 139, 58, 0.3);
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-text);
}

.nav-btn.ghost:hover {
  background: rgba(253, 186, 116, 0.1);
}
</style>



