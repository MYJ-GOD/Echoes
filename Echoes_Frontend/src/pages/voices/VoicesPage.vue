<template>
  <main class="voices-shell">
    <div class="voices-glow"></div>
    <div class="container voices-page">
      <header class="page-header">
        <div class="header-content">
          <p class="eyebrow">{{ t("voices.eyebrow") }}</p>
          <h1 class="title">{{ t("voices.title") }}</h1>
          <p class="subtitle">{{ t("voices.subtitle") }}</p>
        </div>
        <router-link class="primary-cta" to="/voices/create">
          {{ t("voices.create") }}
        </router-link>
      </header>

      <!-- Filter Tabs -->
      <div class="filter-tabs">
        <button
          v-for="tab in filterTabs"
          :key="tab.value"
          class="filter-tab"
          :class="{ active: activeFilter === tab.value }"
          @click="activeFilter = tab.value"
        >
          {{ tab.label }} <span class="tab-count">({{ tab.count }})</span>
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="loading-state">
        <div class="loading-spinner"></div>
        <p>{{ t("voices.loading") }}</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredVoices.length === 0" class="empty-state">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 18V5l12-2v13"/>
            <circle cx="6" cy="18" r="3"/>
            <circle cx="18" cy="16" r="3"/>
          </svg>
        </div>
        <h3>{{ t("voices.emptyTitle") }}</h3>
        <p>{{ t("voices.emptyDesc") }}</p>
        <router-link class="ghost-cta" to="/voices/create">
          {{ t("voices.createFirst") }}
        </router-link>
      </div>
      <!-- Voice Cards -->
      <div v-else class="voices-grid">
        <div
          v-for="(voice, index) in filteredVoices"
          :key="voice.voiceAssetId"
          class="voice-card"
          :style="{ animationDelay: `${index * 50}ms` }"
          @click="goToDetail(voice.voiceAssetId)"
        >
          <div class="card-header">
            <div class="voice-icon" :class="getStatusClass(voice.status)">
              <svg v-if="voice.status === 'READY'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9"/>
                <path d="m8.5 12.5 2.3 2.3 4.7-4.8"/>
              </svg>
              <svg v-else-if="voice.status === 'PROCESSING'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12a9 9 0 1 1-3.2-6.9"/>
                <polyline points="21 3 21 9 15 9"/>
              </svg>
              <svg v-else-if="voice.status === 'FAILED'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9"/>
                <line x1="9" y1="9" x2="15" y2="15"/>
                <line x1="15" y1="9" x2="9" y2="15"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="9"/>
                <polyline points="12 7 12 12 15.5 14"/>
              </svg>
            </div>
            <div class="card-header-right">
              <div v-if="voice.isDefault" class="default-badge">
                {{ t("voices.default") }}
              </div>
              <button
                v-if="canDelete(voice)"
                class="more-btn"
                @click.stop="toggleMoreMenu(voice.voiceAssetId)"
              >
                ⋯
              </button>
              <div
                v-if="activeMenuVoiceId === voice.voiceAssetId"
                class="more-menu"
                @click.stop
              >
                <button
                  v-if="!voice.isDefault && voice.status === 'READY'"
                  class="more-menu-item"
                  @click.stop="setDefaultVoice(voice.voiceAssetId)"
                >
                  {{ t("voices.setDefault") }}
                </button>
                <button
                  v-else-if="voice.isDefault"
                  class="more-menu-item"
                  @click.stop="cancelDefaultVoice(voice.voiceAssetId)"
                >
                  {{ t("voices.cancelDefault") }}
                </button>
                <button class="more-menu-item danger" @click.stop="askDelete(voice.voiceAssetId)">
                  {{ t("voices.delete") }}
                </button>
              </div>
            </div>
          </div>

          <div class="card-body">
            <h3 class="voice-name">{{ voice.name }}</h3>
            <p v-if="voice.description" class="voice-desc">{{ voice.description }}</p>
            <div class="voice-meta">
              <span class="status-tag" :class="getStatusClass(voice.status)">
                {{ getStatusText(voice.status) }}
              </span>
              <span class="create-time">{{ formatTime(voice.createTime) }}</span>
            </div>
          </div>

          <div class="card-actions">
            <button
              class="action-btn primary"
              @click.stop="runPrimaryAction(voice)"
            >
              {{ getPrimaryActionLabel(voice) }}
            </button>
          </div>
        </div>
      </div>

    </div>
    <ConfirmDialog
      v-model:visible="deleteDialogVisible"
      :title="t('voices.delete')"
      :message="t('voices.confirmDelete')"
      :confirm-text="t('voices.delete')"
      :cancel-text="t('voices.cancel')"
      :loading="deleteLoading"
      @confirm="confirmDelete"
    />
    <div v-if="sessionPickerVisible" class="session-picker-mask" @click="closeSessionPicker">
      <div class="session-picker" @click.stop>
        <div class="session-picker-header">
          <h3>{{ t("voices.pickSessionTitle") }}</h3>
          <button class="session-picker-close" @click="closeSessionPicker">×</button>
        </div>
        <p class="session-picker-subtitle">{{ t("voices.pickSessionDesc") }}</p>
        <div v-if="sessionPickerLoading" class="session-picker-loading">{{ t("voices.loading") }}</div>
        <div v-else-if="sessionOptions.length === 0" class="session-picker-empty">
          {{ t("voices.noSessionToPick") }}
        </div>
        <div v-else class="session-picker-list">
          <button
            v-for="session in sessionOptions"
            :key="session.conversationId || session.id"
            class="session-option"
            :class="{ selected: selectedSessionId === (session.conversationId || session.id) }"
            @click="selectedSessionId = String(session.conversationId || session.id || '')"
          >
            <span class="session-option-title">{{ session.sessionTitle || t("sessions.untitled") }}</span>
            <span class="session-option-meta">
              {{ t("sessions.count", { count: session.messageCount || 0 }) }}
            </span>
          </button>
        </div>
        <div class="session-picker-actions">
          <button class="action-btn ghost" @click="closeSessionPicker">
            {{ t("voices.cancel") }}
          </button>
          <button
            class="action-btn primary"
            :disabled="!selectedSessionId || sessionBindingLoading"
            @click="confirmUseVoiceInSession"
          >
            {{ sessionBindingLoading ? t("chat.sending") : t("voices.confirm") }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated, onBeforeUnmount, onDeactivated } from "vue";
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useUserStore } from "../../store/user";
import ConfirmDialog from "../../components/ConfirmDialog.vue";
import {
  getAvailableVoices,
  deleteVoiceAsset,
  setDefaultVoice as apiSetDefaultVoice,
  type VoiceAsset,
} from "../../services/modules/voice.api";
import {
  listSessions,
  updateSessionVoiceAssetId,
  type ConversationSession,
} from "../../services/modules/sessions.api";

