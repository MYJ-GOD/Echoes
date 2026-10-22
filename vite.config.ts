import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Tauri 2 约定：固定端口 1420（strictPort），构建产物 dist/
export default defineConfig({
  plugins: [vue()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    target: "es2021",
  },
});
