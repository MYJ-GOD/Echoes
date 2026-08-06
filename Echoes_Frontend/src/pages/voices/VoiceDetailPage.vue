<template>
  <main class="voice-detail-shell">
    <div class="voice-detail-glow"></div>
    <div class="container voice-detail-page">
      <!-- Back Button -->
      <button class="back-btn" @click="goBack">
        <span class="back-arrow" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </span>
        {{ t("voices.back") }}
      </button>

      <!-- Loading -->
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <p>{{ t("voices.loading") }}</p>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="error-state">
        <div class="error-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="9" />
            <line x1="9" y1="9" x2="15" y2="15" />
            <line x1="15" y1="9" x2="9" y2="15" />
          </svg>
        </div>
        <h3>{{ t("voices.loadError") }}</h3>
        <p>{{ error }}</p>
        <button class="ghost-cta" @click="goBack">{{ t("voices.backHome") }}</button>
      </div>

      <template v-else-if="voice">
        <!-- Header -->
        <header class="detail-header">
          <div class="header-left">
            <div class="voice-avatar" :class="getStatusClass(voice.status)">
              <svg v-if="voice.status === 'READY'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9" />
                <path d="m8.5 12.5 2.3 2.3 4.7-4.8" />
              </svg>
              <svg v-else-if="voice.status === 'PROCESSING'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12a9 9 0 1 1-3.2-6.9" />
                <polyline points="21 3 21 9 15 9" />
              </svg>
              <svg v-else-if="voice.status === 'FAILED'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9" />
                <line x1="9" y1="9" x2="15" y2="15" />
                <line x1="15" y1="9" x2="9" y2="15" />
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9" />
                <polyline points="12 7 12 12 15.5 14" />
              </svg>
            </div>
            <div class="header-info">
              <h1 class="voice-title">{{ voice.name }}</h1>
              <p v-if="voice.description" class="voice-desc">{{ voice.description }}</p>
              <div class="voice-meta">
                <span class="status-badge" :class="getStatusClass(voice.status)">
                  {{ getStatusText(voice.status) }}
                </span>
                <span v-if="voice.isDefault" class="default-badge">
                  {{ t("voices.default") }}
                </span>
                <span class="create-time">{{ formatTime(voice.createTime) }}</span>
              </div>
            </div>
          </div>
          <div class="header-actions">
            <button
              v-if="voice.status === 'READY'"
              class="primary-cta"
              @click="startChat"
            >
              {{ t("voices.useVoice") }}
            </button>
            <button class="ghost-cta" @click="showShareModal = true">
              {{ t("voices.share") }}
            </button>
            <button class="ghost-cta" @click="goToEdit">
              {{ t("voices.edit") }}
            </button>
          </div>
        </header>

        <!-- Training Progress -->
        <section v-if="voice.status === 'PROCESSING'" class="progress-section card">
          <div class="progress-header">
            <h3>{{ t("voices.trainingTitle") }}</h3>
            <span class="progress-percent">{{ Math.round((voice.progress || 0) * 100) }}%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${(voice.progress || 0) * 100}%` }"></div>
          </div>
          <p class="progress-tip">{{ t("voices.trainingTip") }}</p>
          <button class="danger-cta" @click="cancelTraining">
            {{ t("voices.cancelTraining") }}
          </button>
        </section>

        <!-- Training Result -->
        <section v-if="voice.status === 'READY'" class="result-section card">
          <h3>{{ t("voices.trainingResult") }}</h3>
          <div class="result-metrics">
            <div class="metric">
              <span class="metric-label">{{ t("voices.similarity") }}</span>
              <span class="metric-value">{{ (voice.similarityScore || 0).toFixed(2) }}</span>
            </div>
          </div>
          <!-- 播放测试音频 -->
          <div class="audio-preview">
            <button
              v-if="!audioUrl && !isLoadingAudio"
              class="ghost-cta"
              @click="loadTestAudio"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="16" height="16">
                <polygon points="5 3 19 12 5 21 5 3" />
              </svg>
              {{ t("voices.playTestAudio") }}
            </button>
            <div v-else-if="isLoadingAudio" class="audio-loading">
              <div class="mini-spinner"></div>
              <span>{{ t("voices.loadingAudio") }}</span>
            </div>
            <div v-else-if="audioUrl" class="audio-player">
              <audio :src="audioUrl" controls></audio>
            </div>
          </div>
        </section>

        <!-- Failed State -->
        <section v-if="voice.status === 'FAILED'" class="failed-section card">
          <div class="failed-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 9v4" />
              <circle cx="12" cy="16" r="1" />
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            </svg>
          </div>
          <h3>{{ t("voices.trainingFailed") }}</h3>
          <p>{{ voice.errorMessage || t("voices.trainingFailedDesc") }}</p>
          <div class="failed-actions">
            <button class="primary-cta" @click="retryTraining">
              {{ t("voices.retry") }}
            </button>
            <button class="ghost-cta" @click="deleteVoice">
              {{ t("voices.delete") }}
            </button>
          </div>
        </section>

        <!-- History -->
        <section class="history-section card">
          <h3>{{ t("voices.historyTitle") }}</h3>
          <div v-if="tasksLoading" class="mini-loading">
            <div class="mini-spinner"></div>
          </div>
          <div v-else-if="tasks.length === 0" class="empty-history">
            <p>{{ t("voices.noHistory") }}</p>
          </div>
          <div v-else class="history-list">
            <div
              v-for="task in tasks"
              :key="task.taskId"
              class="history-item"
            >
              <div class="history-icon">
                <svg v-if="task.status === 'COMPLETED'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <svg v-else-if="task.status === 'FAILED'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
                <svg v-else-if="task.status === 'CANCELLED'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="9" />
                  <line x1="7" y1="17" x2="17" y2="7" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 12a9 9 0 1 1-3.2-6.9" />
                  <polyline points="21 3 21 9 15 9" />
                </svg>
              </div>
              <div class="history-info">
                <span class="history-status" :class="`status-${task.status.toLowerCase()}`">
                  {{ getTaskStatusText(task.status) }}
                </span>
                <span class="history-time">{{ formatTime(task.createTime) }}</span>
              </div>
              <span v-if="task.progress > 0 && task.status === 'TRAINING'" class="history-progress">
                {{ Math.round(task.progress * 100) }}%
              </span>
            </div>
          </div>
        </section>
      </template>

      <!-- Share Modal -->
      <div v-if="showShareModal" class="modal-overlay" @click.self="showShareModal = false">
        <div class="modal-content">
          <div class="modal-header">
            <h2>{{ t("voices.shareVoice") }}</h2>
            <button class="modal-close" @click="showShareModal = false">&times;</button>
          </div>
          <div class="modal-body">
            <ShareVoicePage :voice-asset-id="voiceId" @close="showShareModal = false" />
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { getVoiceDetail, getVoiceTrainingTasks, cancelTrainingTask, getTestAudioUrl, subscribeTrainingStatus, deleteVoiceAsset, type VoiceAssetDetail, type TrainingTask, type TrainingStatusEvent } from "../../services/modules/voice.api";
import ShareVoicePage from "./ShareVoicePage.vue";

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();

const voiceId = computed(() => route.params.id as string);

const loading = ref(true);
const error = ref<string | null>(null);
const voice = ref<VoiceAssetDetail | null>(null);

const tasksLoading = ref(false);
const tasks = ref<TrainingTask[]>([]);

const showShareModal = ref(false);

// SSE 相关
let eventSource: EventSource | null = null;

// 音频播放
const audioUrl = ref<string | null>(null);
const isLoadingAudio = ref(false);

const normalizeVoiceStatus = (status: unknown): VoiceAssetDetail["status"] => {
  const raw = String(status ?? "").toUpperCase();
  if (raw === "CREATING" || raw === "TRAINING" || raw === "PROCESSING") return "PROCESSING";
  if (raw === "READY" || raw === "SUCCESS") return "READY";
  if (raw === "FAILED" || raw === "ERROR") return "FAILED";
  return "PENDING";
};

const normalizeTaskStatus = (status: unknown): string => {
  const raw = String(status ?? "").toUpperCase();
  if (raw === "SUCCESS" || raw === "COMPLETED") return "COMPLETED";
  if (raw === "TRAINING" || raw === "PROCESSING") return "TRAINING";
  if (raw === "FAILED" || raw === "ERROR") return "FAILED";
  if (raw === "CANCELLED") return "CANCELLED";
  return "PENDING";
};

const normalizeProgress = (value: unknown): number => {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n) || n < 0) return 0;
  return n > 1 ? n / 100 : n;
};

const getStatusClass = (status: string): string => {
  const map: Record<string, string> = {
    PENDING: "status-pending",
    PROCESSING: "status-processing",
    READY: "status-ready",
    FAILED: "status-failed",
  };
  return map[status] || "";
};

const getStatusText = (status: string): string => {
  const map: Record<string, string> = {
    PENDING: t("voices.pending"),
    PROCESSING: t("voices.processing"),
    READY: t("voices.ready"),
    FAILED: t("voices.failed"),
  };
  return map[status] || status;
};

const getTaskStatusText = (status: string): string => {
  const map: Record<string, string> = {
    PENDING: t("voices.pending"),
    TRAINING: t("voices.processing"),
    COMPLETED: t("voices.ready"),
    FAILED: t("voices.failed"),
    CANCELLED: t("voices.cancel"),
  };
  return map[status] || status;
};

const formatTime = (time: string): string => {
  const date = new Date(time);
  const current = String(locale.value || "zh-CN");
  const dateLocale = current === "en-US" ? "en-US" : "zh-CN";
  return date.toLocaleDateString(dateLocale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const goBack = () => {
  router.push("/voices");
};

const startChat = () => {
  router.push(`/chat?voiceAssetId=${voiceId.value}`);
};

const goToEdit = () => {
  router.push(`/voices/${voiceId.value}/edit`);
};

const cancelTraining = async () => {
  if (!confirm(t("voices.confirmCancel"))) return;
  try {
    const latestTask = tasks.value.find((task) => task.status === "TRAINING" || task.status === "PENDING") || tasks.value[0];
    if (!latestTask?.taskId) {
      console.warn("No training task found for cancellation");
      return;
    }
    await cancelTrainingTask(latestTask.taskId);
    await fetchVoice();
    await fetchTasks();
  } catch (e) {
    console.error("Failed to cancel training:", e);
  }
};

const retryTraining = () => {
  router.push(`/voices/${voiceId.value}/retry`);
};

const deleteVoice = async () => {
  if (!confirm(t("voices.confirmDelete"))) return;
  try {
    await deleteVoiceAsset(voiceId.value);
    router.push("/voices");
  } catch (e) {
    console.error("Failed to delete voice:", e);
    alert(t("voices.deleteFailed") || "删除失败");
  }
};

const fetchVoice = async () => {
  if (!voiceId.value) {
    error.value = t("voices.loadError");
    loading.value = false;
    return;
  }
  try {
    loading.value = true;
    error.value = null;
    const result = await getVoiceDetail(voiceId.value);
    if (result.code === 200 && result.data) {
      voice.value = {
        ...result.data,
        status: normalizeVoiceStatus(result.data.status),
        progress: normalizeProgress(result.data.progress),
      };
    } else {
      error.value = result.message || t("voices.loadError");
    }
  } catch (e) {
    error.value = t("voices.loadError");
    console.error(e);
  } finally {
    loading.value = false;
  }
};

// 启动 SSE 订阅
const startSseSubscription = (taskId: string) => {
  // 如果已有连接，先关闭
  stopSseSubscription();

  eventSource = subscribeTrainingStatus(
    taskId,
    (event: TrainingStatusEvent) => {
      console.log("收到训练状态更新:", event);

      // 更新本地状态
      if (voice.value) {
        // 更新进度
        if (event.progress !== undefined) {
          voice.value.progress = event.progress / 100;
        }

        // 更新状态
        if (event.status === "success") {
          voice.value.status = "READY";
          voice.value.voiceModelId = event.voiceModelId;
          voice.value.similarityScore = event.similarityScore;
          // 成功后停止订阅
          stopSseSubscription();
          // 刷新任务列表
          fetchTasks();
        } else if (event.status === "failed" || event.status === "cancelled") {
          voice.value.status = "FAILED";
          // 失败后停止订阅
          stopSseSubscription();
          // 刷新任务列表
          fetchTasks();
        } else if (event.status === "training") {
          voice.value.status = "PROCESSING";
        }
      }
    },
    (error: Event) => {
      console.error("SSE 连接错误:", error);
      // 可以在这里处理重连逻辑
    }
  );
};

// 停止 SSE 订阅
const stopSseSubscription = () => {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
};

// 加载测试音频
const loadTestAudio = async () => {
  if (!voice.value?.voiceModelId || isLoadingAudio.value) return;

  try {
    isLoadingAudio.value = true;
    // 释放之前的 URL
    if (audioUrl.value) {
      URL.revokeObjectURL(audioUrl.value);
    }
    audioUrl.value = await getTestAudioUrl(voice.value.voiceModelId);
  } catch (e) {
    console.error("Failed to load test audio:", e);
    audioUrl.value = null;
  } finally {
    isLoadingAudio.value = false;
  }
};

const fetchTasks = async () => {
  if (!voiceId.value) {
    tasksLoading.value = false;
    return;
  }
  try {
    tasksLoading.value = true;
    const result = await getVoiceTrainingTasks(voiceId.value);
    const list = Array.isArray(result.data) ? result.data : [];
    if (result.code === 200) {
      tasks.value = list.map((task) => ({
        ...task,
        status: normalizeTaskStatus(task.status),
        progress: normalizeProgress(task.progress),
      }));
    }
  } catch (e) {
    console.error("Failed to fetch training tasks:", e);
  } finally {
    tasksLoading.value = false;
  }
};

onMounted(async () => {
  await fetchVoice();
  await fetchTasks();

  // 如果任务正在进行中，订阅 SSE 获取实时更新
  if (voice.value?.status === "PROCESSING" && tasks.value.length > 0) {
    const latestTask = tasks.value[0];
    if (latestTask?.taskId) {
      startSseSubscription(latestTask.taskId);
    }
  }
});

// 组件卸载时清理 SSE 连接
onUnmounted(() => {
  stopSseSubscription();
  // 释放音频 URL
  if (audioUrl.value) {
    URL.revokeObjectURL(audioUrl.value);
    audioUrl.value = null;
  }
});

// 监听 voice 和 tasks 变化，启动/停止 SSE
watch([() => voice.value?.status, () => tasks.value], ([newStatus, newTasks]) => {
  if (newStatus === "PROCESSING" && newTasks.length > 0) {
    const latestTask = newTasks[0];
    if (latestTask?.taskId && !eventSource) {
      startSseSubscription(latestTask.taskId);
    }
  } else if (newStatus !== "PROCESSING" && eventSource) {
    stopSseSubscription();
  }
}, { immediate: true });

// Watch for voiceId changes to refetch data when navigating between voice details
watch(voiceId, (newId) => {
  if (newId) {
    stopSseSubscription();
    fetchVoice();
    fetchTasks();
  }
});
</script>

<style scoped>
.voice-detail-shell {
  position: relative;
  padding: var(--space-6) 0 var(--space-9);
  overflow: hidden;
}

.voice-detail-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(720px 480px at 50% 0%, rgba(253, 186, 116, 0.12), transparent 60%);
  pointer-events: none;
}

.voice-detail-page {
  position: relative;
  z-index: 1;
  max-width: 800px;
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

/* Loading / Error */
.loading-state,
.error-state {
  display: grid;
  gap: var(--space-4);
  justify-items: center;
  padding: var(--space-9) 0;
  text-align: center;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 3px solid rgba(253, 186, 116, 0.2);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  color: #b91c1c;
}

.error-icon svg {
  width: 44px;
  height: 44px;
}

.error-state h3 {
  margin: 0;
  font-family: var(--font-display);
}

.ghost-cta {
  padding: 10px 18px;
  border-radius: 999px;
  border: 1px solid rgba(229, 139, 58, 0.3);
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.8);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.ghost-cta:hover {
  border-color: rgba(229, 139, 58, 0.6);
  background: rgba(255, 255, 255, 0.95);
}

/* Card Style */
.card {
  padding: var(--space-5);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(239, 227, 215, 0.9);
  box-shadow: var(--shadow-card);
  margin-bottom: var(--space-4);
}

/* Header */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-5);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}

.header-left {
  display: flex;
  gap: var(--space-4);
}

.voice-avatar {
  width: 72px;
  height: 72px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  color: #9a3412;
  background: linear-gradient(135deg, rgba(253, 186, 116, 0.32), rgba(251, 146, 60, 0.22));
  flex-shrink: 0;
}

.voice-avatar svg {
  width: 32px;
  height: 32px;
}

.voice-avatar.status-ready {
  color: #15803d;
  background: linear-gradient(135deg, rgba(74, 222, 128, 0.25), rgba(34, 197, 94, 0.15));
}

.voice-avatar.status-processing {
  color: #1d4ed8;
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.25), rgba(59, 130, 246, 0.15));
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.voice-avatar.status-failed {
  color: #b91c1c;
  background: linear-gradient(135deg, rgba(248, 113, 113, 0.25), rgba(239, 68, 68, 0.15));
}

.header-info {
  display: grid;
  gap: var(--space-2);
}

.voice-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: 24px;
}

.voice-desc {
  margin: 0;
  color: var(--color-muted);
  font-size: 14px;
}

.voice-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.status-badge {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 500;
  background: rgba(253, 186, 116, 0.2);
  color: #c26a28;
}

.status-badge.status-ready {
  background: rgba(74, 222, 128, 0.2);
  color: #15803d;
}

.status-badge.status-processing {
  background: rgba(96, 165, 250, 0.2);
  color: #1d4ed8;
}

.status-badge.status-failed {
  background: rgba(248, 113, 113, 0.2);
  color: #b91c1c;
}

.default-badge {
  padding: 4px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #fb923c, #f97316);
  color: white;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

.create-time {
  font-size: 13px;
  color: var(--color-muted);
}

.header-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.primary-cta {
  padding: 10px 18px;
  border-radius: 999px;
  border: none;
  font-weight: 600;
  font-size: 14px;
  background: linear-gradient(135deg, #fb923c, #f97316);
  color: white;
  box-shadow: 0 12px 25px rgba(249, 115, 22, 0.28);
  cursor: pointer;
  transition: all 0.2s ease;
}

.primary-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 30px rgba(249, 115, 22, 0.35);
}

.danger-cta {
  padding: 10px 18px;
  border-radius: 999px;
  border: 1px solid rgba(248, 113, 113, 0.4);
  font-weight: 600;
  font-size: 14px;
  background: rgba(248, 113, 113, 0.1);
  color: #b91c1c;
  cursor: pointer;
  transition: all 0.2s ease;
}

.danger-cta:hover {
  background: rgba(248, 113, 113, 0.2);
}

/* Progress Section */
.progress-section h3,
.result-section h3,
.history-section h3 {
  margin: 0 0 var(--space-4);
  font-family: var(--font-display);
  font-size: 18px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
}

.progress-percent {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-accent);
}

.progress-bar {
  height: 12px;
  background: rgba(253, 186, 116, 0.2);
  border-radius: 6px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #fb923c, #f97316);
  border-radius: 6px;
  transition: width 0.3s ease;
}

.progress-tip {
  margin: var(--space-3) 0;
  font-size: 13px;
  color: var(--color-muted);
}

/* Result Section */
.result-metrics {
  display: grid;
  gap: var(--space-4);
}

.metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) 0;
  border-bottom: 1px solid rgba(239, 227, 215, 0.6);
}

.metric-label {
  color: var(--color-muted);
  font-size: 14px;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-accent);
}

/* 音频预览 */
.audio-preview {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid rgba(239, 227, 215, 0.6);
}

.audio-preview .ghost-cta {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.audio-loading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-muted);
  font-size: 14px;
}

.audio-player {
  margin-top: var(--space-2);
}

.audio-player audio {
  width: 100%;
  height: 40px;
  border-radius: 8px;
}

/* Failed Section */
.failed-section {
  text-align: center;
}

.failed-icon {
  width: 52px;
  height: 52px;
  margin: 0 auto var(--space-3);
  display: grid;
  place-items: center;
  color: #b45309;
}

.failed-icon svg {
  width: 46px;
  height: 46px;
}

.failed-section h3 {
  margin-bottom: var(--space-2);
}

.failed-section p {
  margin: 0 0 var(--space-5);
  color: var(--color-muted);
}

.failed-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
}

/* History Section */
.mini-loading {
  display: grid;
  justify-items: center;
  padding: var(--space-4) 0;
}

.mini-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(253, 186, 116, 0.2);
  border-top-color: var(--color-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.empty-history {
  text-align: center;
  padding: var(--space-4) 0;
  color: var(--color-muted);
}

.history-list {
  display: grid;
  gap: var(--space-3);
}

.history-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: 12px;
  background: rgba(253, 186, 116, 0.08);
}

.history-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.8);
  display: grid;
  place-items: center;
  color: #1d4ed8;
}

.history-icon svg {
  width: 16px;
  height: 16px;
}

.history-info {
  flex: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.history-status {
  font-size: 14px;
  font-weight: 500;
}

.history-status.status-completed { color: #15803d; }
.history-status.status-failed { color: #b91c1c; }
.history-status.status-cancelled { color: #ca8a04; }
.history-status.status-training,
.history-status.status-pending { color: #1d4ed8; }

.history-time {
  font-size: 12px;
  color: var(--color-muted);
}

.history-progress {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-accent);
}

/* Modal */
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
  max-width: 600px;
  max-height: 80vh;
  background: white;
  border-radius: 20px;
  overflow: hidden;
  display: grid;
  grid-template-rows: auto 1fr;
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
  background: rgba(253, 186, 116, 0.2);
  border-radius: 50%;
  font-size: 20px;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: all 0.2s ease;
}

.modal-close:hover {
  background: rgba(253, 186, 116, 0.4);
}

.modal-body {
  overflow-y: auto;
  max-height: calc(80vh - 80px);
}
</style>



