import http from "../http";
import type { ApiResult } from "../../types/api";

export interface LoginPayload {
  phoneNumber: string;
}

export interface RegisterPayload {
  name: string;
  phoneNumber: string;
  email?: string;
  userType?: string;
}

export interface UserLoginVO {
  token: string;
  userId?: string;
  name?: string;
  phoneNumber?: string;
  userType?: string;
}

export function login(payload: LoginPayload) {
  return http.post<ApiResult<UserLoginVO>>("/user/auth/login", payload);
}

export function register(payload: RegisterPayload) {
  return http.post<ApiResult<UserLoginVO>>("/user/auth/register", payload);
}

export function fetchCurrentUser() {
  return http.get<ApiResult<UserLoginVO>>("/user/auth/current");
}

export function logout() {
  return http.post<ApiResult<void>>("/user/auth/logout");
}
