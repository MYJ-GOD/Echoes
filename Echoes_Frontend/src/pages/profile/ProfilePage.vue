<template>
  <main class="section">
    <div class="container profile">
      <div class="card profile-card">
        <h2 class="profile-title">{{ t("profile.title") }}</h2>
        <div class="profile-row">
          <span>{{ t("profile.language") }}</span>
          <button class="link" @click="toggleLocale">
            {{ localeLabel }}
          </button>
        </div>
        <div class="profile-row">
          <span>{{ t("profile.voice") }}</span>
          <span class="muted">{{ t("profile.voiceHint") }}</span>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { setLocale } from "../../app/i18n";

const { locale, t } = useI18n();

const localeLabel = computed(() => (locale.value === "zh-CN" ? "����" : "English"));

function toggleLocale() {
  const next = locale.value === "zh-CN" ? "en-US" : "zh-CN";
  setLocale(next as "zh-CN" | "en-US");
}
</script>

<style scoped>
.profile {
  display: grid;
  place-items: center;
  padding: var(--space-8) 0;
}

.profile-card {
  width: min(100%, 520px);
  padding: var(--space-7);
  display: grid;
  gap: var(--space-5);
  background: rgba(255, 255, 255, 0.85);
  border-radius: 20px;
  border: 1px solid rgba(239, 227, 215, 0.7);
  box-shadow: var(--shadow-card);
  backdrop-filter: blur(8px);
}

.profile-title {
  margin: 0 0 var(--space-2);
  font-family: var(--font-display);
  font-size: 24px;
  color: var(--color-text);
}

.profile-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) 0;
  border-bottom: 1px solid rgba(239, 227, 215, 0.5);
}

.profile-row:last-child {
  border-bottom: none;
}

.link {
  background: none;
  border: none;
  color: var(--color-primary-strong);
  cursor: pointer;
}

.muted {
  color: var(--color-muted);
}
</style>
