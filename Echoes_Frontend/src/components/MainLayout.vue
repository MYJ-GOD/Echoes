<template>
  <div class="main-layout" :class="{ collapsed: isCollapsed }">
    
    <aside class="sidebar">
      <div class="sidebar-inner">
        
        <div class="sidebar-brand">
          <router-link to="/home" class="brand-link">
            <svg class="brand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="22"/>
            </svg>
            <span class="brand-name">{{ t("nav.brand") }}</span>
          </router-link>
        </div>

        
        <nav class="sidebar-nav">
          <router-link
            v-for="item in mainNavItems"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
          >
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <component :is="item.icon" />
            </svg>
            <span class="nav-label">{{ item.label }}</span>
          </router-link>

          <div class="nav-divider"></div>

          <router-link
            v-for="item in secondaryNavItems"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
          >
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <component :is="item.icon" />
            </svg>
            <span class="nav-label">{{ item.label }}</span>
          </router-link>
        </nav>

        
        <div class="sidebar-footer">
          <div class="user-card" @click="showUserMenu = !showUserMenu">
            <div class="user-avatar">
              {{ userStore.profile?.name?.charAt(0) || "U" }}
            </div>
            <div class="user-info">
              <span class="user-name">{{ userStore.profile?.name || t("nav.user") }}</span>
              <span class="user-role">{{ t("nav.member") }}</span>
            </div>
            <svg class="menu-arrow" :class="{ open: showUserMenu }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          </div>

          
          <transition name="slide-up">
            <div v-if="showUserMenu" class="user-menu">
              <router-link to="/profile" class="menu-item" @click="showUserMenu = false">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                  <circle cx="12" cy="7" r="4"/>
                </svg>
                <span>{{ t("nav.profile") }}</span>
              </router-link>
              <button class="menu-item danger" @click="handleLogout">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                  <polyline points="16 17 21 12 16 7"/>
                  <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
                <span>{{ t("nav.logout") }}</span>
              </button>
            </div>
          </transition>
        </div>
      </div>
    </aside>

    
    <main class="main-content" :class="{ 'home-bg-disabled': isHomeRoute }">
      
      <div class="content-wrapper" :class="{ 'home-gradient-layer': isHomeRoute }">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, h } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useUserStore } from "../store/user";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const showUserMenu = ref(false);
const isCollapsed = ref(false);

const handleSidebarToggle = (e: CustomEvent) => {
  isCollapsed.value = e.detail.collapsed;
};

onMounted(() => {
  window.addEventListener("toggle-sidebar", handleSidebarToggle as EventListener);
});

onUnmounted(() => {
  window.removeEventListener("toggle-sidebar", handleSidebarToggle as EventListener);
});

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value;
};

const HomeIcon = () => h("path", { d: "M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z", fill: "none", stroke: "currentColor", "stroke-width": "1.5" });
const ChatIcon = () => h("g", { fill: "none", stroke: "currentColor", "stroke-width": "1.5" }, [
  h("path", { d: "M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" })
]);
const SessionsIcon = () => h("g", { fill: "none", stroke: "currentColor", "stroke-width": "1.5" }, [
  h("line", { x1: "8", y1: "6", x2: "21", y2: "6" }),
  h("line", { x1: "8", y1: "12", x2: "21", y2: "12" }),
  h("line", { x1: "8", y1: "18", x2: "21", y2: "18" }),
  h("line", { x1: "3", y1: "6", x2: "3.01", y2: "6" }),
  h("line", { x1: "3", y1: "12", x2: "3.01", y2: "12" }),
  h("line", { x1: "3", y1: "18", x2: "3.01", y2: "18" })
]);
const VoicesIcon = () => h("g", { fill: "none", stroke: "currentColor", "stroke-width": "1.5" }, [
  h("path", { d: "M9 18V5l12-2v13" }),
  h("circle", { cx: "6", cy: "18", r: "3" }),
  h("circle", { cx: "18", cy: "16", r: "3" })
]);
const FamiliesIcon = () => h("g", { fill: "none", stroke: "currentColor", "stroke-width": "1.5" }, [
  h("path", { d: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" }),
  h("circle", { cx: "9", cy: "7", r: "4" }),
  h("path", { d: "M23 21v-2a4 4 0 0 0-3-3.87" }),
  h("path", { d: "M16 3.13a4 4 0 0 1 0 7.75" })
]);

const mainNavItems = computed(() => [
  { path: "/home", icon: HomeIcon, label: t("nav.home") },
  { path: "/chat", icon: ChatIcon, label: t("nav.chat") },
  { path: "/sessions", icon: SessionsIcon, label: t("nav.sessions") },
]);

const secondaryNavItems = computed(() => [
  { path: "/voices", icon: VoicesIcon, label: t("nav.voices") },
  { path: "/families", icon: FamiliesIcon, label: t("nav.families") },
]);

const isHomeRoute = computed(() => route.path === "/home");

const isActive = (path: string): boolean => {
  if (path === "/home") return route.path === "/home";
  return route.path.startsWith(path);
};

const handleLogout = async () => {
  showUserMenu.value = false;
  await userStore.logout();
  router.push("/auth/login");
};
</script>

<style scoped>
.main-layout {
  display: flex;
  min-height: 100vh;
  background: var(--color-bg);
  transition: all var(--duration-medium) var(--ease-standard);
}

/* ===== 渚ц竟鏍?===== */
.sidebar {
  width: 220px;
  background: rgba(255, 250, 244, 0.86);
  border-right: 1px solid rgba(243, 229, 216, 0.6);
  backdrop-filter: blur(var(--blur-soft));
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: hidden;
  transition: width var(--duration-medium) var(--ease-standard),
    background var(--duration-medium) var(--ease-standard);
}

.main-layout.collapsed .sidebar {
  width: 72px;
}

.sidebar-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--space-4);
  transition: padding 0.3s ease;
}

