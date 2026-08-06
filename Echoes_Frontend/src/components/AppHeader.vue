<template>
  <header class="app-header">
    <div class="container header-inner">
      <div class="brand">
        <span class="brand-mark">{{ t("nav.brand") }}</span>
      </div>
      <nav class="nav-links">
        <router-link to="/home">{{ t("nav.home") }}</router-link>
        <router-link to="/sessions">{{ t("nav.sessions") }}</router-link>
        <router-link to="/voices">{{ t("nav.voices") }}</router-link>
        <router-link to="/families">{{ t("nav.families") }}</router-link>
      </nav>
      <div class="header-right">
        <router-link class="header-action" to="/chat">{{ t("nav.chat") }}</router-link>
        <div class="profile-menu">
          <button class="profile-trigger" type="button">
            <span class="avatar-dot"></span>
          </button>
          <div class="profile-panel">
            <router-link class="panel-link" to="/profile">{{ t("nav.profile") }}</router-link>
            <router-link class="panel-link" to="/voices">{{ t("nav.myVoices") }}</router-link>
            <router-link class="panel-link" to="/families">{{ t("nav.myFamilies") }}</router-link>
            <button class="panel-link danger" type="button" @click="handleLogout">
              {{ t("nav.logout") }}
            </button>
          </div>
        </div>
        <LanguageSwitcher />
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { useUserStore } from "../store/user";
import LanguageSwitcher from "./LanguageSwitcher.vue";

const { t } = useI18n();
const router = useRouter();
const userStore = useUserStore();

const handleLogout = async () => {
  await userStore.logout();
  router.push("/auth/login");
};
</script>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 10;
  backdrop-filter: blur(8px);
  background: rgba(255, 248, 240, 0.85);
  border-bottom: 1px solid rgba(243, 229, 216, 0.6);
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) 0;
}

.brand {
  display: flex;
  align-items: center;
}

.brand-mark {
  font-family: var(--font-display);
  font-size: 16px;
}

.nav-links {
  display: none;
  gap: var(--space-1);
  font-size: 15px;
  color: var(--color-muted);
}

.nav-links a {
  padding: 8px 14px;
  border-radius: 10px;
  transition: all 0.2s ease;
}

.nav-links a:hover {
  background: rgba(253, 186, 116, 0.1);
  color: var(--color-text);
}

.nav-links a.router-link-active {
  color: var(--color-text);
  font-weight: 600;
  background: rgba(253, 186, 116, 0.15);
}

.header-action {
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  background: rgba(253, 186, 116, 0.2);
  color: var(--color-text);
  font-size: 15px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.profile-menu {
  position: relative;
}

.profile-menu::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  top: 100%;
  height: 8px;
  background: transparent;
}

.profile-trigger {
  border: 1px solid rgba(249, 115, 22, 0.18);
  background: rgba(255, 255, 255, 0.8);
  color: var(--color-text);
  padding: 6px 8px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.profile-trigger:hover {
  border-color: rgba(249, 115, 22, 0.5);
  box-shadow: 0 4px 12px rgba(249, 115, 22, 0.15);
}

.avatar-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, #fdba74, #f97316);
  box-shadow: 0 0 0 3px rgba(253, 186, 116, 0.28);
}

.profile-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 160px;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(239, 227, 215, 0.8);
  border-radius: 12px;
  box-shadow: 0 12px 30px rgba(45, 36, 32, 0.1);
  padding: 6px;
  display: grid;
  gap: 2px;
  opacity: 0;
  transform: translateY(-4px);
  pointer-events: none;
  transition: all 0.2s ease;
}

.profile-menu:hover .profile-panel,
.profile-menu:focus-within .profile-panel {
  opacity: 1;
  transform: translateY(0);
  pointer-events: auto;
}

.panel-link {
  display: block;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 14px;
  color: var(--color-text);
  background: transparent;
  border: none;
  text-align: left;
  cursor: pointer;
  text-decoration: none;
}

.panel-link:hover {
  background: rgba(253, 186, 116, 0.15);
}

.panel-link.danger {
  color: #b9553a;
}

@media (min-width: 860px) {
  .nav-links {
    display: flex;
  }
}
</style>
