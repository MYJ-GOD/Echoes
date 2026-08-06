<template>
  <div class="sessions-page-root">
    <main class="section">
    <div class="container">
      <h2 class="title">{{ t("sessions.title") }}</h2>
      
      <div v-if="loading && !sessions.length" class="empty">{{ t("sessions.loading") }}</div>
      
      <div v-else-if="!sessions.length" class="empty">{{ t("sessions.empty") }}</div>
      
      <div v-else>
        <div class="session-list">
          <div class="card session-item" v-for="session in sessions" :key="getSessionId(session)">
            <div class="session-content">
              <div class="session-info">
                <p class="session-name">
                  <template v-if="editingId === getSessionId(session)">
                    <input 
                      v-model="editingTitle" 
                      class="title-input"
                      @keyup.enter="saveTitle(getSessionId(session))"
                      @keyup.escape="cancelEdit"
                      ref="titleInputRef"
                    />
                  </template>
                  <template v-else>
                    {{ session.sessionTitle || t("sessions.untitled") }}
                  </template>
                </p>
                <p class="session-preview">
                  {{ t("sessions.count", { count: session.messageCount || 0 }) }}
                  <span v-if="session.lastMessageTime" class="session-time">
                    | {{ formatTime(session.lastMessageTime) }}
                  </span>
                </p>
              </div>
              <div class="session-actions">
                <button
                  v-if="!session.voiceAssetId"
                  class="action-btn voice-btn"
                  @click="openVoiceDialog(session)"
                  :title="t('sessions.selectVoice')"
                >
                  <svg class="icon-voice" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                    <line x1="8" y1="23" x2="16" y2="23"/>
                  </svg>
                </button>
                <button 
                  v-if="editingId !== getSessionId(session)"
                  class="action-btn" 
                  @click="startEdit(session)"
                  :title="t('sessions.edit')"
                >
                  <svg class="icon-edit" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button 
                  v-if="editingId === getSessionId(session)"
                  class="action-btn save-btn" 
                  @click="saveTitle(getSessionId(session))"
                  :title="t('sessions.save')"
                >
                  <svg class="icon-save" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                </button>
                <button 
                  class="action-btn delete" 
                  @click="handleDelete(getSessionId(session))"
                  :title="t('sessions.delete')"
                >
                  <svg class="icon-delete" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    <line x1="10" y1="11" x2="10" y2="17"/>
                    <line x1="14" y1="11" x2="14" y2="17"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
        
        
        <div class="pagination" v-if="totalPages > 1">
          <button 
            class="page-btn" 
            :disabled="currentPage <= 1"
            @click="goToPage(currentPage - 1)"
          >
            {{ t('sessions.prev') }}
          </button>
          <span class="page-info">
            {{ currentPage }} / {{ totalPages }}
          </span>
          <button 
            class="page-btn" 
            :disabled="currentPage >= totalPages"
            @click="goToPage(currentPage + 1)"
          >
            {{ t('sessions.next') }}
          </button>
        </div>
      </div>
    </div>
  </main>

  
  <ConfirmDialog
    :visible="showDeleteDialog"
    :title="t('sessions.delete')"
    :message="t('sessions.confirmDelete')"
    :confirm-text="t('sessions.delete')"
    :cancel-text="t('sessions.cancel')"
    danger
    @confirm="confirmDelete"
    @cancel="showDeleteDialog = false"
  />

  <!-- Voice Selection Dialog -->
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="showVoiceDialog" class="modal-overlay" @click.self="closeVoiceDialog">
        <div class="modal-content">
          <div class="modal-header">
            <h3>{{ t('sessions.selectVoice') }}</h3>
          </div>
          <div class="modal-body">
            <div class="voice-list">
              <label
                v-for="voice in voices"
                :key="voice.voiceAssetId"
                class="voice-option"
                :class="{ active: selectedVoiceId === voice.voiceAssetId }"
              >
                <input
                  type="radio"
                  name="voice"
                  :value="voice.voiceAssetId"
                  v-model="selectedVoiceId"
                />
                <span class="voice-name">{{ voice.name }}</span>
              </label>
              <label
                class="voice-option"
                :class="{ active: selectedVoiceId === '' }"
              >
                <input
                  type="radio"
                  name="voice"
                  value=""
                  v-model="selectedVoiceId"
                />
                <span class="voice-name">{{ t('sessions.defaultVoice') }}</span>
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn-cancel" @click="closeVoiceDialog">
              {{ t('sessions.cancel') }}
            </button>
            <button class="btn-confirm" @click="handleVoiceChange">
              {{ t('sessions.confirm') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from "vue";
import { useI18n } from "vue-i18n";
import { useUserStore } from "../../store/user";
import {
  listSessionsPaged,
  updateSessionTitle,
  deleteSession,
  updateSessionVoiceAssetId,
  type ConversationSession,
} from "../../services/modules/sessions.api";
import { getAvailableVoices, type VoiceAsset } from "../../services/modules/voice.api";
import ConfirmDialog from "../../components/ConfirmDialog.vue";

const { t } = useI18n();
const userStore = useUserStore();
const sessions = ref<ConversationSession[]>([]);
const loading = ref(false);

// 可用音色列表
const voices = ref<(VoiceAsset & { source: "OWN" | "SHARED" })[]>([]);
const loadingVoices = ref(false);

const currentPage = ref(1);
const pageSize = ref(20);
const totalCount = ref(0);

const totalPages = computed(() => Math.ceil(totalCount.value / pageSize.value));

const editingId = ref<string | null>(null);
const editingTitle = ref("");
const titleInputRef = ref<HTMLInputElement | null>(null);

// delete dialog
const showDeleteDialog = ref(false);
const pendingDeleteId = ref<string | null>(null);

// voice dialog
const showVoiceDialog = ref(false);
const pendingVoiceSessionId = ref<string | null>(null);
const selectedVoiceId = ref<string>("");

function openVoiceDialog(session: ConversationSession) {
  const sessionId = getSessionId(session);
  if (!sessionId) return;
  pendingVoiceSessionId.value = sessionId;
  selectedVoiceId.value = session.voiceAssetId || "";
  showVoiceDialog.value = true;
}

function closeVoiceDialog() {
  showVoiceDialog.value = false;
  pendingVoiceSessionId.value = null;
  selectedVoiceId.value = "";
}

function getSessionId(session: ConversationSession) {
  return session.conversationId || session.id || "";
}

function isApiSuccess(code?: number) {
  return code === 1 || code === 200;
}

onMounted(async () => {
  loading.value = true;
  try {
    if (!userStore.profile?.userId) {
      await userStore.fetchCurrent();
    }
    const userId = userStore.profile?.userId;
    if (!userId) return;
    await loadSessions(userId);
    await loadVoices();
  } finally {
    loading.value = false;
  }
});

async function loadVoices() {
  loadingVoices.value = true;
  try {
    const result = await getAvailableVoices();
    if (isApiSuccess(result.code) && result.data) {
      voices.value = result.data;
    }
  } catch (e) {
    console.error("Failed to load voices:", e);
  } finally {
    loadingVoices.value = false;
  }
}

async function loadSessions(userId: string) {
  loading.value = true;
  try {
    const result = await listSessionsPaged(userId, currentPage.value, pageSize.value);
    if (isApiSuccess(result.code) && result.data) {
      sessions.value = result.data.records || [];
      totalCount.value = result.data.total || 0;
    }
  } finally {
    loading.value = false;
  }
}

async function goToPage(page: number) {
  if (page < 1 || page > totalPages.value) return;
  currentPage.value = page;
  const userId = userStore.profile?.userId;
  if (userId) {
    await loadSessions(userId);
  }
}

function startEdit(session: ConversationSession) {
  const sessionId = getSessionId(session);
  editingId.value = sessionId || null;
  editingTitle.value = session.sessionTitle || "";
  nextTick(() => {
    const input = titleInputRef.value;
    if (input) {
      input.focus();
    }
  });
}

function cancelEdit() {
  editingId.value = null;
  editingTitle.value = "";
}

async function saveTitle(conversationId: string) {
  if (!conversationId) {
    cancelEdit();
    return;
  }
  if (!editingTitle.value.trim()) {
    cancelEdit();
    return;
  }
  try {
    const result = await updateSessionTitle(conversationId, editingTitle.value.trim());
    if (isApiSuccess(result.code)) {
      const session = sessions.value.find((s) => getSessionId(s) === conversationId);
      if (session) {
        session.sessionTitle = editingTitle.value.trim();
      }
    }
  } catch (e) {
    console.error("Failed to update title:", e);
  }
  cancelEdit();
}

function handleDelete(conversationId: string) {
  if (!conversationId) return;
  pendingDeleteId.value = conversationId;
  showDeleteDialog.value = true;
}

async function confirmDelete() {
  const conversationId = pendingDeleteId.value;
  if (!conversationId) return;
  
  try {
    const result = await deleteSession(conversationId);
    if (isApiSuccess(result.code)) {
      sessions.value = sessions.value.filter((s) => getSessionId(s) !== conversationId);
      totalCount.value = Math.max(0, totalCount.value - 1);
    }
  } catch (e) {
    console.error("Failed to delete session:", e);
  } finally {
    showDeleteDialog.value = false;
    pendingDeleteId.value = null;
  }
}

async function handleVoiceChange() {
  const conversationId = pendingVoiceSessionId.value;
  const voiceAssetId = selectedVoiceId.value;
  if (!conversationId) return;
  try {
    const result = await updateSessionVoiceAssetId(conversationId, voiceAssetId);
    if (isApiSuccess(result.code)) {
      const session = sessions.value.find((s) => getSessionId(s) === conversationId);
      if (session) {
        session.voiceAssetId = voiceAssetId;
      }
    }
  } catch (e) {
    console.error("Failed to update session voice:", e);
  } finally {
    closeVoiceDialog();
  }
}

function getVoiceName(voiceId: string) {
  const voice = voices.value.find((v) => v.voiceAssetId === voiceId);
  return voice ? voice.name : "";
}

function formatTime(timeStr: string) {
  if (!timeStr) return "";
  try {
    const date = new Date(timeStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    
    if (days === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
      return t('sessions.yesterday');
    } else if (days < 7) {
      return t('sessions.daysAgo', { days });
    } else {
      return date.toLocaleDateString();
    }
  } catch {
    return timeStr;
  }
}
</script>

<style scoped>
.title {
  font-family: var(--font-display);
  font-size: clamp(24px, 4vw, 32px);
  margin-bottom: var(--space-6);
  color: var(--color-text);
}

.session-list {
  display: grid;
  gap: var(--space-4);
}

.session-item {
  padding: var(--space-5);
  border-radius: 16px;
  border: 1px solid rgba(239, 227, 215, 0.7);
  background: rgba(255, 255, 255, 0.75);
  box-shadow: var(--shadow-card);
  transition: all 0.2s ease;
}

.session-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 34px rgba(77, 48, 20, 0.1);
  background: rgba(255, 255, 255, 0.9);
}

.session-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.voice-selector {
  margin-right: var(--space-4);
}

.voice-btn {
  position: relative;
}

.voice-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 100;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  padding: var(--space-2);
}

.voice-select {
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 0.85rem;
  cursor: pointer;
  min-width: 100px;
}

.voice-select:hover {
  border-color: var(--color-primary);
}

.voice-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.session-info {
  flex: 1;
}

.session-name {
  margin: 0 0 var(--space-2);
  font-weight: 600;
  font-size: 1.1rem;
}

.session-preview {
  margin: 0;
  color: var(--color-muted);
  font-size: 0.9rem;
}

.session-time {
  color: var(--color-muted);
}

.session-actions {
  display: flex;
  gap: var(--space-2);
  margin-left: var(--space-4);
}

.action-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: var(--space-2);
  border-radius: 4px;
  transition: background-color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
}

