<template>
  <main class="chat-page">
    
    <aside class="contact-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <div class="sidebar-title">
          <span class="dot"></span>
          <span>{{ t("chat.sidebarTitle") }}</span>
        </div>
        <button class="new-session" type="button" @click="createNewSession">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>

      <div class="sidebar-list">
        <button
          v-for="session in sessions"
          :key="session.conversationId || session.id"
          class="session-item"
          :class="{ active: (session.conversationId || session.id) === activeSessionId }"
          type="button"
          @click="selectSession(session)"
        >
          <span class="session-icon-wrapper">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          </span>
          <div class="session-info">
            <span class="session-title">{{ session.sessionTitle || t("sessions.untitled") }}</span>
            <span class="session-meta">
              {{ t("sessions.count", { count: session.messageCount || 0 }) }}
            </span>
          </div>
        </button>

        <div v-if="!sessions.length && !loadingSessions" class="sidebar-empty">
          {{ t("chat.noSessions") }}
        </div>
        <div v-if="loadingSessions" class="sidebar-empty">
          {{ t("chat.loadingSessions") }}
        </div>
      </div>

        
        <button class="collapse-btn" type="button" @click="toggleSidebar">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
    </aside>

    
    <section class="chat-main">
      
      <div v-if="!activeSessionId" class="empty-state">
        <div class="empty-heart">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.5">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
          </svg>
        </div>
        <h2 class="empty-title">{{ t("chat.emptyTitle") }}</h2>
        <p class="empty-subtitle">{{ t("chat.emptySubtitle") }}</p>
      </div>

      
      <div v-else class="message-area">
        <div class="message-list">
          <div
            v-for="message in chatStore.messages"
            :key="message.id"
            class="message-row"
            :class="message.role"
          >
            <div
              class="message-bubble"
              :class="{ 'has-audio': message.role === 'assistant' && (message.audioUrl || (message.audioPcmChunks && message.audioPcmChunks.length)) }"
              @click="message.role === 'assistant' && (message.audioUrl || (message.audioPcmChunks && message.audioPcmChunks.length)) ? toggleAudio(message) : null"
            >
              <div class="bubble-content">
                <p>{{ message.content || t("chat.listening") }}</p>
              </div>
              <div v-if="message.role === 'assistant' && (message.audioUrl || (message.audioPcmChunks && message.audioPcmChunks.length))" class="bubble-footer">
                <span v-if="playingId === message.id" class="playing-icon">
                  <span class="voice-bar"></span>
                  <span class="voice-bar"></span>
                  <span class="voice-bar"></span>
                </span>
                <span v-else class="volume-icon">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  </svg>
                </span>
              </div>
              <span v-if="message.role === 'assistant'" class="heart-icon">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                </svg>
              </span>
            </div>
          </div>
        </div>

        
        <div class="input-area">
          <div class="input-row">
            <button class="mic-btn" type="button" :disabled="true">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
            </button>
            <input
              v-model="input"
              class="chat-input"
              type="text"
              :placeholder="t('chat.placeholder')"
              @keyup.enter="submit"
            />
            <button class="send-btn" type="button" :disabled="chatStore.loading || !activeSessionId || !input.trim()" @click="submit">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, watch } from "vue";
import { useRoute } from "vue-router";
import { useI18n } from "vue-i18n";
import { useChatStore } from "../../store/chat";
import { useUserStore } from "../../store/user";
import {
  listSessions,
  listSessionMessages,
  type ConversationSession,
  type SessionMessage
} from "../../services/modules/sessions.api";
import { createSession } from "../../services/modules/chat.api";
import { getToken } from "../../utils/token";
import { audioCache } from "../../utils/audioCache";

const { t } = useI18n();
const route = useRoute();
const chatStore = useChatStore();
const userStore = useUserStore();
const input = ref("");
const sessions = ref<ConversationSession[]>([]);
const loadingSessions = ref(false);
const sidebarCollapsed = ref(false);
const activeSessionId = ref<string | null>(null);
const activeSessionTitle = ref("");
const playingId = ref<string | null>(null);
let audioPlayer: HTMLAudioElement | null = null;
const blobUrlCache = new Map<string, string>();

const pcmPlayingId = ref<string | null>(null);
let pcmContext: AudioContext | null = null;
let pcmNextTime = 0;
let pcmConsumed = 0;
let pcmScheduledUntil = 0;
let pcmEndTimer: number | null = null;
const pcmSources: AudioBufferSourceNode[] = [];

