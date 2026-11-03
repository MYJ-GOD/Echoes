<script setup lang="ts">
import DsButton from "../ui/DsButton.vue";
import DsChip from "../ui/DsChip.vue";
import DsStatusDot from "../ui/DsStatusDot.vue";

withDefaults(
  defineProps<{
    name: string;
    stateLabel: string;
    stateTone: "ready" | "active" | "waiting" | "error";
    privacyMode: boolean;
    privacyTitle: string;
    voiceName: string;
    busy: boolean;
    canRecover?: boolean;
  }>(),
  {
    canRecover: false,
  },
);

const emit = defineEmits<{
  openSettings: [];
  stop: [];
  recover: [];
}>();
</script>

<template>
  <header class="chat-header">
    <div class="chat-header__id">
      <h1 class="chat-header__name">{{ name }}</h1>
      <DsStatusDot :tone="stateTone" :label="stateLabel" />
    </div>

    <div class="chat-header__actions">
      <button
        v-if="canRecover"
        type="button"
        class="chat-header__recover"
        title="从备份还原数据库"
        @click="emit('recover')"
      >
        恢复
      </button>
      <DsChip
        :tone="privacyMode ? 'ok' : 'warn'"
        :title="privacyTitle"
        @click="emit('openSettings')"
      >
        {{ privacyMode ? "隐私模式" : "联网模式" }}
      </DsChip>
      <DsButton variant="secondary" size="sm" @click="emit('openSettings')">
        {{ voiceName }}
      </DsButton>
      <DsButton v-if="busy" variant="danger" size="sm" @click="emit('stop')">
        停止
      </DsButton>
    </div>
  </header>
</template>

<style scoped>
.chat-header {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-height: 56px;
  padding: var(--space-3) var(--space-6);
  border-bottom: 1px solid var(--rule);
}

.chat-header__id {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  min-width: 0;
}

.chat-header__name {
  overflow: hidden;
  color: var(--ink);
  font-size: var(--text-title);
  font-weight: 600;
  line-height: var(--text-title-line);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-header__actions {
  display: flex;
  flex: none;
  align-items: center;
  gap: var(--space-2);
}

.chat-header__recover {
  padding: 4px 8px;
  border-radius: var(--radius-control);
  color: var(--danger);
  font-size: 12px;
}

.chat-header__recover:hover {
  background: color-mix(in srgb, var(--danger) 10%, transparent);
}

@media (max-width: 620px) {
  .chat-header {
    padding: var(--space-2) var(--space-4);
  }

  .chat-header__name {
    font-size: 16px;
    line-height: 24px;
  }
}
</style>
