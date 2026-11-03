/** Lucide 风格的图标路径（ISC），以内联 SVG 使用，不引依赖。 */
export const navIcons = {
  chat: [
    "M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z",
  ],
  history: ["M3 12a9 9 0 1 0 3-6.7", "M3 4v4h4", "M12 7v5l3 2"],
  memory: [
    "M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z",
    "M8 7h8",
    "M8 11h8",
    "M8 15h5",
  ],
  voice: [
    "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z",
    "M5 11a7 7 0 0 0 14 0",
    "M12 18v3",
  ],
  about: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 11v5", "M12 8h.01"],
  settings: [
    "M4 7h9",
    "M18 7h2",
    "M4 17h3",
    "M12 17h8",
    "M13.3 7a2.2 2.2 0 1 0 4.4 0 2.2 2.2 0 1 0-4.4 0",
    "M7.3 17a2.2 2.2 0 1 0 4.4 0 2.2 2.2 0 1 0-4.4 0",
  ],
  chevron: ["m15 18-6-6 6-6"],
} as const;

export type NavIconName = keyof typeof navIcons;

/**
 * 设置窗口左侧导航的图标（与主壳同一套线条风格）。
 * 键名与 `SettingsWindow.vue` 的 section id 一一对应。
 */
export const settingsIcons = {
  appearance: [
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z",
    "M12 3v18",
    "M12 7a5 5 0 0 1 0 10",
  ],
  persona: [
    "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2",
    "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  ],
  engine: [
    "M6 6h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z",
    "M9 9h6v6H9z",
    "M9 2v2",
    "M15 2v2",
    "M9 20v2",
    "M15 20v2",
  ],
  voice: [
    "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z",
    "M5 11a7 7 0 0 0 14 0",
    "M12 18v3",
  ],
  data: ["M12 21s7-3.6 7-9V6l-7-3-7 3v6c0 5.4 7 9 7 9z", "M9.5 11.5l1.8 1.8 3.4-3.4"],
  shortcuts: [
    "M3 7h18v10H3z",
    "M7 11h.01",
    "M11 11h.01",
    "M15 11h.01",
    "M7.5 14h9",
  ],
  about: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z", "M12 11v5", "M12 8h.01"],
  back: ["M15 18l-6-6 6-6"],
} as const;