const stopPcmPlayback = () => {
  pcmSources.forEach((source) => {
    try {
      source.stop();
    } catch {
      // ignore stop errors
    }
  });
  pcmSources.length = 0;
  pcmPlayingId.value = null;
  pcmConsumed = 0;
  pcmNextTime = 0;
  pcmScheduledUntil = 0;
  if (pcmEndTimer) {
    clearTimeout(pcmEndTimer);
    pcmEndTimer = null;
  }
  if (pcmContext) {
    pcmContext.close();
    pcmContext = null;
  }
};

const ensurePcmContext = (sampleRate: number) => {
  if (!pcmContext) {
    pcmContext = new AudioContext({ sampleRate });
  }
  if (pcmContext.state === "suspended") {
    pcmContext.resume();
  }
  return pcmContext;
};

const pcmChunkToBuffer = (chunk: ArrayBuffer, sampleRate: number) => {
  const pcm16 = new Int16Array(chunk);
  const floats = new Float32Array(pcm16.length);
  for (let i = 0; i < pcm16.length; i += 1) {
    floats[i] = Math.max(-1, Math.min(1, pcm16[i] / 32768));
  }
  const ctx = ensurePcmContext(sampleRate);
  const buffer = ctx.createBuffer(1, floats.length, sampleRate);
  buffer.copyToChannel(floats, 0);
  return buffer;
};

const schedulePcmChunks = (message: { id: string; audioPcmChunks?: ArrayBuffer[]; audioSampleRate?: number; status?: string }) => {
  if (!message.audioPcmChunks || message.audioPcmChunks.length === 0) return;
  const rate = message.audioSampleRate || 24000;
  const ctx = ensurePcmContext(rate);
  if (pcmNextTime < ctx.currentTime + 0.05) {
    pcmNextTime = ctx.currentTime + 0.05;
  }
  while (pcmConsumed < message.audioPcmChunks.length) {
    const chunk = message.audioPcmChunks[pcmConsumed];
    const buffer = pcmChunkToBuffer(chunk, rate);
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.start(pcmNextTime);
    pcmNextTime += buffer.duration;
    pcmScheduledUntil = pcmNextTime;
    pcmSources.push(source);
    pcmConsumed += 1;
  }

  if (message.status === "done" && pcmConsumed >= message.audioPcmChunks.length) {
    if (pcmEndTimer) {
      clearTimeout(pcmEndTimer);
    }
    const remainingMs = Math.max(0, (pcmScheduledUntil - ctx.currentTime) * 1000);
    pcmEndTimer = window.setTimeout(() => {
      playingId.value = null;
      stopPcmPlayback();
    }, remainingMs + 30);
  }
};

const activePcmMessage = computed(() =>
  chatStore.messages.find((msg) => msg.id === pcmPlayingId.value)
);

watch(
  () => activePcmMessage.value?.audioPcmChunks?.length,
  () => {
    if (activePcmMessage.value && pcmPlayingId.value) {
      schedulePcmChunks(activePcmMessage.value);
    }
  }
);

watch(
  () => activePcmMessage.value?.status,
  () => {
    if (activePcmMessage.value && pcmPlayingId.value) {
      schedulePcmChunks(activePcmMessage.value);
    }
  }
);

const normalizeAudioUrl = (url: string) => {
  if (!url) return "";
  if (url.startsWith("http") || url.startsWith("blob:") || url.startsWith("data:")) {
    return url;
  }
  if (url.startsWith("/api/")) {
    return url;
  }
  const base = import.meta.env.VITE_API_BASE || "/api";
  if (url.startsWith("/conversation/")) {
    return `${base}${url}`;
  }
  return url;
};

const mapMessages = (items: SessionMessage[]) =>
  items.map((item, index) => ({
    id: item.id || `${activeSessionId.value}-${index}`,
    role: (item.role === 0 ? "user" : "assistant") as "user" | "assistant",
    content: item.content || "",
    status: "done" as const,
    audioUrl: item.audioUrl || item.audio_url || null
  }));

async function submit() {
  if (!input.value.trim() || chatStore.loading || !activeSessionId.value) return;
  const message = input.value;
  const currentSessionId = activeSessionId.value;
  input.value = "";
  try {
    await chatStore.sendMessage(message);
    await loadSessions();
    activeSessionId.value = currentSessionId;
  } catch (error) {
    console.error("Failed to send message:", error);
  }
}

const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value;
};

