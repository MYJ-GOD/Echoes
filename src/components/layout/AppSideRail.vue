<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { navIcons } from "./icons";
import type { NavIconName } from "./icons";

defineProps<{ mode: "light" | "dark" }>();
const emit = defineEmits<{ settings: [] }>();

const route = useRoute();
const collapsed = ref(false);

const items: { to: string; label: string; icon: NavIconName }[] = [
  { to: "/", label: "对话", icon: "chat" },
  { to: "/history", label: "历史", icon: "history" },
  { to: "/memory", label: "记忆", icon: "memory" },
  { to: "/voice", label: "声音", icon: "voice" },
  { to: "/about", label: "关于", icon: "about" },
];

const activePath = computed(() => route.path);

function isActive(path: string): boolean {
  return path === "/" ? activePath.value === "/" : activePath.value === path;
}
</script>

<template>
  <aside
    class="rail"
    :class="{ 'is-collapsed': collapsed }"
    data-skin="next"
    :data-mode="mode"
    aria-label="主导航"
  >
    <nav class="rail__nav">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="rail__item"
        :class="{ 'is-active': isActive(item.to) }"
        :title="item.label"
        :aria-label="item.label"
        :aria-current="isActive(item.to) ? 'page' : undefined"
      >
        <span class="rail__icon" aria-hidden="true">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.7"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path v-for="(path, index) in navIcons[item.icon]" :key="index" :d="path" />
          </svg>
        </span>
        <span class="rail__label">{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="rail__bottom">
      <button
        type="button"
        class="rail__item"
        title="设置"
        aria-label="设置"
        @click="emit('settings')"
      >
        <span class="rail__icon" aria-hidden="true">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.7"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path v-for="(path, index) in navIcons.settings" :key="index" :d="path" />
          </svg>
        </span>
        <span class="rail__label">设置</span>
      </button>

      <button
        type="button"
        class="rail__toggle"
        :aria-label="collapsed ? '展开导航' : '收起导航'"
        :title="collapsed ? '展开导航' : '收起导航'"
        @click="collapsed = !collapsed"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.7"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
          :class="{ 'is-flipped': collapsed }"
        >
          <path v-for="(path, index) in navIcons.chevron" :key="index" :d="path" />
        </svg>
      </button>
    </div>
  </aside>
</template>

<style scoped>
.rail {
  display: flex;
  flex: none;
  flex-direction: column;
  justify-content: space-between;
  width: 208px;
  min-height: 0;
  padding: 8px 6px;
  border-right: 1px solid var(--rule);
  background: var(--surface);
  transition: width var(--dur-enter) var(--ease);
}

.rail.is-collapsed {
  width: 64px;
}

.rail__nav,
.rail__bottom {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rail__bottom {
  padding-top: 8px;
  border-top: 1px solid var(--rule);
}

.rail__item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  height: 34px;
  padding: 0 8px;
  border-radius: var(--radius-control);
  color: var(--ink-2);
  font-size: 13px;
  text-align: left;
  white-space: nowrap;
  transition:
    background-color var(--dur-hover) var(--ease),
    color var(--dur-hover) var(--ease);
}

.rail__item:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.rail__item.is-active {
  background: var(--accent-soft);
  color: var(--accent);
}

.rail__item.is-active::before {
  content: "";
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 2px;
  border-radius: 2px;
  background: var(--accent);
}

.rail__icon {
  display: grid;
  place-items: center;
  width: 18px;
  height: 18px;
  flex: none;
}

.rail__label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.rail.is-collapsed .rail__label {
  display: none;
}

.rail.is-collapsed .rail__item {
  justify-content: center;
  padding: 0;
}

.rail__toggle {
  display: grid;
  place-items: center;
  width: 100%;
  height: 28px;
  margin-top: 2px;
  border-radius: var(--radius-control);
  color: var(--ink-3);
}

.rail__toggle:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.rail__toggle svg {
  transition: transform var(--dur-enter) var(--ease);
}

.rail__toggle svg.is-flipped {
  transform: rotate(180deg);
}

@media (max-width: 980px) {
  .rail {
    width: 64px;
  }

  .rail .rail__label {
    display: none;
  }

  .rail .rail__item {
    justify-content: center;
    padding: 0;
  }

  .rail__toggle {
    display: none;
  }
}
</style>
