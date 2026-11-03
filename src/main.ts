import { createApp } from "vue";

import "./styles/themes.css";
import "./design/tokens.css";
import "./design/base.css";
import App from "./App.vue";
import router from "./router";

// 暗色主题必须在首帧前落到 <html> 上，否则会闪一下白底
try {
  const stored = localStorage.getItem("echoes.theme");
  const dark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  if (stored === "nocturne") {
    document.documentElement.dataset.theme = stored;
  } else if (stored === "system" && dark) {
    document.documentElement.dataset.theme = "nocturne";
  }
} catch {
  // 存储不可用：按默认信笺主题走
}

createApp(App).use(router).mount("#app");
