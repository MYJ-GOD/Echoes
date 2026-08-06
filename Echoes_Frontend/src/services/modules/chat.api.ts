import { streamSSE } from "../sse";
import { getToken } from "../../utils/token";

export interface ChatRequest {
  message: string;
  sessionId: string;
  turnId: string;
  idempotencyKey?: string;
  stream?: boolean;
}

export async function* streamChat(
  payload: ChatRequest,
  onController?: (ctrl: AbortController) => void
) {
  const controller = new AbortController();
  onController?.(controller);

  const base = import.meta.env.VITE_API_BASE || "";
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  yield* streamSSE(
    `${base}/conversation/chat-stream`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({ ...payload, stream: true })
    },
    controller.signal
  );
}

export async function createSession(title?: string) {
  const base = import.meta.env.VITE_API_BASE || "";
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  const query = title ? `?title=${encodeURIComponent(title)}` : "";
  const response = await fetch(`${base}/conversation-session${query}`, {
    method: "POST",
    headers
  });
  if (!response.ok) {
    throw new Error(`Create session failed: ${response.status}`);
  }
  return response.json();
}
