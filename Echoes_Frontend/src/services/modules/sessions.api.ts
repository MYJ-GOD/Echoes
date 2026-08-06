import http from "../http";
import type { ApiResult, PageResult } from "../../types/api";

export interface ConversationSession {
  id?: string;
  conversationId?: string;
  sessionTitle?: string;
  lastMessageTime?: string;
  messageCount?: number;
  voiceAssetId?: string;
}

export interface SessionMessage {
  id?: string;
  role?: number;
  content?: string;
  audioUrl?: string;
  audio_url?: string;
  messageIndex?: number;
}

export async function listSessions(userId: string) {
  const response = await http.get<ApiResult<ConversationSession[]>>(
    `/conversation-session/user/${userId}`
  );
  return response.data;
}

/**
 * 分页查询会话列表
 */
export async function listSessionsPaged(userId: string, page = 1, size = 20) {
  const response = await http.get<ApiResult<PageResult<ConversationSession>>>(
    `/conversation-session/user/${userId}/page`,
    { params: { page, size } }
  );
  return response.data;
}

/**
 * 更新会话标题
 */
export async function updateSessionTitle(conversationId: string, title: string) {
  const response = await http.put<ApiResult<boolean>>(
    `/conversation-session/${conversationId}/title`,
    null,
    { params: { title } }
  );
  return response.data;
}

/**
 * 删除会话（软删除）
 */
export async function deleteSession(conversationId: string) {
  const response = await http.delete<ApiResult<boolean>>(
    `/conversation-session/${conversationId}`
  );
  return response.data;
}

export async function listSessionMessages(conversationId: string, limit = 50) {
  const response = await http.get<ApiResult<SessionMessage[]>>(
    `/conversation-session/${conversationId}/messages`,
    { params: { limit } }
  );
  return response.data;
}

/**
 * 更新会话的默认音色
 */
export async function updateSessionVoiceAssetId(conversationId: string, voiceAssetId: string) {
  const response = await http.put<ApiResult<boolean>>(
    `/conversation-session/${conversationId}/voiceId`,
    null,
    { params: { voiceId: voiceAssetId } }
  );
  return response.data;
}