const { t, locale } = useI18n();
const router = useRouter();
const userStore = useUserStore();
type DisplayVoice = VoiceAsset & { source?: "OWN" | "SHARED" };

const loading = ref(true);
const voices = ref<DisplayVoice[]>([]);
const activeFilter = ref("all");
const deleteDialogVisible = ref(false);
const deleteLoading = ref(false);
const deletingVoiceId = ref("");
const activeMenuVoiceId = ref("");
const sessionPickerVisible = ref(false);
const sessionPickerLoading = ref(false);
const sessionBindingLoading = ref(false);
const sessionOptions = ref<ConversationSession[]>([]);
const selectedSessionId = ref("");
const selectedVoiceId = ref("");
const pollingTimer = ref<number | null>(null);
const fetchingVoices = ref(false);
const POLLING_INTERVAL_MS = 3000;

const filterTabs = computed(() => [
  { label: t("voices.all"), value: "all", count: voices.value.length },
  {
    label: t("voices.ready"),
    value: "READY",
    count: voices.value.filter((v) => v.status === "READY").length,
  },
  {
    label: t("voices.processing"),
    value: "PROCESSING",
    count: voices.value.filter((v) => v.status === "PROCESSING").length,
  },
  {
    label: t("voices.failed"),
    value: "FAILED",
    count: voices.value.filter((v) => v.status === "FAILED").length,
  },
  {
    label: t("voices.sharedFilter"),
    value: "SHARED",
    count: voices.value.filter((v) => v.source === "SHARED").length,
  },
]);

