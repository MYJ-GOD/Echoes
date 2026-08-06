import { defineStore } from "pinia";
import { clearToken, getToken, setToken } from "../utils/token";
import * as authApi from "../services/modules/auth.api";

interface UserState {
  token: string | null;
  profile: authApi.UserLoginVO | null;
  loading: boolean;
}

export const useUserStore = defineStore("user", {
  state: (): UserState => ({
    token: getToken(),
    profile: null,
    loading: false
  }),
  actions: {
    async login(payload: authApi.LoginPayload) {
      this.loading = true;
      try {
        const { data } = await authApi.login(payload);
        const token = data.data?.token;
        if (token) {
          this.token = token;
          setToken(token);
          this.profile = data.data || null;
          if (!this.profile?.userId) {
            await this.fetchCurrent();
          }
        }
        return data;
      } catch (error: any) {
        return {
          code: error?.response?.data?.code ?? -1,
          message: error?.response?.data?.message ?? error?.message ?? "Login failed",
          data: null
        };
      } finally {
        this.loading = false;
      }
    },
    async register(payload: authApi.RegisterPayload) {
      this.loading = true;
      try {
        const { data } = await authApi.register(payload);
        const token = data.data?.token;
        if (token) {
          this.token = token;
          setToken(token);
          this.profile = data.data || null;
          if (!this.profile?.userId) {
            await this.fetchCurrent();
          }
        }
        return data;
      } catch (error: any) {
        return {
          code: error?.response?.data?.code ?? -1,
          message: error?.response?.data?.message ?? error?.message ?? "Register failed",
          data: null
        };
      } finally {
        this.loading = false;
      }
    },
    async fetchCurrent() {
      if (!this.token) return null;
      const { data } = await authApi.fetchCurrentUser();
      this.profile = data.data || null;
      return data;
    },
    async logout() {
      try {
        await authApi.logout();
      } finally {
        this.token = null;
        this.profile = null;
        clearToken();
      }
    }
  }
});
