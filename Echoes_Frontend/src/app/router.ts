import { createRouter, createWebHistory } from "vue-router";
import { useUserStore } from "../store/user";
import MainLayout from "../components/MainLayout.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/auth/login", name: "login", component: () => import("../pages/auth/LoginPage.vue"), meta: { showLayout: false } },
    { path: "/auth/register", name: "register", component: () => import("../pages/auth/RegisterPage.vue"), meta: { showLayout: false } },
    {
      path: "/",
      component: MainLayout,
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "/home" },
        { path: "home", name: "home", component: () => import("../pages/home/HomePage.vue") },
        { path: "chat", name: "chat", component: () => import("../pages/chat/ChatPage.vue") },
        { path: "sessions", name: "sessions", component: () => import("../pages/sessions/SessionsPage.vue") },
        { path: "profile", name: "profile", component: () => import("../pages/profile/ProfilePage.vue") },
        { path: "voices", name: "voices", component: () => import("../pages/voices/VoicesPage.vue") },
        { path: "voices/create", name: "create-voice", component: () => import("../pages/voices/CreateVoicePage.vue") },
        { path: "voices/:id", name: "voice-detail", component: () => import("../pages/voices/VoiceDetailPage.vue") },
        { path: "voices/:id/edit", name: "edit-voice", component: () => import("../pages/voices/EditVoicePage.vue") },
        { path: "voices/:id/retry", name: "retry-voice", component: () => import("../pages/voices/RetryVoicePage.vue") },
        { path: "families", name: "families", component: () => import("../pages/families/FamiliesPage.vue") },
        { path: "families/create", name: "create-family", component: () => import("../pages/families/CreateFamilyPage.vue") },
        { path: "families/:id", name: "family-detail", component: () => import("../pages/families/FamilyDetailPage.vue") },
        { path: "families/:id/settings", name: "family-settings", component: () => import("../pages/families/FamilySettingsPage.vue") }
      ]
    }
  ]
});

router.beforeEach(async (to, from, next) => {
  if (to.meta.showLayout === false) {
    const userStore = useUserStore();
    if (to.name === "login" && userStore.token && userStore.profile) {
      return next({ name: "home" });
    }
    return next();
  }

  const userStore = useUserStore();

  if (userStore.token && !userStore.profile) {
    try {
      await userStore.fetchCurrent();
    } catch {
      userStore.logout();
      return next({ name: "login", query: { redirect: to.fullPath } });
    }
  }

  if (userStore.token && userStore.profile) {
    return next();
  }

  return next({ name: "login", query: { redirect: to.fullPath } });
});

export default router;