const normalizeStatus = (status: unknown): VoiceAsset["status"] => {
  const raw = String(status ?? "").toUpperCase();
  if (raw === "CREATING" || raw === "TRAINING" || raw === "PROCESSING") return "PROCESSING";
  if (raw === "READY" || raw === "SUCCESS") return "READY";
  if (raw === "FAILED" || raw === "ERROR") return "FAILED";
  return "PENDING";
};

const toVoiceArray = (data: unknown): DisplayVoice[] => {
  const currentUserId = userStore.profile?.userId;
  const source = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as { records?: unknown[] }).records)
      ? (data as { records: unknown[] }).records
      : [];

  return source.map((item) => {
    const v = (item ?? {}) as Partial<VoiceAsset>;
    return {
      ...v,
      voiceAssetId: String(v.voiceAssetId ?? ""),
      ownerUserId: String(v.ownerUserId ?? ""),
      name: String(v.name ?? ""),
      refId: String(v.refId ?? ""),
      isDefault: Boolean(v.isDefault),
      createTime: String(v.createTime ?? ""),
      updateTime: String(v.updateTime ?? ""),
      status: normalizeStatus(v.status),
      source:
        v.source === "SHARED" || v.source === "OWN"
          ? v.source
          : currentUserId && String(v.ownerUserId ?? "") !== currentUserId
            ? "SHARED"
            : "OWN",
    };
  });
};

const filteredVoices = computed(() => {
  if (!Array.isArray(voices.value)) {
    return [];
  }
  if (activeFilter.value === "all") {
    return voices.value;
  }
  if (activeFilter.value === "SHARED") {
    return voices.value.filter((v) => v.source === "SHARED");
  }
  return voices.value.filter((v) => v.status === activeFilter.value);
});

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

const formatTime = (time: string): string => {
  const date = new Date(time);
  const current = String(locale.value || "zh-CN");
  const dateLocale = current === "en-US" ? "en-US" : "zh-CN";
  return date.toLocaleDateString(dateLocale, { month: "short", day: "numeric" });
};

const goToDetail = (id: string) => {
  router.push(`/voices/${id}`);
};

const startChat = (voiceAssetId: string) => {
  router.push(`/chat?voiceAssetId=${voiceAssetId}`);
};

const toggleMoreMenu = (voiceAssetId: string) => {
  activeMenuVoiceId.value = activeMenuVoiceId.value === voiceAssetId ? "" : voiceAssetId;
};

const getPrimaryActionLabel = (voice: VoiceAsset) => {
  if (voice.status === "READY") return t("voices.useVoice");
  if (voice.status === "PROCESSING") return t("voices.viewProgress");
  if (voice.status === "FAILED") return t("voices.viewFailure");
  return t("voices.viewDetail");
};

const runPrimaryAction = (voice: VoiceAsset) => {
  if (voice.status === "READY") {
    openSessionPicker(voice.voiceAssetId);
    return;
  }
  goToDetail(voice.voiceAssetId);
};

const canDelete = (voice: VoiceAsset) => {
  const currentUserId = userStore.profile?.userId;
  return !!currentUserId && voice.ownerUserId === currentUserId;
};

const askDelete = (voiceAssetId: string) => {
  activeMenuVoiceId.value = "";
  deletingVoiceId.value = voiceAssetId;
  deleteDialogVisible.value = true;
};

const openSessionPicker = async (voiceAssetId: string) => {
  selectedVoiceId.value = voiceAssetId;
  selectedSessionId.value = "";
  sessionPickerVisible.value = true;
  sessionPickerLoading.value = true;
  try {
    if (!userStore.profile?.userId) {
      await userStore.fetchCurrent();
    }
    const userId = userStore.profile?.userId;
    if (!userId) {
      sessionOptions.value = [];
      return;
    }
    const result = await listSessions(userId);
    sessionOptions.value = result.data || [];
  } catch (error) {
    console.error("Failed to load sessions for picker:", error);
    sessionOptions.value = [];
  } finally {
    sessionPickerLoading.value = false;
  }
};