const getAudioSrc = async (audioUrl: string): Promise<string | null> => {
  if (!audioUrl) return null;
  
  if (audioUrl.startsWith("blob:")) {
    return audioUrl;
  }
  
  if (audioUrl.startsWith("data:") || audioUrl.startsWith("http")) {
    return audioUrl;
  }
  
  if (audioUrl.startsWith("/api/conversation/audio/")) {
    try {
      const token = getToken();
      const resp = await fetch(audioUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (!resp.ok) {
        console.error("鑾峰彇闊抽 URL 澶辫触:", resp.status);
        return null;
      }
      const body = await resp.json();
      return body?.url || body?.signed_url || body?.ref_url || null;
    } catch (e) {
      console.error("鑾峰彇闊抽 URL 閿欒:", e);
      return null;
    }
  }
  
  return normalizeAudioUrl(audioUrl);
};

const toggleAudio = async (message: {
  id: string;
  audioUrl?: string | null;
  audioPcmChunks?: ArrayBuffer[];
  audioSampleRate?: number;
  status?: string;
}) => {
  const cacheKey = message.audioUrl || "";
  const hasPcm = message.audioPcmChunks && message.audioPcmChunks.length > 0;
  const hasUrl = !!cacheKey;
  if (!hasPcm && !hasUrl) return;

  const preferPcm = hasPcm && message.status !== "done";

  // --- Stop Current Playback ---
  if (playingId.value === message.id) {
    if (audioPlayer) {
      audioPlayer.pause();
    }
    stopPcmPlayback();
    playingId.value = null;
    return;
  }
  if (audioPlayer) {
    audioPlayer.pause();
  }
  stopPcmPlayback();
  playingId.value = message.id;

  // --- Handle PCM Streaming ---
  if (preferPcm || !hasUrl) {
    pcmPlayingId.value = message.id;
    pcmConsumed = 0;
    pcmNextTime = 0;
    schedulePcmChunks(message);
    return;
  }

  // --- Caching and URL Playback Logic ---
  if (!audioPlayer) {
    audioPlayer = new Audio();
    audioPlayer.onended = () => {
      playingId.value = null;
    };
    audioPlayer.onerror = () => {
      console.error("Audio player error:", {
        src: audioPlayer?.src,
        code: audioPlayer?.error?.code,
        message: audioPlayer?.error?.message
      });
      playingId.value = null;
    };
  }
  const player = audioPlayer;
  player.pause();
  player.currentTime = 0;

  const playFromSrc = (src: string) => {
    player.src = src;
    player.play().catch((e) => {
      console.error("Audio play failed:", { error: e, src });
      playingId.value = null;
    });
  };

  // 1. Check session cache for blob URL
  if (blobUrlCache.has(cacheKey)) {
    const blobUrl = blobUrlCache.get(cacheKey)!;
    playFromSrc(blobUrl);
    return;
  }

  // 2. Check persistent cache for blob
  const cachedBlob = await audioCache.get(cacheKey);
  if (cachedBlob) {
    const blobUrl = URL.createObjectURL(cachedBlob);
    blobUrlCache.set(cacheKey, blobUrl);
    playFromSrc(blobUrl);
    return;
  }

  // 3. Fetch from network, cache, and play
  const ossUrl = await getAudioSrc(cacheKey);
  if (!ossUrl) {
    playingId.value = null;
    return;
  }

  try {
    const audioBlob = await fetch(ossUrl).then((res) => {
      if (!res.ok) throw new Error(`Failed to fetch audio: ${res.status}`);
      return res.blob();
    });
    await audioCache.set(cacheKey, audioBlob);
    const blobUrl = URL.createObjectURL(audioBlob);
    blobUrlCache.set(cacheKey, blobUrl);
    playFromSrc(blobUrl);
  } catch (e) {
    console.error("Failed to fetch or cache audio, playing from source directly:", e);
    // Fallback: play directly from the OSS URL if caching fails
    playFromSrc(ossUrl);
  }
};

const loadSessions = async () => {
  loadingSessions.value = true;
  try {
    if (!userStore.profile?.userId) {
      await userStore.fetchCurrent();
    }
    const userId = userStore.profile?.userId;
    if (!userId) return;
    const result = await listSessions(userId);
    sessions.value = result.data || [];
  } finally {
    loadingSessions.value = false;
  }
};

const selectSession = async (session: ConversationSession) => {
  const sessionId = session.conversationId || session.id;
  console.log("閫変腑浼氳瘽ID:", sessionId, session);
  if (!sessionId) {
    console.error("浼氳瘽ID涓嶅瓨鍦?", session);
    return;
  }
  activeSessionId.value = sessionId;
  activeSessionTitle.value = session.sessionTitle || t("sessions.untitled");
  chatStore.setSession(sessionId);
  try {
    const result = await listSessionMessages(sessionId);
    console.log("API杩斿洖鏁版嵁:", result);
    const history = mapMessages(result.data || []);
    console.log("娑堟伅鍘嗗彶:", history);
    chatStore.setMessages(history);
  } catch (error) {
    console.error("鍔犺浇鑱婂ぉ璁板綍澶辫触:", error);
  }
};

const createNewSession = async () => {
  const result = await createSession();
  const id = result?.data?.conversationId || result?.data?.sessionId || result?.data?.id;
  if (!id) return;
  await loadSessions();
  const session = sessions.value.find((item) => (item.conversationId || item.id) === id);
  if (session) {
    await selectSession(session);
  } else {
    activeSessionId.value = id;
    activeSessionTitle.value = t("sessions.untitled");
    chatStore.setSession(id);
  }
};

const applyRouteSessionSelection = async () => {
  const sessionId = typeof route.query.sessionId === "string" ? route.query.sessionId : "";
  if (!sessionId || !sessions.value.length) return;
  const target = sessions.value.find((item) => (item.conversationId || item.id) === sessionId);
  if (target) {
    await selectSession(target);
  }
};

onMounted(async () => {
  await loadSessions();
  await applyRouteSessionSelection();
});

watch(
  () => route.query.sessionId,
  async () => {
    await applyRouteSessionSelection();
  }
);

onBeforeUnmount(() => {
  if (audioPlayer) {
    audioPlayer.pause();
    audioPlayer = null;
  }
  stopPcmPlayback();
  blobUrlCache.forEach((url) => URL.revokeObjectURL(url));
  blobUrlCache.clear();
});
</script>

<style scoped>
.chat-page {
  display: flex;
  height: min(860px, calc(100vh - 48px));
  min-height: 560px;
  border-radius: 18px;
  border: 1px solid rgba(239, 227, 215, 0.8);
  box-shadow: var(--shadow-soft);
  overflow: hidden;
  background: rgba(255, 255, 255, 0.72);
}

/* 宸︿晶鑱旂郴浜轰晶杈规爮 */
.contact-sidebar {
  width: 300px;
  background: rgba(255, 255, 255, 0.68);
  border-right: 1px solid rgba(239, 227, 215, 0.8);
  backdrop-filter: blur(8px);
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width var(--duration-medium) var(--ease-standard);
  flex-shrink: 0;
}

.contact-sidebar.collapsed {
  width: 72px;
}

.contact-sidebar.collapsed .sidebar-header,
.contact-sidebar.collapsed .sidebar-list {
  opacity: 0;
  pointer-events: none;
}

/* 鎶樺彔鎸夐挳 - 濮嬬粓鍨傜洿灞呬腑 */
.collapse-btn {
  position: absolute;
  top: 50%;
  right: -16px;
  transform: translateY(-50%);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid rgba(239, 227, 215, 0.8);
  background: rgba(255, 255, 255, 0.96);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(45, 36, 32, 0.12);
  z-index: 10;
  color: var(--color-muted);
  transition: all 0.3s ease;
}

.collapse-btn:hover {
  background: var(--color-surface);
  transform: translateY(-50%) scale(1.1);
}

.contact-sidebar.collapsed .collapse-btn {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
  color: white;
  border-color: transparent;
}

.sidebar-header {
  padding: 16px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(239, 227, 215, 0.6);
  flex-shrink: 0;
}

.sidebar-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--text-sm);
  letter-spacing: 0.1em;
  color: var(--color-muted-soft);
  text-transform: uppercase;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
}

