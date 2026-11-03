import { onMounted, onUnmounted, ref } from "vue";

export type SkinMode = "light" | "dark";

/**
 * 把旧的 `data-theme`（paper / nocturne / desktop）映射成新皮肤的 light / dark。
 * P3 会换成正式的 system / light / dark 设置；在那之前只读不写，避免两套主题打架。
 */
export function useSkinMode() {
  const mode = ref<SkinMode>("light");
  let observer: MutationObserver | null = null;

  function sync(): void {
    if (typeof document === "undefined") return;
    mode.value =
      document.documentElement.dataset.theme === "nocturne" ? "dark" : "light";
  }

  onMounted(() => {
    sync();
    if (typeof MutationObserver === "undefined") return;
    observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
  });

  onUnmounted(() => observer?.disconnect());

  return { mode };
}