const closeSessionPicker = (force = false) => {
  if (sessionBindingLoading.value && !force) return;
  sessionPickerVisible.value = false;
  selectedSessionId.value = "";
  selectedVoiceId.value = "";
};

const confirmUseVoiceInSession = async () => {
  if (!selectedSessionId.value || !selectedVoiceId.value || sessionBindingLoading.value) return;
  try {
    sessionBindingLoading.value = true;
    await updateSessionVoiceAssetId(selectedSessionId.value, selectedVoiceId.value);
    closeSessionPicker(true);
    router.push(`/chat?sessionId=${selectedSessionId.value}&voiceAssetId=${selectedVoiceId.value}`);
  } catch (error) {
    console.error("Failed to bind voice to session:", error);
    alert(t("voices.saveFailed"));
  } finally {
    sessionBindingLoading.value = false;
  }
};

const setDefaultVoice = async (voiceAssetId: string) => {
  activeMenuVoiceId.value = "";
  try {
    const result = await apiSetDefaultVoice(voiceAssetId);
    if (result.code === 200 || result.code === 1) {
      // 更新本地状态
      voices.value.forEach((v) => {
        v.isDefault = v.voiceAssetId === voiceAssetId;
      });
      alert(t("voices.setDefaultSuccess"));
    } else {
      alert(result.message || t("voices.setDefaultFailed"));
    }
  } catch (error) {
    console.error("Failed to set default voice:", error);
    alert(t("voices.setDefaultFailed"));
  }
};

const cancelDefaultVoice = async (voiceAssetId: string) => {
  activeMenuVoiceId.value = "";
  try {
    // 取消默认音色：调用 setDefaultVoice 接口但后端需要支持取消逻辑
    // 当前简化处理：提示用户选择其他音色为默认
    alert(t("voices.cancelDefaultHint"));
  } catch (error) {
    console.error("Failed to cancel default voice:", error);
  }
};

const confirmDelete = async () => {
  if (!deletingVoiceId.value || deleteLoading.value) return;
  try {
    deleteLoading.value = true;
    const result = await deleteVoiceAsset(deletingVoiceId.value);
    if (result.code === 200) {
      voices.value = voices.value.filter((v) => v.voiceAssetId !== deletingVoiceId.value);
    } else {
      alert(result.message || t("voices.deleteFailed"));
    }
  } catch (error) {
    console.error("Failed to delete voice:", error);
    alert(t("voices.deleteFailed"));
  } finally {
    deleteLoading.value = false;
    deleteDialogVisible.value = false;
    deletingVoiceId.value = "";
  }
};

const hasProcessingVoice = () =>
  voices.value.some((voice) => voice.status === "PROCESSING");

const stopTrainingPolling = () => {
  if (pollingTimer.value !== null) {
    window.clearInterval(pollingTimer.value);
    pollingTimer.value = null;
  }
};

const startTrainingPolling = () => {
  if (pollingTimer.value !== null) return;
  pollingTimer.value = window.setInterval(() => {
    void fetchVoices(false);
  }, POLLING_INTERVAL_MS);
};

const syncTrainingPolling = () => {
  if (hasProcessingVoice()) {
    startTrainingPolling();
  } else {
    stopTrainingPolling();
  }
};

const fetchVoices = async (showLoading = true) => {
  if (fetchingVoices.value) return;
  fetchingVoices.value = true;
  try {
    if (showLoading) {
      loading.value = true;
    }
    const result = await getAvailableVoices();
    voices.value = result.code === 200 ? toVoiceArray(result.data) : [];
  } catch (error) {
    console.error("Failed to fetch voices:", error);
    if (showLoading) {
      voices.value = [];
    }
  } finally {
    loading.value = false;
    fetchingVoices.value = false;
    activeMenuVoiceId.value = "";
    syncTrainingPolling();
  }
};

