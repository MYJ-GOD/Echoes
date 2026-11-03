import { ref } from "vue";

export type Density = "comfortable" | "compact";

const KEY = "echoes.density";
const density = ref<Density>(read());

function read(): Density {
  try {
    return localStorage.getItem(KEY) === "compact" ? "compact" : "comfortable";
  } catch {
    return "comfortable";
  }
}

function sync(): void {
  density.value = read();
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (event.key === KEY) sync();
  });
  window.addEventListener("echoes:density", sync);
}

export function useDensity() {
  function setDensity(next: Density): void {
    density.value = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // 隐私模式：只在本次窗口生效
    }
    window.dispatchEvent(new Event("echoes:density"));
  }
  return { density, setDensity };
}
