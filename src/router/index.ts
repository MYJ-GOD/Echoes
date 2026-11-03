import { createRouter, createWebHashHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";

import AboutPage from "../pages/AboutPage.vue";
import ChatPage from "../pages/ChatPage.vue";
import HistoryPage from "../pages/HistoryPage.vue";
import Hud from "../pages/Hud.vue";
import MemoryPage from "../pages/MemoryPage.vue";
import SettingsWindow from "../components/settings/SettingsWindow.vue";
import VoicePage from "../pages/VoicePage.vue";

/**
 * D2：五页 + 独立设置窗口。
 *
 * - 主窗口：对话 / 历史 / 记忆 / 声音 / 关于，统一由 AppShell 提供标题栏与侧栏。
 * - `/settings`：独立窗口创建失败时的整页回退；成功时由壳打开 720×760 的设置窗口。
 * - `/hud`：悬浮条，保留全屏自绘。
 * - `/design`：仅开发态的设计系统沙盒。
 */
const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "chat",
    component: ChatPage,
  },
  {
    path: "/history",
    name: "history",
    component: HistoryPage,
  },
  {
    path: "/memory",
    name: "memory",
    component: MemoryPage,
  },
  {
    path: "/voice",
    name: "voice",
    component: VoicePage,
  },
  {
    path: "/about",
    name: "about",
    component: AboutPage,
  },
  {
    path: "/settings",
    name: "settings",
    component: SettingsWindow,
    // 独立设置窗口（Tauri `index.html#/settings`）inline=false → 关闭时走 ipc.closeWindow()；
    // 主窗口回退（`#/settings?inline=1`）inline=true → 关闭时 router.push("/") 返回对话。
    props: (route) => ({ inline: route.query.inline === "1" }),
  },
  {
    path: "/hud",
    name: "hud",
    component: Hud,
  },
  // 兜底：任何没匹配上的 hash（旧链接、手改的地址）都回对话页，
  // 否则 RouterView 渲染空内容 = 白屏。
  {
    path: "/:pathMatch(.*)*",
    redirect: "/",
  },
];

if (import.meta.env.DEV) {
  routes.push({
    path: "/design",
    name: "design",
    component: () => import("../pages/Design.vue"),
  });
}

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

export default router;