.action-btn:hover {
  background-color: var(--color-hover);
}

.action-btn.delete:hover {
  background-color: var(--color-danger-bg, #fee2e2);
}

.action-btn.delete:hover svg {
  stroke: #ef4444;
}

.action-btn.save-btn:hover {
  background-color: #dcfce7;
}

.action-btn.save-btn:hover svg {
  stroke: #22c55e;
}

.icon-edit,
.icon-delete,
.icon-save,
.icon-voice {
  width: 16px;
  height: 16px;
}

.title-input {
  font-size: 1.1rem;
  font-weight: 600;
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg);
  color: var(--color-text);
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-6);
  padding: var(--space-4) 0;
}

.page-btn {
  padding: var(--space-2) var(--space-4);
  background-color: var(--color-primary);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-btn:not(:disabled):hover {
  opacity: 0.9;
}

.page-info {
  color: var(--color-muted);
  font-size: 0.9rem;
}

.empty {
  color: var(--color-muted);
  text-align: center;
  padding: var(--space-9) var(--space-5);
  background: rgba(255, 253, 248, 0.8);
  border-radius: 20px;
  border: 1px dashed rgba(241, 180, 123, 0.4);
  backdrop-filter: blur(4px);
  font-size: 15px;
}

/* Voice Dialog Styles */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(45, 36, 32, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-4);
}