.new-session {
  border: none;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
  color: white;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease;
  white-space: nowrap;
}

.new-session:hover {
  transform: scale(1.05);
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  border: none;
  background: rgba(255, 249, 242, 0.74);
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-fast) var(--ease-standard);
}

.session-item:hover {
  background: rgba(255, 249, 242, 0.96);
  transform: translateX(2px);
}

.session-item.active {
  background: linear-gradient(135deg, var(--color-surface) 0%, rgba(255, 241, 227, 0.96) 100%);
  border: 1px solid rgba(251, 146, 60, 0.4);
  box-shadow: inset 0 0 0 1px rgba(251, 146, 60, 0.12);
}

.session-item.active .session-title {
  color: var(--color-primary-strong);
  font-weight: 700;
}

.session-item.active .session-icon-wrapper {
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
  color: white;
}

.session-icon-wrapper {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-muted);
  flex-shrink: 0;
}

.session-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.session-title {
  font-size: 15px;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.45;
}

.session-meta {
  font-size: 12px;
  color: var(--color-muted-soft);
}

.sidebar-empty {
  font-size: var(--text-sm);
  color: var(--color-muted-soft);
  text-align: center;
  padding: 30px;
}

/* 鍙充晶涓诲尯鍩?*/
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 252, 245, 0.97));
  position: relative;
}

