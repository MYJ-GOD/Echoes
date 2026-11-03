<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, useId, watch } from "vue";

import { useSkinMode } from "../../composables/useSkinMode";

const { mode } = useSkinMode();

const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    description?: string;
    size?: "sm" | "md";
    persistent?: boolean;
  }>(),
  {
    description: "",
    size: "sm",
    persistent: false,
  },
);

const emit = defineEmits<{ close: [] }>();
const panel = ref<HTMLElement | null>(null);
const titleId = useId();
const descId = useId();

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

let previousActive: HTMLElement | null = null;

function focusFirst(): void {
  const root = panel.value;
  if (!root) return;
  const target =
    root.querySelector<HTMLElement>("[data-autofocus]") ??
    root.querySelector<HTMLElement>(FOCUSABLE) ??
    root;
  target.focus();
}

function close(): void {
  emit("close");
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape" && !props.persistent) {
    event.stopPropagation();
    close();
    return;
  }
  if (event.key !== "Tab") return;
  const root = panel.value;
  if (!root) return;
  const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (item) => item.offsetParent !== null,
  );
  if (items.length === 0) {
    event.preventDefault();
    root.focus();
    return;
  }
  const first = items[0]!;
  const last = items[items.length - 1]!;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      previousActive = document.activeElement as HTMLElement | null;
      await nextTick();
      focusFirst();
    } else {
      previousActive?.focus?.();
      previousActive = null;
    }
  },
);

onBeforeUnmount(() => {
  previousActive?.focus?.();
});
</script>

<template>
  <Teleport to="body">
    <Transition name="ds-dialog">
      <div
        v-if="open"
        class="ds-dialog-overlay"
        data-skin="next"
        :data-mode="mode"
        @mousedown.self="!persistent && close()"
      >
        <section
          ref="panel"
          class="ds-dialog"
          :class="`ds-dialog--${size}`"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
          :aria-describedby="description ? descId : undefined"
          tabindex="-1"
          @keydown="onKeydown"
        >
          <header class="ds-dialog__head">
            <div class="ds-dialog__heading">
              <h2 :id="titleId" class="ds-dialog__title">{{ title }}</h2>
              <p v-if="description" :id="descId" class="ds-dialog__desc">
                {{ description }}
              </p>
            </div>
            <button
              type="button"
              class="ds-dialog__close"
              aria-label="关闭"
              @click="close"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                aria-hidden="true"
              >
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </header>

          <div v-if="$slots.default" class="ds-dialog__body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="ds-dialog__footer">
            <slot name="footer" />
          </footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.ds-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: var(--space-6);
  background: color-mix(in srgb, var(--ink) 28%, transparent);
}

.ds-dialog {
  display: flex;
  flex-direction: column;
  width: min(100%, 420px);
  max-height: calc(100vh - 48px);
  border: 1px solid var(--rule);
  border-radius: var(--radius-overlay);
  background: var(--raised);
  box-shadow: var(--shadow-3);
}

.ds-dialog--md {
  width: min(100%, 560px);
}

.ds-dialog__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-5) var(--space-5) var(--space-3);
}

.ds-dialog__heading {
  min-width: 0;
}

.ds-dialog__title {
  color: var(--ink);
  font-size: var(--text-title);
  font-weight: 600;
  line-height: var(--text-title-line);
}

.ds-dialog__desc {
  margin-top: var(--space-1);
  color: var(--ink-2);
  font-size: 13px;
  line-height: 19px;
}

.ds-dialog__close {
  display: grid;
  place-items: center;
  width: var(--control-h-sm);
  height: var(--control-h-sm);
  flex: none;
  border-radius: var(--radius-control);
  color: var(--ink-3);
}

.ds-dialog__close:hover {
  background: var(--surface-2);
  color: var(--ink);
}

.ds-dialog__body {
  min-height: 0;
  padding: 0 var(--space-5) var(--space-4);
  overflow-y: auto;
  color: var(--ink-2);
  font-size: 13px;
  line-height: 1.7;
}

.ds-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5) var(--space-5);
}

.ds-dialog-enter-active,
.ds-dialog-leave-active {
  transition: opacity var(--dur-enter) var(--ease);
}

.ds-dialog-enter-active .ds-dialog,
.ds-dialog-leave-active .ds-dialog {
  transition:
    opacity var(--dur-enter) var(--ease),
    transform var(--dur-enter) var(--ease);
}

.ds-dialog-enter-from,
.ds-dialog-leave-to {
  opacity: 0;
}

.ds-dialog-enter-from .ds-dialog,
.ds-dialog-leave-to .ds-dialog {
  opacity: 0;
  transform: translateY(6px) scale(0.985);
}
</style>
