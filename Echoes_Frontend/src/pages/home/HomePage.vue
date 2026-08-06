<template>
  <main class="home-shell">
    <div class="home-toolbar">
      <button class="toolbar-btn" @click="toggleCollapse" :title="isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'">
        <svg v-if="isCollapsed" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>
      <LanguageSwitcher />
    </div>
    <div class="container home">
      <header class="hero card">
        <div class="hero-intro">
          <p class="eyebrow">{{ t("home.eyebrow") }}</p>
          <h1 class="title">{{ t("home.title") }}</h1>
          <p class="subtitle">{{ t("home.subtitle") }}</p>
          <div class="hero-actions">
            <router-link class="primary-cta" to="/chat">{{ t("home.tileChat") }}</router-link>
            <router-link class="ghost-cta" to="/sessions">{{ t("home.tileSessions") }}</router-link>
          </div>
        </div>
        <div class="hero-note">
          <div class="note-header">
            <span class="note-dot"></span>
            <span>{{ t("home.welcomeLabel") }}</span>
          </div>
          <p class="note-text">{{ t("home.welcomeText") }}</p>
          <div class="note-divider"></div>
          <p class="note-tip">
            <span>{{ t("home.tipTitle") }}</span>
            {{ t("home.tipText") }}
          </p>
        </div>
      </header>

      <section class="feature-grid">
        <router-link class="feature-card" to="/chat">
          <div class="feature-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <div>
            <h3>{{ t("home.tileChat") }}</h3>
            <p>{{ t("home.tileChatDesc") }}</p>
          </div>
        </router-link>
        <router-link class="feature-card" to="/sessions">
          <div class="feature-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <line x1="8" y1="6" x2="21" y2="6"/>
              <line x1="8" y1="12" x2="21" y2="12"/>
              <line x1="8" y1="18" x2="21" y2="18"/>
              <line x1="3" y1="6" x2="3.01" y2="6"/>
              <line x1="3" y1="12" x2="3.01" y2="12"/>
              <line x1="3" y1="18" x2="3.01" y2="18"/>
            </svg>
          </div>
          <div>
            <h3>{{ t("home.tileSessions") }}</h3>
            <p>{{ t("home.tileSessionsDesc") }}</p>
          </div>
        </router-link>
        <router-link class="feature-card" to="/profile">
          <div class="feature-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
              <circle cx="12" cy="7" r="4"/>
            </svg>
          </div>
          <div>
            <h3>{{ t("home.tileProfile") }}</h3>
            <p>{{ t("home.tileProfileDesc") }}</p>
          </div>
        </router-link>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue";
import { useI18n } from "vue-i18n";
import LanguageSwitcher from "../../components/LanguageSwitcher.vue";

const { t } = useI18n();
const isCollapsed = ref(false);

const handleSidebarToggle = (e: Event) => {
  const event = e as CustomEvent<{ collapsed?: boolean }>;
  isCollapsed.value = !!event.detail?.collapsed;
};

const toggleCollapse = () => {
  const next = !isCollapsed.value;
  isCollapsed.value = next;
  window.dispatchEvent(new CustomEvent("toggle-sidebar", { detail: { collapsed: next } }));
};

onMounted(() => {
  window.addEventListener("toggle-sidebar", handleSidebarToggle as EventListener);
});

onBeforeUnmount(() => {
  window.removeEventListener("toggle-sidebar", handleSidebarToggle as EventListener);
});
</script>

<style scoped>
.home-shell {
  position: relative;
  min-height: 100%;
  padding: var(--space-8) 0 var(--space-9);
  overflow: hidden;
}

/* 椤堕儴鍔熻兘鏍?*/
.home-toolbar {
  position: relative;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4);
  margin-top: -4px;
  margin-bottom: var(--space-6);
}

.toolbar-btn {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  border: 1px solid rgba(243, 229, 216, 0.6);
  background: var(--color-surface-elevated);
  color: var(--color-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-standard);
  box-shadow: var(--shadow-card);
}

.toolbar-btn:hover {
  background: rgba(253, 186, 116, 0.12);
  border-color: rgba(249, 115, 22, 0.3);
  color: var(--color-primary);
  transform: translateY(-1px);
}

.toolbar-btn svg {
  width: 20px;
  height: 20px;
}

.home-toolbar :deep(.lang-switcher) {
  transform: translateY(-2px);
}

.home-toolbar :deep(.lang-trigger) {
  min-height: 44px;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
}

.home {
  display: grid;
  gap: var(--space-7);
  position: relative;
  z-index: 1;
  padding-top: var(--space-5);
}

.hero {
  padding: clamp(24px, 4vw, 48px);
  display: grid;
  gap: var(--space-5);
  background:
    linear-gradient(140deg, rgba(255, 245, 233, 0.92), rgba(255, 252, 245, 0.9));
  border: 1px solid rgba(239, 227, 215, 0.7);
  box-shadow: var(--shadow-elevated);
}