/* 绌虹姸鎬?*/
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 20px;
}

.empty-heart {
  width: 100px;
  height: 100px;
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 24px 60px rgba(253, 186, 116, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  margin-bottom: 24px;
  transform: rotate(6deg);
  animation: heart-beat 3s ease-in-out infinite;
}

@keyframes heart-beat {
  0%, 100% { transform: rotate(6deg) scale(1); }
  50% { transform: rotate(6deg) scale(1.05); }
}

.empty-title {
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 12px;
  line-height: var(--lh-tight);
}

.empty-subtitle {
  font-size: 15px;
  color: var(--color-muted-soft);
  line-height: var(--lh-copy);
  max-width: 38ch;
}

/* 娑堟伅鍖哄煙 */
.message-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 22px 26px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-bubble {
  padding: 16px 20px;
  border-radius: 20px;
  max-width: min(70%, 700px);
  font-size: 15px;
  line-height: var(--lh-copy);
  box-shadow: 0 6px 16px rgba(77, 48, 20, 0.07);
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.message-bubble.has-audio {
  cursor: pointer;
}

.message-bubble.has-audio:hover {
  opacity: 0.95;
}

.bubble-content {
  flex: 1;
  min-width: 0;
}

.bubble-content p {
  margin: 0;
}

.bubble-footer {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.assistant .message-bubble {
  background: linear-gradient(135deg, rgba(255, 248, 238, 0.98), rgba(255, 252, 246, 0.96));
  border: 1px solid rgba(253, 186, 116, 0.34);
  color: var(--color-text);
}

.user .message-bubble {
  background: linear-gradient(135deg, #f5b370, #e88945);
  color: #2f1f13;
  border: 1px solid rgba(214, 125, 62, 0.65);
}

.heart-icon {
  color: rgba(253, 186, 116, 0.6);
  flex-shrink: 0;
  margin-left: 2px;
}

.volume-icon {
  display: flex;
  align-items: center;
  color: var(--color-primary);
}

.playing-icon {
  display: flex;
  align-items: flex-end;
  gap: 1px;
  height: 10px;
}

.voice-bar {
  width: 2px;
  background: currentColor;
  border-radius: 1px;
  animation: voice-bar 0.6s ease-in-out infinite;
}

.voice-bar:nth-child(1) {
  height: 4px;
  animation-delay: 0s;
}

.voice-bar:nth-child(2) {
  height: 8px;
  animation-delay: 0.1s;
}

.voice-bar:nth-child(3) {
  height: 6px;
  animation-delay: 0.2s;
}

@keyframes voice-bar {
  0%, 100% {
    transform: scaleY(0.5);
  }
  50% {
    transform: scaleY(1);
  }
}

/* 杈撳叆鍖?*/
.input-area {
  padding: 14px 18px;
  background: rgba(255, 255, 255, 0.86);
  border-top: 1px solid rgba(239, 227, 215, 0.6);
  backdrop-filter: blur(8px);
}

.input-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-input {
  flex: 1;
  border: 1px solid rgba(239, 227, 215, 0.8);
  border-radius: 24px;
  padding: 13px 18px;
  font-size: 15px;
  background: rgba(255, 255, 255, 0.95);
  outline: none;
  transition: border-color var(--duration-fast) var(--ease-standard),
    box-shadow var(--duration-fast) var(--ease-standard);
}

.chat-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.16);
}

.mic-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid rgba(239, 227, 215, 0.8);
  background: rgba(255, 255, 255, 0.9);
  color: var(--color-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-standard);
  flex-shrink: 0;
}

.mic-btn:hover {
  background: var(--color-surface);
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.send-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-strong) 100%);
  color: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-standard);
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(229, 139, 58, 0.35);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .chat-page {
    height: calc(100vh - 24px);
    min-height: 0;
    border-radius: 14px;
  }

  .contact-sidebar {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 20;
    box-shadow: 8px 0 30px rgba(45, 36, 32, 0.15);
  }

  .contact-sidebar.collapsed {
    width: 0;
    padding: 0;
    overflow: hidden;
  }

  .message-bubble {
    max-width: 90%;
    border-radius: 18px;
    padding: 14px 16px;
  }

  .message-list {
    padding: 16px 14px;
    gap: 12px;
  }

  .input-area {
    padding: 12px;
  }

  .input-row {
    gap: 8px;
  }

  .chat-input {
    padding: 12px 14px;
    font-size: 14px;
  }

  .mic-btn,
  .send-btn {
    width: 40px;
    height: 40px;
  }
}
</style>

