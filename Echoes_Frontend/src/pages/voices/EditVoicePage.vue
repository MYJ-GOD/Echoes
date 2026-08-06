<template>
  <main class="edit-voice-shell">
    <div class="edit-voice-glow"></div>
    <div class="container edit-voice-page">
      <!-- 返回按钮 -->
      <button class="back-btn" @click="goBack">
        <span class="back-arrow">←</span>
        {{ t("voices.back") }}
      </button>

      <header class="page-header">
        <h1 class="title">{{ t("voices.edit") }}</h1>
        <p class="subtitle">{{ t("voices.editVoice") }}</p>
      </header>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <p>{{ t("voices.loading") }}</p>
      </div>

      <!-- 表单 -->
      <section v-else class="form-section card">
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

        <!-- 操作按钮 -->
        <div class="form-actions">
          <button class="delete-btn" @click="deleteVoice">
            {{ t("voices.delete") }}
          </button>
          <button
            class="save-btn"
            :disabled="!canSave || saving"
            @click="saveVoice"
          >
            <span v-if="saving">{{ t("voices.saving") }}</span>
            <span v-else>{{ t("voices.save") }}</span>
          </button>
        </div>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { getVoiceDetail, updateVoiceAsset, deleteVoiceAsset, type VoiceAssetDetail } from "../../services/modules/voice.api";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();

const voiceId = computed(() => route.params.id as string);

const loading = ref(true);
const saving = ref(false);
const voice = ref<VoiceAssetDetail | null>(null);
const voiceName = ref("");
const description = ref("");

const canSave = computed(() => {
  return voiceName.value.trim() && voice.value;
});

const goBack = () => {
  router.push(`/voices/${voiceId.value}`);
};

const saveVoice = async () => {
  if (!canSave.value) return;
  
  try {
    saving.value = true;
    const result = await updateVoiceAsset(voiceId.value, {
      name: voiceName.value.trim(),
      description: description.value.trim() || undefined,
    });
    
    if (result.code === 200) {
      alert(t("voices.saveSuccess"));
      router.push(`/voices/${voiceId.value}`);
    } else {
      alert(result.message || t("voices.saveFailed"));
    }
  } catch (error) {
    console.error("保存失败:", error);
    alert(t("voices.saveFailed"));
  } finally {
    saving.value = false;
  }
};

const deleteVoice = async () => {
  if (!confirm(t("voices.confirmDelete"))) return;
  
  try {
    const result = await deleteVoiceAsset(voiceId.value);
    if (result.code === 200) {
      alert(t("voices.deleteSuccess"));
      router.push("/voices");
    } else {
      alert(result.message || t("voices.deleteFailed"));
    }
  } catch (error) {
    console.error("删除失败:", error);
    alert(t("voices.deleteFailed"));
  }
};

const fetchVoice = async () => {
  try {
    loading.value = true;
    const result = await getVoiceDetail(voiceId.value);
    if (result.code === 200 && result.data) {
      voice.value = result.data;
      voiceName.value = result.data.name || "";
      description.value = result.data.description || "";
    } else {
      alert(t("voices.loadError"));
      router.push("/voices");
    }
  } catch (error) {
    console.error("获取音色信息失败:", error);
    router.push("/voices");
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchVoice();
});
</script>

<style scoped>
.edit-voice-shell {
  position: relative;
  padding: var(--space-6) 0 var(--space-9);
  overflow: hidden;
}

.edit-voice-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(720px 480px at 50% 0%, rgba(253, 186, 116, 0.12), transparent 60%);
  pointer-events: none;
}

.edit-voice-page {
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
  font-size: 18px;
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
  border: 3px solid rgba(253, 186, 116, 0.2);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 表单 */
.card {
  padding: var(--space-6);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(239, 227, 215, 0.9);
  box-shadow: var(--shadow-card);
}

.form-group {
  margin-bottom: var(--space-5);
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-label {
  display: block;
  margin-bottom: var(--space-3);
  font-size: 15px;
  font-weight: 500;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 14px 18px;
  border: 1px solid rgba(229, 139, 58, 0.3);
  border-radius: 14px;
  font-size: 16px;
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

/* 操作按钮 */
.form-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding-top: var(--space-5);
  border-top: 1px solid rgba(239, 227, 215, 0.6);
}

.delete-btn,
.save-btn {
  flex: 1;
  padding: 14px;
  border-radius: 14px;
  border: none;
  font-weight: 600;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.save-btn {
  background: linear-gradient(135deg, #fb923c, #f97316);
  color: white;
  box-shadow: 0 12px 25px rgba(249, 115, 22, 0.28);
}

.save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}

.save-btn:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 16px 30px rgba(249, 115, 22, 0.35);
}

.delete-btn {
  border: 1px solid rgba(248, 113, 113, 0.4);
  background: rgba(248, 113, 113, 0.1);
  color: #b91c1c;
  max-width: 120px;
}

.delete-btn:hover {
  background: rgba(248, 113, 113, 0.2);
}
</style>

