import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Tauri 2 约定：固定端口 1420（strictPort），构建产物 dist/
export default defineConfig({
  plugins: [vue()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    // 只盯前端源码：仓库根还有 src-tauri/target(1.4w)、tmp(3w)、sidecar(4w)、
    // .venv(1.3w) 共十万级文件，全量 watch 会让依赖扫描/首屏等到分钟级（白屏）。
    watch: {
      ignored: [
        "**/src-tauri/**",
        "**/sidecar/**",
        "**/tmp/**",
        "**/.venv/**",
        "**/docs/**",
        "**/models/**",
        "**/.workbuddy/**",
        "**/*.pyc",
      ],
    },
  },
  build: {
    outDir: "dist",
    target: "es2021",
  },
});