onMounted(() => {
  void fetchVoices();
});

// Refresh voice list when returning to this page
onActivated(() => {
  void fetchVoices();
});

onDeactivated(() => {
  stopTrainingPolling();
});

onBeforeUnmount(() => {
  stopTrainingPolling();
});
</script>

<style scoped>
.voices-shell {
  position: relative;
  padding: var(--space-8) 0 var(--space-9);
  overflow: hidden;
}

.voices-glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(720px 480px at 20% 10%, rgba(253, 186, 116, 0.09), transparent 60%),
    radial-gradient(680px 420px at 80% 20%, rgba(254, 215, 170, 0.07), transparent 60%);
  pointer-events: none;
}

.voices-page {
  position: relative;
  z-index: 1;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--space-6);
}

.header-content {
  display: grid;
  gap: var(--space-2);
}

.eyebrow {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--color-accent);
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
  padding: 9px 16px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 14px;
  border: 1px solid rgba(229, 139, 58, 0.35);
  background: rgba(255, 255, 255, 0.92);
  color: var(--color-text);
  transition: all 0.2s ease;
}

.primary-cta:hover {
  transform: translateY(-2px);
  border-color: rgba(229, 139, 58, 0.7);
  background: #fff;
}

/* Filter Tabs */
.filter-tabs {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
  position: sticky;
  top: 10px;
  z-index: 4;
  background: rgba(255, 249, 243, 0.86);
  padding: 6px;
  border-radius: 12px;
  backdrop-filter: blur(8px);
}

.filter-tab {
  padding: 8px 16px;
  border-radius: 999px;
  border: 1px solid rgba(229, 139, 58, 0.25);
  background: rgba(255, 255, 255, 0.8);
  color: var(--color-text);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-tab:hover {
  border-color: rgba(229, 139, 58, 0.5);
  background: rgba(253, 186, 116, 0.1);
}

.filter-tab.active {
  background: linear-gradient(135deg, rgba(251, 146, 60, 0.2), rgba(249, 115, 22, 0.15));
  border-color: rgba(249, 115, 22, 0.4);
  color: var(--color-text);
  font-weight: 600;
}

.tab-count {
  color: var(--color-muted);
}

/* Loading */
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

/* Empty State */
.empty-state {
  display: grid;
  gap: var(--space-3);
  justify-items: center;
  padding: var(--space-9) var(--space-5);
  text-align: center;
  background: rgba(255, 253, 248, 0.8);
  border-radius: 20px;
  border: 1px dashed rgba(241, 180, 123, 0.5);
  backdrop-filter: blur(4px);
  animation: fade-in 0.6s ease-out;
}

@keyframes fade-in {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}

.empty-icon {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
}

.empty-icon svg {
  width: 44px;
  height: 44px;
  stroke: #ea580c;
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
  border: 1px solid rgba(229, 139, 58, 0.3);
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.8);
  font-weight: 600;
  font-size: 14px;
  transition: all 0.2s ease;
}

.ghost-cta:hover {
  border-color: rgba(229, 139, 58, 0.6);
  background: rgba(255, 255, 255, 0.95);
}

/* Voice Grid */
.voices-grid {
  display: grid;
  gap: var(--space-4);
  margin-bottom: var(--space-7);
}

@media (min-width: 600px) {
  .voices-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1000px) {
  .voices-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

/* Voice Card */
.voice-card {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
  border-radius: 18px;
  border: 1px solid rgba(239, 227, 215, 0.7);
  background: rgba(255, 255, 255, 0.75);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: all 0.2s ease;
  animation: card-enter 0.5s var(--ease-standard) backwards;
}

@keyframes card-enter {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.voice-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 20px 40px rgba(77, 48, 20, 0.12);
  background: rgba(255, 255, 255, 0.85);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  position: relative;
}

.card-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
}

.voice-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, rgba(253, 186, 116, 0.32), rgba(251, 146, 60, 0.22));
}

