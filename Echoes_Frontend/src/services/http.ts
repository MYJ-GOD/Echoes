import axios from "axios";
import { getToken } from "../utils/token";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "/api",
  timeout: 20000
});

http.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default http;
