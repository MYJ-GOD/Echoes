/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_PROXY_TARGET || "http://localhost:18080";

  return {
    plugins: [vue()],
    server: {
      host: true,
      port: 5173,
      proxy: {
        "/api": { target, changeOrigin: true }
      }
    },
    test: {
      environment: "node",
      include: ["src/**/*.{test,spec}.ts"],
      globals: true
    }
  };
});