.hero-intro {
  display: grid;
  gap: var(--space-4);
}

.eyebrow {
  font-size: var(--text-xs);
  text-transform: uppercase;
  letter-spacing: 0.2em;
  color: var(--color-accent);
  margin: 0;
}

.title {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(30px, 4.4vw, 46px);
  line-height: var(--lh-tight);
}

.subtitle {
  margin: 0;
  color: var(--color-muted-soft);
  max-width: 56ch;
  font-size: clamp(15px, 1.35vw, 17px);
  line-height: var(--lh-copy);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.primary-cta,
.ghost-cta {
  padding: 12px 20px;
  border-radius: 999px;
  font-weight: 600;
  font-size: var(--text-sm);
  transition: all var(--duration-fast) var(--ease-standard);
}

.primary-cta {
  background: linear-gradient(135deg, #fb923c, #f97316);
  color: #fffaf5;
  box-shadow: 0 12px 25px rgba(249, 115, 22, 0.28);
}

.primary-cta:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 28px rgba(249, 115, 22, 0.3);
}

.ghost-cta {
  border: 1px solid rgba(229, 139, 58, 0.3);
  color: var(--color-text);
  background: rgba(255, 255, 255, 0.7);
}

.ghost-cta:hover {
  border-color: rgba(229, 139, 58, 0.6);
  background: rgba(255, 255, 255, 0.9);
}

.hero-note {
  padding: 22px;
  border-radius: 18px;
  background: rgba(255, 253, 248, 0.92);
  border: 1px dashed rgba(241, 180, 123, 0.4);
  display: grid;
  gap: var(--space-3);
  backdrop-filter: blur(6px);
}

.note-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--text-xs);
  letter-spacing: 0.2em;
  color: var(--color-muted-soft);
  text-transform: uppercase;
}

.note-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f1b47b;
}

.note-text {
  margin: 0;
  font-weight: 600;
  font-size: var(--text-lg);
  line-height: 1.5;
}

.note-divider {
  height: 1px;
  background: rgba(239, 227, 215, 0.8);
}

.note-tip {
  margin: 0;
  color: var(--color-muted-soft);
  font-size: 13px;
  line-height: 1.65;
}

.note-tip span {
  font-weight: 600;
  margin-right: 6px;
  color: var(--color-text);
}

.feature-grid {
  display: grid;
  gap: var(--space-4);
}

.feature-card {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--space-4);
  padding: 22px 24px;
  border-radius: 18px;
  border: 1px solid rgba(239, 227, 215, 0.7);
  background: rgba(255, 255, 255, 0.8);
  box-shadow: var(--shadow-card);
  transition: transform var(--duration-fast) var(--ease-standard),
    box-shadow var(--duration-fast) var(--ease-standard),
    background var(--duration-fast) var(--ease-standard);
}

.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 34px rgba(77, 48, 20, 0.1);
  background: rgba(255, 255, 255, 0.85);
}

.feature-icon {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: linear-gradient(135deg, rgba(253, 186, 116, 0.32), rgba(251, 146, 60, 0.22));
  display: grid;
  place-items: center;
}

.feature-icon svg {
  width: 22px;
  height: 22px;
  stroke: #ea580c;
}

.feature-card h3 {
  margin: 0 0 6px;
  font-family: var(--font-display);
  line-height: 1.35;
}

.feature-card p {
  margin: 0;
  color: var(--color-muted-soft);
  line-height: 1.62;
}

@media (max-width: 768px) {
  .home-shell {
    padding: var(--space-6) 0 var(--space-7);
  }

  .home-toolbar {
    padding: var(--space-3);
    margin-bottom: var(--space-4);
  }

  .home {
    gap: var(--space-5);
    padding-top: var(--space-4);
  }

  .hero {
    padding: 20px;
    gap: var(--space-4);
    border-radius: 18px;
  }

  .title {
    font-size: clamp(26px, 8vw, 34px);
  }

  .subtitle {
    max-width: 100%;
    font-size: 15px;
  }

  .hero-note {
    padding: 18px;
    border-radius: 16px;
  }

  .feature-grid {
    gap: var(--space-3);
  }

  .feature-card {
    padding: 18px;
    gap: var(--space-3);
    border-radius: 16px;
  }
}

@media (min-width: 900px) {
  .hero {
    grid-template-columns: 1.2fr 0.8fr;
    align-items: center;
  }
  .feature-grid {
    grid-template-columns: repeat(3, 1fr);
  }
  .feature-card {
    grid-template-columns: 1fr;
    text-align: left;
    align-content: start;
    min-height: 180px;
  }
  .feature-icon {
    width: 52px;
    height: 52px;
  }
  .feature-icon svg {
    width: 26px;
    height: 26px;
  }
}
</style>


