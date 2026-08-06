import { createI18n } from "vue-i18n";
import zhCN from "../locales/zh-CN";
import enUS from "../locales/en-US";

const LOCALE_KEY = "echoes_locale";

const messages = {
  "zh-CN": zhCN,
  "en-US": enUS
};

const locale = localStorage.getItem(LOCALE_KEY) || "zh-CN";

const i18n = createI18n({
  legacy: false,
  locale,
  fallbackLocale: "zh-CN",
  messages
});

export function setLocale(next: "zh-CN" | "en-US") {
  localStorage.setItem(LOCALE_KEY, next);
  i18n.global.locale.value = next;
}

export default i18n;
