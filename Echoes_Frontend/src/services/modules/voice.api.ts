/**
 * 闊宠壊鏈嶅姟 API
 * 绠＄悊闊宠壊璧勪骇銆佽缁冧换鍔°€佸垎浜巿鏉?
 */

import http from "../http";
import { getToken } from "../../utils/token";
import type { ApiResult, PageResult } from "../../types/api";

const BASE = import.meta.env.VITE_API_BASE || "";

// ==================== 绫诲瀷瀹氫箟 ====================

/** 闊宠壊璧勪骇鐘舵€?*/
export type VoiceAssetStatus = "PENDING" | "PROCESSING" | "READY" | "FAILED";

/** 鏉冮檺绫诲瀷 */
export type GrantPermission = "USE" | "FULL";

/** 闊宠壊璧勪骇 */
export interface VoiceAsset {
  voiceAssetId: string;
  ownerUserId: string;
  name: string;
  description?: string;
  refId: string;
  status: VoiceAssetStatus;
  isDefault: boolean;
  createTime: string;
  updateTime: string;
  voiceIdExternal?: string;
  similarityScore?: number;
  voiceModelId?: string;
}

/** 闊宠壊璧勪骇璇︽儏 (鎵╁睍) */
export interface VoiceAssetDetail extends VoiceAsset {
  progress?: number;
  similarityScore?: number;
  voiceModelId?: string;
  tasks?: TrainingTask[];
}

/** 鍒涘缓闊宠壊璇锋眰 */
export interface CreateVoiceAssetRequest {
  refId: string;
  name: string;
  role?: string;
  tags?: string[];
  setAsDefault?: boolean;
  description?: string;
  prompt?: string;
}

/** 鏇存柊闊宠壊璇锋眰 */
export interface UpdateVoiceAssetRequest {
  name?: string;
  description?: string;
}

/** 璁粌浠诲姟 */
export interface TrainingTask {
  taskId: string;
  voiceAssetId: string;
  voiceAssetName?: string;
  status: "PENDING" | "TRAINING" | "COMPLETED" | "FAILED" | "CANCELLED";
  progress: number;
  similarityScore?: number;
  startTime?: string;
  endTime?: string;
  errorMessage?: string;
  retryCount?: number;
}

/** 鍒嗕韩鎺堟潈 */
export interface VoiceGrant {
  grantId: string;
  voiceAssetId: string;
  grantorUserId: string;
  granteeUserId: string;
  permission: GrantPermission;
  expiresAt?: string;
  createTime: string;
}

/** 鍒涘缓鍒嗕韩璇锋眰 */
export interface CreateGrantRequest {
  voiceAssetId: string;
  granteeUserId: string;
  permission: GrantPermission;
  expiresAt?: string;
}

/** 鍒嗕韩璇︽儏 (甯﹁鎺堟潈浜轰俊鎭? */
export interface VoiceGrantDetail extends VoiceGrant {
  grantorName?: string;
  granteeName?: string;
  voiceAssetName?: string;
}

/** 鏀跺埌鐨勫垎浜?*/
export interface ReceivedGrant extends VoiceGrant {
  voiceAssetName?: string;
  grantorName?: string;
  voiceAsset?: VoiceAsset;
}

// ==================== 闊宠壊璧勪骇 API ====================

/**
 * 鑾峰彇鎴戠殑闊宠壊鍒楄〃
 */
export async function getMyVoices(): Promise<ApiResult<VoiceAsset[]>> {
  const response = await http.get<ApiResult<VoiceAsset[]>>(`/voice/assets`);
  return response.data;
}

/**
 * 鑾峰彇闊宠壊璇︽儏
 */
export async function getVoiceDetail(voiceAssetId: string): Promise<ApiResult<VoiceAssetDetail>> {
  const response = await http.get<ApiResult<VoiceAssetDetail>>(`/voice/assets/${voiceAssetId}`);
  return response.data;
}

/**
 * 鍒涘缓闊宠壊璧勪骇
 */
export async function createVoiceAsset(data: CreateVoiceAssetRequest): Promise<ApiResult<VoiceAsset>> {
  const response = await http.post<ApiResult<VoiceAsset>>(`/voice/assets`, data);
  return response.data;
}

/**
 * 鏇存柊闊宠壊
 */
export async function updateVoiceAsset(
  voiceAssetId: string,
  data: UpdateVoiceAssetRequest
): Promise<ApiResult<VoiceAsset>> {
  const response = await http.put<ApiResult<VoiceAsset>>(`/voice/assets/${voiceAssetId}`, data);
  return response.data;
}

/**
 * 鍒犻櫎闊宠壊
 */
export async function deleteVoiceAsset(voiceAssetId: string): Promise<ApiResult<void>> {
  const response = await http.delete<ApiResult<void>>(`/voice/assets/${voiceAssetId}`);
  return response.data;
}

/**
 * 璁剧疆榛樿闊宠壊
 */
export async function setDefaultVoice(voiceAssetId: string): Promise<ApiResult<void>> {
  const response = await http.put<ApiResult<void>>(`/voice/assets/${voiceAssetId}/default`);
  return response.data;
}

/**
 * 妫€鏌ユ槸鍚︽湁鏉冮檺璁块棶闊宠壊
 */
export async function checkVoicePermission(voiceAssetId: string): Promise<ApiResult<boolean>> {
  const response = await http.get<ApiResult<boolean>>(`/voice/assets/${voiceAssetId}/permission`);
  return response.data;
}

// ==================== 璁粌浠诲姟 API ====================

/**
 * 鑾峰彇璁粌浠诲姟鍒楄〃
 */
