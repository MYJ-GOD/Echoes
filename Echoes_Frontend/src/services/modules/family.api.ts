/**
 * 家庭服务 API
 * 管理家庭创建、成员管理、家庭关系查询
 */

import { getToken } from "../../utils/token";

const BASE = import.meta.env.VITE_API_BASE || "";

// ==================== 类型定义 ====================

/** 家庭角色 */
export type FamilyRole = "PARENT" | "CHILD" | "CAREGIVER" | "OTHER";

/** 家庭 */
export interface Family {
  familyId: string;
  ownerUserId: string;
  name: string;
  isDeleted: boolean;
  createTime: string;
  updateTime: string;
}

/** 家庭成员 */
export interface FamilyMember {
  id: string;
  familyId: string;
  userId: string;
  role: FamilyRole;
  createTime: string;
}

/** 家庭成员详情 (带用户信息) */
export interface FamilyMemberDetail extends FamilyMember {
  userName?: string;
  userPhone?: string;
}

/** 家庭详情 (带成员列表) */
export interface FamilyDetail extends Family {
  members: FamilyMemberDetail[];
  memberCount: number;
}

/** 创建家庭请求 */
export interface CreateFamilyRequest {
  name: string;
}

/** 添加成员请求 */
export interface AddMemberRequest {
  userId: string;
  role: FamilyRole;
}

/** 更新家庭名称请求 */
export interface UpdateFamilyNameRequest {
  name: string;
}

/** 检查家庭关系响应 */
export interface FamilyRelationResponse {
  inSameFamily: boolean;
  commonFamilyId?: string;
}

/** API 响应 */
export interface ApiResult<T> {
  code?: number;
  message?: string;
  data?: T;
}

// ==================== 家庭 API ====================

/**
 * 获取我的家庭列表
 */
export async function getMyFamilies(): Promise<ApiResult<Family[]>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family/my`, {
    method: "GET",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(`获取家庭列表失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 获取家庭详情
 */
export async function getFamilyDetail(familyId: string): Promise<ApiResult<FamilyDetail>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family/${familyId}`, {
    method: "GET",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(`获取家庭详情失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 创建家庭
 */
export async function createFamily(data: CreateFamilyRequest): Promise<ApiResult<Family>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family`, {
    method: "POST",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error(`创建家庭失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 更新家庭名称
 */
export async function updateFamilyName(familyId: string, name: string): Promise<ApiResult<void>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family/${familyId}/name`, {
    method: "PUT",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    throw new Error(`更新家庭名称失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 解散家庭
 */
export async function dissolveFamily(familyId: string): Promise<ApiResult<void>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family/${familyId}`, {
    method: "DELETE",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(`解散家庭失败: ${response.status}`);
  }
  return response.json();
}

// ==================== 家庭成员 API ====================

/**
 * 获取家庭成员列表
 */
export async function getFamilyMembers(familyId: string): Promise<ApiResult<FamilyMemberDetail[]>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family/${familyId}/members`, {
    method: "GET",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(`获取家庭成员列表失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 添加家庭成员
 */
export async function addFamilyMember(familyId: string, data: AddMemberRequest): Promise<ApiResult<FamilyMember>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family/${familyId}/members`, {
    method: "POST",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error(`添加家庭成员失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 移除家庭成员
 */
export async function removeFamilyMember(familyId: string, userId: string): Promise<ApiResult<void>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family/${familyId}/members/${userId}`, {
    method: "DELETE",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(`移除家庭成员失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 更新家庭成员角色
 */
export async function updateMemberRole(
  familyId: string,
  userId: string,
  role: FamilyRole
): Promise<ApiResult<void>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family/${familyId}/members/${userId}/role`, {
    method: "PUT",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ role }),
  });
  if (!response.ok) {
    throw new Error(`更新成员角色失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 检查用户是否在家庭中 (供其他服务调用)
 */
export async function checkFamilyMember(familyId: string, userId: string): Promise<ApiResult<boolean>> {
  const token = getToken();
  const response = await fetch(`${BASE}/family/${familyId}/members/${userId}/check`, {
    method: "GET",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(`检查家庭成员失败: ${response.status}`);
  }
  return response.json();
}

// ==================== 家庭关系 API ====================

/**
 * 检查两个用户是否在同一家庭
 */
export async function checkFamilyRelation(userId1: string, userId2: string): Promise<ApiResult<FamilyRelationResponse>> {
  const token = getToken();
  const query = new URLSearchParams({
    userId1,
    userId2,
  });
  const response = await fetch(`${BASE}/family/check-relation?${query}`, {
    method: "GET",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(`检查家庭关系失败: ${response.status}`);
  }
  return response.json();
}

/**
 * 搜索用户 (用于添加家庭成员)
 */
export async function searchUsers(keyword: string): Promise<ApiResult<{ userId: string; name: string; phone?: string }[]>> {
  const token = getToken();
  const response = await fetch(`${BASE}/user/search?keyword=${encodeURIComponent(keyword)}`, {
    method: "GET",
    headers: {
      Authorization: token ? `Bearer ${token}` : "",
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    throw new Error(`搜索用户失败: ${response.status}`);
  }
  return response.json();
}