.modal-content {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: 0 20px 50px rgba(77, 48, 20, 0.2);
  width: 100%;
  max-width: 400px;
  overflow: hidden;
}

.modal-header {
  padding: var(--space-5) var(--space-6) var(--space-3);
}

.modal-header h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.25rem;
  color: var(--color-text);
}

.modal-body {
  padding: 0 var(--space-6) var(--space-5);
}

.modal-footer {
  padding: var(--space-4) var(--space-6);
  background: rgba(243, 229, 216, 0.3);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

.voice-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 300px;
  overflow-y: auto;
}

.voice-option {
  display: flex;
  align-items: center;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s ease;
}

.voice-option:hover {
  background-color: var(--color-hover);
}

.voice-option.active {
  border-color: var(--color-primary);
  background-color: rgba(249, 115, 22, 0.1);
}

.voice-option input {
  margin-right: var(--space-2);
}

.voice-name {
  font-size: 0.95rem;
  color: var(--color-text);
}

.btn-cancel,
.btn-confirm {
  padding: 10px 20px;
  border-radius: var(--radius-sm);
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.btn-cancel {
  background: transparent;
  color: var(--color-muted);
  border: 1px solid var(--color-border);
}

.btn-cancel:hover {
  background: rgba(243, 229, 216, 0.5);
  color: var(--color-text);
}

.btn-confirm {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-strong));
  color: #2a1a0f;
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.2);
}

.btn-confirm:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(249, 115, 22, 0.3);
}

/* Transition animations */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-active .modal-content,
.modal-leave-active .modal-content {
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-content,
.modal-leave-to .modal-content {
  transform: scale(0.95);
  opacity: 0;
}
</style>