export async function getTrainingTasks(params?: {
  status?: string;
  pageNum?: number;
  pageSize?: number;
}): Promise<ApiResult<PageResult<TrainingTask>>> {
  const response = await http.get<ApiResult<PageResult<TrainingTask>>>(`/voice/training`, { params });
  return response.data;
}

/**
 * 鑾峰彇璁粌浠诲姟璇︽儏
 */
export async function getTrainingTaskDetail(taskId: string): Promise<ApiResult<TrainingTask>> {
  const response = await http.get<ApiResult<TrainingTask>>(`/voice/training/${taskId}`);
  return response.data;
}

/**
 * 鑾峰彇闊宠壊鍏宠仈鐨勮缁冧换鍔″垪琛?
 */
export async function getVoiceTrainingTasks(voiceAssetId: string): Promise<ApiResult<TrainingTask[]>> {
  const response = await http.get<ApiResult<TrainingTask[]>>(`/voice/training/asset/${voiceAssetId}`);
  return response.data;
}

/**
 * 鍙栨秷璁粌浠诲姟
 */
export async function cancelTrainingTask(taskId: string): Promise<ApiResult<void>> {
  const response = await http.post<ApiResult<void>>(`/voice/training/${taskId}/cancel`);
  return response.data;
}

/**
 * 鑾峰彇璁粌娴嬭瘯闊抽 URL
 */
export async function getTestAudioUrl(voiceModelId: string): Promise<string> {
  const response = await http.get(`/voice/training/model/${voiceModelId}/sample`, {
    responseType: "blob"
  });
  return URL.createObjectURL(response.data as Blob);
}

/**
 * 閲嶈瘯璁粌浠诲姟
 */
export async function retryTrainingTask(
  taskId: string,
  request?: {
    refId?: string;
    modelVersion?: number;
    prompt?: string;
  }
): Promise<ApiResult<TrainingTask>> {
  const response = await http.post<ApiResult<TrainingTask>>(
    `/voice/training/${taskId}/retry`,
    request
  );
  return response.data;
}

/**
 * 璁粌鐘舵€?SSE 浜嬩欢绫诲瀷
 */
export interface TrainingStatusEvent {
  taskId: string;
  status: "pending" | "training" | "success" | "failed" | "cancelled";
  progress: number;
  voiceAssetId?: string;
  voiceModelId?: string;
  similarityScore?: number;
  message?: string;
}

/**
 * 璁㈤槄璁粌鐘舵€?SSE 浜嬩欢娴?
 * @param taskId 浠诲姟ID
 * @param onMessage 娑堟伅鍥炶皟
 * @param onError 閿欒鍥炶皟
 * @returns EventSource 瀹炰緥
 */
export function subscribeTrainingStatus(
  taskId: string,
  onMessage: (event: TrainingStatusEvent) => void,
  onError?: (error: Event) => void
): EventSource {
  const token = getToken();
  // 灏?token 鏀惧湪 URL 鍙傛暟涓紙EventSource 涓嶆敮鎸佽嚜瀹氫箟 headers锛?
  const url = token
    ? `${BASE}/voice/training/stream/${taskId}?token=${encodeURIComponent(token)}`
    : `${BASE}/voice/training/stream/${taskId}`;
  const eventSource = new EventSource(url);

  const handleEvent = (raw: string) => {
    try {
      const data = JSON.parse(raw);
      onMessage(data);
    } catch (e) {
      onMessage({
        taskId,
        status: "training",
        progress: 0,
        message: raw,
      });
    }
  };

  eventSource.onmessage = (event) => {
    handleEvent(event.data);
  };

  eventSource.addEventListener("progress", (event: MessageEvent) => {
    handleEvent(event.data);
  });

  eventSource.addEventListener("status_change", (event: MessageEvent) => {
    handleEvent(event.data);
  });

  eventSource.addEventListener("connected", (event: MessageEvent) => {
    handleEvent(event.data);
  });

  eventSource.onerror = (error) => {
    console.error("SSE 杩炴帴閿欒:", error);
    onError?.(error);
  };

  return eventSource;
}

// ==================== 鍒嗕韩鎺堟潈 API ====================

/**
 * 鑾峰彇鎴戠粰鍑虹殑鍒嗕韩鍒楄〃
 */
export async function getGivenGrants(): Promise<ApiResult<VoiceGrantDetail[]>> {
  const response = await http.get<ApiResult<VoiceGrantDetail[]>>(`/voice/grants/given`);
  return response.data;
}

/**
 * 鑾峰彇鎴戞敹鍒扮殑鍒嗕韩鍒楄〃
 */
export async function getReceivedGrants(): Promise<ApiResult<ReceivedGrant[]>> {
  const response = await http.get<ApiResult<ReceivedGrant[]>>(`/voice/grants/received`);
  return response.data;
}

/**
 * 鍒涘缓鍒嗕韩鎺堟潈
 */
export async function createGrant(data: CreateGrantRequest): Promise<ApiResult<VoiceGrant>> {
  const response = await http.post<ApiResult<VoiceGrant>>(`/voice/grants`, data);
  return response.data;
}

/**
 * 鍙栨秷鍒嗕韩鎺堟潈
 */
export async function revokeGrant(grantId: string): Promise<ApiResult<void>> {
  const response = await http.delete<ApiResult<void>>(`/voice/grants/${grantId}`);
  return response.data;
}

/**
 * 鑾峰彇鍙敤鐨勯煶鑹插垪琛?(鑷繁鐨?+ 鏀跺埌鐨勫垎浜?
 */
export async function getAvailableVoices(): Promise<ApiResult<(VoiceAsset & { source: "OWN" | "SHARED" })[]>> {
  const response = await http.get<ApiResult<(VoiceAsset & { source: "OWN" | "SHARED" })[]>>(
    `/voice/assets/available`
  );
  return response.data;
}

