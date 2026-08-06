import { defineStore } from "pinia";
import { streamChat, createSession } from "../services/modules/chat.api";

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  status?: "streaming" | "done" | "error";
  audioUrl?: string | null;
  audioFormat?: "wav" | "pcm16";
  audioSampleRate?: number;
  audioPcmChunks?: ArrayBuffer[];
}

interface ChatState {
  messages: ChatMessage[];
  sessionId: string | null;
  loading: boolean;
}

interface AudioChunkPayload {
  sample_rate?: number;
  mime?: string;
  format?: string;
  audio?: string;
}

function safeJsonParse(payload: string) {
  try {
    return JSON.parse(payload);
  } catch {
    return null;
  }
}

// Transient, non-reactive handle to the in-flight stream so it can be aborted
// on session switch or when a new message starts. Kept out of Pinia state to
// avoid wrapping the native AbortController in a reactive proxy.
let activeController: AbortController | null = null;

export const useChatStore = defineStore("chat", {
  state: (): ChatState => ({
    messages: [],
    sessionId: null,
    loading: false
  }),
  actions: {
    setSession(sessionId: string | null) {
      // Abort any in-flight stream before switching sessions
      activeController?.abort();
      activeController = null;
      this.sessionId = sessionId;
      this.messages = [];
    },
    setMessages(messages: ChatMessage[]) {
      this.messages = messages;
    },
    async ensureSession() {
      if (this.sessionId) return this.sessionId;
      const result = await createSession();
      const id = result?.data?.conversationId || result?.data?.sessionId;
      if (!id) {
        throw new Error("Session creation failed");
      }
      this.sessionId = id;
      return id;
    },
    async sendMessage(text: string) {
      if (!text.trim()) return;
      this.loading = true;
      const sessionId = await this.ensureSession();
      const turnId = crypto.randomUUID();

      const userMessage: ChatMessage = {
        id: `u-${turnId}`,
        role: "user",
        content: text,
        status: "done"
      };
      const assistantMessage: ChatMessage = {
        id: `a-${turnId}`,
        role: "assistant",
        content: "",
        status: "streaming"
      };

      this.messages.push(userMessage, assistantMessage);

      const pcmChunks: ArrayBuffer[] = [];
      let sampleRate: number | undefined;

      const base64ToArrayBuffer = (base64: string): ArrayBuffer => {
        const cleaned = base64.replace(/\s+/g, "");
        const binary = atob(cleaned);
        const len = binary.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i += 1) {
          bytes[i] = binary.charCodeAt(i);
        }
        return bytes.buffer;
      };

      const isWavHeader = (bytes: Uint8Array) =>
        bytes.length >= 12 &&
        bytes[0] === 0x52 &&
        bytes[1] === 0x49 &&
        bytes[2] === 0x46 &&
        bytes[3] === 0x46 &&
        bytes[8] === 0x57 &&
        bytes[9] === 0x41 &&
        bytes[10] === 0x56 &&
        bytes[11] === 0x45;

      const extractPcmFromWav = (bytes: Uint8Array) => {
        let dataOffset = -1;
        let dataSize = 0;
        for (let i = 12; i + 8 <= bytes.length; i += 1) {
          if (
            bytes[i] === 0x64 &&
            bytes[i + 1] === 0x61 &&
            bytes[i + 2] === 0x74 &&
            bytes[i + 3] === 0x61
          ) {
            dataOffset = i + 8;
            dataSize =
              bytes[i + 4] |
              (bytes[i + 5] << 8) |
              (bytes[i + 6] << 16) |
              (bytes[i + 7] << 24);
            break;
          }
        }
        const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
        const rate = bytes.length >= 28 ? view.getUint32(24, true) : 24000;
        if (dataOffset < 0) {
          return { pcm: bytes.slice(12).buffer, sampleRate: rate };
        }
        const end = Math.min(bytes.length, dataOffset + dataSize);
        return { pcm: bytes.slice(dataOffset, end).buffer, sampleRate: rate };
      };

      const buildWavBlob = (chunks: ArrayBuffer[], rate: number) => {
        const total = chunks.reduce((sum, c) => sum + c.byteLength, 0);
        const buffer = new ArrayBuffer(44 + total);
        const view = new DataView(buffer);
        const writeString = (offset: number, value: string) => {
          for (let i = 0; i < value.length; i += 1) {
            view.setUint8(offset + i, value.charCodeAt(i));
          }
        };
        writeString(0, "RIFF");
        view.setUint32(4, 36 + total, true);
        writeString(8, "WAVE");
        writeString(12, "fmt ");
        view.setUint32(16, 16, true);
        view.setUint16(20, 1, true);
        view.setUint16(22, 1, true);
        view.setUint32(24, rate, true);
        view.setUint32(28, rate * 2, true);
        view.setUint16(32, 2, true);
        view.setUint16(34, 16, true);
        writeString(36, "data");
        view.setUint32(40, total, true);
        let offset = 44;
        for (const chunk of chunks) {
          new Uint8Array(buffer, offset, chunk.byteLength).set(new Uint8Array(chunk));
          offset += chunk.byteLength;
        }
        return new Blob([buffer], { type: "audio/wav" });
      };

      // Abort a previous stream if the user sends before the last one finished
      activeController?.abort();

      try {
        for await (const raw of streamChat(
          {
            message: text,
            sessionId,
            turnId,
            idempotencyKey: turnId,
            stream: true
          },
          (ctrl) => {
            activeController = ctrl;
          }
        )) {
          const parsed = safeJsonParse(raw);
          if (!parsed) {
            continue;
          }
          const type = parsed.type as string | undefined;
          const data = parsed.data;

          if (type === "message.delta") {
            assistantMessage.content += (typeof data === "string" ? data : "") || "";
          } else if (type === "message.final") {
            if (typeof data === "string") {
              assistantMessage.content = data || assistantMessage.content;
            }
            assistantMessage.status = "done";
          } else if (type === "audio_chunk") {
            const payload = data as AudioChunkPayload;
            if (payload && typeof payload.audio === "string" && payload.audio) {
              try {
                const chunk = base64ToArrayBuffer(payload.audio);
                if (!sampleRate) {
                  sampleRate = payload.sample_rate || 24000;
                }
                const bytes = new Uint8Array(chunk);
                if (isWavHeader(bytes)) {
                  const extracted = extractPcmFromWav(bytes);
                  sampleRate = extracted.sampleRate || sampleRate;
                  pcmChunks.push(extracted.pcm);
                  assistantMessage.audioFormat = "pcm16";
                } else {
                  pcmChunks.push(chunk);
                  assistantMessage.audioFormat = "pcm16";
                }
                assistantMessage.audioSampleRate = sampleRate || 24000;
                assistantMessage.audioPcmChunks = pcmChunks;
              } catch {
                // Ignore a single chunk parse failure.
              }
            }
          } else if (type === "error") {
            assistantMessage.status = "error";
          }
        }

        if (pcmChunks.length > 0) {
          const blob = buildWavBlob(pcmChunks, sampleRate || 24000);
          assistantMessage.audioUrl = URL.createObjectURL(blob);
          assistantMessage.audioFormat = "wav";
          console.log("Audio blob created:", {
            size: blob.size,
            type: blob.type,
            chunks: pcmChunks.length
          });
        }

        if (assistantMessage.status === "streaming") {
          assistantMessage.status = "done";
        }
      } catch {
        assistantMessage.status = "error";
      } finally {
        this.loading = false;
      }
    }
  }
});
