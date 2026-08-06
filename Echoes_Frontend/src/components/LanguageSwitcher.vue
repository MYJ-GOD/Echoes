<template>
  <div class="lang-switcher">
    <!-- 图标按钮 -->
    <button
      type="button"
      class="lang-icon-btn"
      :title="locale === 'zh-CN' ? '当前: 中文' : 'Current: English'"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="2" y1="12" x2="22" y2="12"/>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
      </svg>
    </button>

    <!-- 悬浮语言选择菜单 -->
    <div class="lang-menu">
      <button
        type="button"
        class="lang-option"
        :class="{ active: locale === 'zh-CN' }"
        @click="switchLocale('zh-CN')"
      >
        <span class="lang-code">中</span>
        <span class="lang-name">中文</span>
      </button>
      <button
        type="button"
        class="lang-option"
        :class="{ active: locale === 'en-US' }"
        @click="switchLocale('en-US')"
      >
        <span class="lang-code">EN</span>
        <span class="lang-name">English</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from "vue-i18n";
import { setLocale } from "../app/i18n";

const { locale } = useI18n();

const switchLocale = (nextLocale: "zh-CN" | "en-US") => {
  if (locale.value === nextLocale) return;
  setLocale(nextLocale);
};
</script>

<style scoped>
.lang-switcher {
  position: relative;
  display: flex;
  align-items: center;
}

/* 图标按钮 */
.lang-icon-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(243, 229, 216, 0.6);
  background: rgba(255, 255, 255, 0.8);
  color: var(--color-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.lang-icon-btn:hover {
  background: rgba(253, 186, 116, 0.15);
  border-color: rgba(249, 115, 22, 0.3);
  color: var(--color-primary);
}

.lang-icon-btn svg {
  width: 18px;
  height: 18px;
}

/* 悬浮菜单 */
.lang-menu {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  background: rgba(255, 255, 255, 0.98);
  border: 1px solid rgba(239, 227, 215, 0.8);
  border-radius: var(--radius-md);
  box-shadow: 0 12px 30px rgba(45, 36, 32, 0.1);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-4px);
  transition: all 0.2s ease;
  z-index: 100;
}

/* 悬浮显示菜单 */
.lang-switcher:hover .lang-menu {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

/* 语言选项 */
.lang-option {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--color-text);
  background: transparent;
  border: none;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
}

.lang-option:hover {
  background: rgba(253, 186, 116, 0.15);
}

.lang-option.active {
  background: rgba(249, 115, 22, 0.1);
  color: var(--color-primary);
  font-weight: 500;
}

.lang-code {
  font-weight: 600;
  font-size: 13px;
  min-width: 24px;
}

.lang-name {
  color: var(--color-muted);
  font-size: 13px;
}

.lang-option.active .lang-name {
  color: var(--color-primary);
}
</style>
