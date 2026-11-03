import { computed, onMounted, onUnmounted, ref } from "vue";

export type ThemeMode = "system" | "light" | "dark";

const KEY = "echoes.theme";

function readMode(): ThemeMode {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw === "light" || raw === "paper" || raw === "desktop") return "light";
    if (raw === "dark" || raw === "nocturne") return "dark";
    return "system";
  } catch {
    return "system";
  }
}

/**
 * 设置窗口的唯一主题入口：对外只说 system / light / dark，
 * 对旧 CSS 仍写 paper / nocturne，避免和旧主题选择器打架。
 */
export function useTheme() {
  const mode = ref<ThemeMode>(readMode());
  const darkQuery =
    typeof window !== "undefined" && "matchMedia" in window
      ? window.matchMedia("(prefers-color-scheme: dark)")
      : null;
  const resolved = computed<"light" | "dark">(() =>
    mode.value === "system"
      ? darkQuery?.matches
        ? "dark"
        : "light"
      : mode.value,
  );

  function apply(): void {
    if (typeof document === "undefined") return;
    document.documentElement.dataset.theme =
      resolved.value === "dark" ? "nocturne" : "paper";
  }

  function persist(): void {
    try {
      localStorage.setItem(
        KEY,
        mode.value === "system"
          ? "system"
          : resolved.value === "dark"
            ? "nocturne"
            : "paper",
      );
    } catch {
      // 隐私模式/存储被禁用：只在本次窗口生效
    }
  }

  function setMode(next: ThemeMode): void {
    mode.value = next;
    persist();
    apply();
  }

  function onSystemChange(): void {
    if (mode.value !== "system") return;
    persist();
    apply();
  }

  onMounted(() => {
    apply();
    darkQuery?.addEventListener("change", onSystemChange);
  });

  onUnmounted(() => {
    darkQuery?.removeEventListener("change", onSystemChange);
  });

  return { mode, resolved, setMode };
}