.main-layout.collapsed .sidebar-inner {
  padding: var(--space-3);
}

.sidebar-brand {
  margin-bottom: var(--space-5);
  transition: margin 0.3s ease;
}

.main-layout.collapsed .sidebar-brand {
  margin-bottom: var(--space-4);
}

.brand-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-standard);
  overflow: hidden;
}

.brand-link:hover {
  background: rgba(253, 186, 116, 0.15);
}

.brand-icon {
  width: 28px;
  height: 28px;
  color: var(--color-primary);
  flex-shrink: 0;
}

.brand-name {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  letter-spacing: 0.02em;
  white-space: nowrap;
  opacity: 1;
  transition: opacity 0.2s ease;
}

.main-layout.collapsed .brand-name {
  opacity: 0;
  width: 0;
}

/* ===== 瀵艰埅鑿滃崟 ===== */
.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 10px 12px;
  border-radius: var(--radius-md);
  color: var(--color-muted);
  font-size: 15px;
  transition: all var(--duration-fast) var(--ease-standard);
  text-decoration: none;
  overflow: hidden;
}

.nav-item:hover {
  background: rgba(253, 186, 116, 0.12);
  color: var(--color-text);
}

.nav-item.active {
  background: linear-gradient(90deg, rgba(249, 115, 22, 0.12), rgba(249, 115, 22, 0.02));
  color: var(--color-primary-strong);
  font-weight: 500;
}

.nav-item.active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--color-primary);
}

.nav-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
}

.nav-label {
  flex: 1;
  white-space: nowrap;
  opacity: 1;
  transition: opacity 0.2s ease;
}

.main-layout.collapsed .nav-label {
  opacity: 0;
  width: 0;
}

.nav-divider {
  height: 1px;
  background: rgba(243, 229, 216, 0.6);
  margin: var(--space-3) 0;
  transition: margin 0.3s ease, opacity 0.2s ease;
}

.main-layout.collapsed .nav-divider {
  margin: var(--space-2) calc(var(--space-3) - 8px);
}

.main-layout.collapsed .nav-divider {
  opacity: 0.5;
}

/* ===== 搴曢儴鐢ㄦ埛鍗＄墖 ===== */
.sidebar-footer {
  position: relative;
  margin-top: var(--space-4);
  transition: margin 0.3s ease;
}

.main-layout.collapsed .sidebar-footer {
  margin-top: var(--space-3);
}

.user-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(243, 229, 216, 0.6);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-standard);
  overflow: hidden;
}

.user-card:hover {
  background: rgba(255, 255, 255, 0.95);
  border-color: rgba(249, 115, 22, 0.3);
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-accent), var(--color-primary));
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
}

.user-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  opacity: 1;
  transition: opacity 0.2s ease;
}

.main-layout.collapsed .user-info {
  opacity: 0;
  width: 0;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  font-size: 12px;
  color: var(--color-muted);
}

.menu-arrow {
  width: 16px;
  height: 16px;
  color: var(--color-muted);
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.main-layout.collapsed .menu-arrow {
  opacity: 0;
}

.menu-arrow.open {
  transform: rotate(90deg);
}

/* ===== 鐢ㄦ埛鑿滃崟 ===== */
.user-menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(239, 227, 215, 0.8);
  border-radius: var(--radius-md);
  box-shadow: 0 12px 30px rgba(45, 36, 32, 0.1);
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-menu svg {
  width: 18px;
  height: 18px;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--color-text);
  background: transparent;
  border: none;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
  text-decoration: none;
}

.menu-item:hover {
  background: rgba(253, 186, 116, 0.15);
}

.menu-item.danger {
  color: #b9553a;
}

.menu-item.danger:hover {
  background: rgba(248, 113, 113, 0.15);
}

/* ===== 涓诲唴瀹瑰尯 ===== */
.main-content {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow-x: hidden;
  transition: margin-left 0.3s ease;
}

.main-content::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    radial-gradient(920px 560px at 0% 0%, rgba(253, 186, 116, 0.1), transparent 62%),
    radial-gradient(860px 520px at 100% 0%, rgba(147, 197, 253, 0.08), transparent 60%),
    linear-gradient(180deg, #fffaf5 0%, #fff8f2 55%, #fff6ef 100%);
}

.main-content.home-bg-disabled::before {
  display: none;
}

.content-wrapper {
  position: relative;
  z-index: 1;
  flex: 1;
  padding: clamp(16px, 2.6vw, 24px);
  max-width: 100%;
  overflow-x: hidden;
  background: transparent;
}

.content-wrapper.home-gradient-layer::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background:
    linear-gradient(180deg, rgba(255, 250, 244, 0.96) 0%, rgba(255, 246, 238, 0.94) 55%, rgba(255, 243, 233, 0.95) 100%),
    radial-gradient(820px 520px at 12% 8%, rgba(253, 186, 116, 0.11), transparent 60%),
    radial-gradient(720px 480px at 88% -4%, rgba(254, 215, 170, 0.1), transparent 60%),
    radial-gradient(680px 420px at 50% 100%, rgba(253, 186, 116, 0.09), transparent 70%);
}

.content-wrapper.home-gradient-layer > * {
  position: relative;
  z-index: 1;
}

/* ===== 杩囨浮鍔ㄧ敾 ===== */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.2s ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

/* ===== 鍝嶅簲寮?===== */
@media (max-width: 768px) {
  .sidebar {
    display: none;
  }

  .main-content {
    width: 100%;
  }
}
</style>