.voice-icon.status-ready {
  background: linear-gradient(135deg, rgba(74, 222, 128, 0.25), rgba(34, 197, 94, 0.15));
}

.voice-icon.status-processing {
  background: linear-gradient(135deg, rgba(96, 165, 250, 0.25), rgba(59, 130, 246, 0.15));
}

.voice-icon.status-failed {
  background: linear-gradient(135deg, rgba(248, 113, 113, 0.25), rgba(239, 68, 68, 0.15));
}

.voice-icon svg {
  width: 22px;
  height: 22px;
}

.default-badge {
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(251, 146, 60, 0.16);
  color: #c45d1f;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.more-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: 1px solid rgba(229, 139, 58, 0.2);
  background: rgba(255, 255, 255, 0.9);
  color: #985425;
  font-size: 18px;
  line-height: 1;
  letter-spacing: 0;
  white-space: nowrap;
  overflow: hidden;
  cursor: pointer;
}

.more-btn:hover {
  background: rgba(253, 186, 116, 0.12);
}

.more-menu {
  position: absolute;
  right: 0;
  top: 34px;
  min-width: 120px;
  border: 1px solid rgba(229, 139, 58, 0.22);
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 12px 24px rgba(60, 35, 14, 0.14);
  padding: 6px;
  z-index: 5;
}

.more-menu-item {
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  cursor: pointer;
}

.more-menu-item:hover {
  background: rgba(253, 186, 116, 0.12);
}

.more-menu-item.danger {
  color: #b91c1c;
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

.voice-desc {
  margin: 0;
  color: var(--color-muted);
  font-size: 13px;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.voice-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

.status-tag {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(253, 186, 116, 0.2);
  color: #c26a28;
}

.status-tag.status-ready {
  background: rgba(74, 222, 128, 0.2);
  color: #15803d;
}

.status-tag.status-processing {
  background: rgba(96, 165, 250, 0.2);
  color: #1d4ed8;
}

.status-tag.status-failed {
  background: rgba(248, 113, 113, 0.2);
  color: #b91c1c;
}

.create-time {
  font-size: 12px;
  color: var(--color-muted);
}

.card-actions {
  display: flex;
  padding-top: var(--space-3);
  border-top: 1px solid rgba(239, 227, 215, 0.6);
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
  border: 1px solid rgba(229, 139, 58, 0.25);
  color: var(--color-text);
}

.action-btn.ghost:hover {
  background: rgba(253, 186, 116, 0.1);
}

@media (max-width: 640px) {
  .filter-tabs {
    top: 0;
  }
}

.session-picker-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: grid;
  place-items: center;
  z-index: 1000;
  padding: 16px;
}

.session-picker {
  width: min(560px, 100%);
  max-height: 78vh;
  background: #fff;
  border-radius: 16px;
  border: 1px solid rgba(229, 139, 58, 0.2);
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.25);
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: 10px;
  padding: 16px;
}

.session-picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.session-picker-header h3 {
  margin: 0;
  font-size: 18px;
}

.session-picker-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 8px;
  background: rgba(148, 163, 184, 0.16);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}

.session-picker-subtitle {
  margin: 0;
  color: var(--color-muted);
  font-size: 13px;
}

.session-picker-loading,
.session-picker-empty {
  padding: 16px 8px;
  color: var(--color-muted);
  font-size: 13px;
}

.session-picker-list {
  overflow: auto;
  display: grid;
  gap: 8px;
  padding: 4px 2px;
}

.session-option {
  border: 1px solid rgba(229, 139, 58, 0.2);
  background: rgba(255, 255, 255, 0.95);
  border-radius: 10px;
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
  display: grid;
  gap: 2px;
}

.session-option:hover {
  background: rgba(253, 186, 116, 0.1);
}

.session-option.selected {
  border-color: rgba(249, 115, 22, 0.55);
  background: rgba(251, 146, 60, 0.12);
}

.session-option-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.session-option-meta {
  font-size: 12px;
  color: var(--color-muted);
}

.session-picker-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding-top: 4px;
}
</style>


