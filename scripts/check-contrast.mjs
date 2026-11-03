#!/usr/bin/env node
/**
 * 对比度门禁：从设计系统 token 取实际计算值，按 WCAG 2.2 计算。
 * 用法：npm run check:contrast
 */
import { startApp } from "./lib/cdp.mjs";

const PAIRS = [
  ["--ink", "--bg", 4.5, "正文 / 窗口底"],
  ["--ink", "--surface", 4.5, "正文 / 表面"],
  ["--ink-2", "--surface", 4.5, "次文字 / 表面"],
  ["--ink-2", "--surface-2", 4.5, "次文字 / 次级表面"],
  ["--ink-3", "--bg", 4.5, "元信息 / 窗口底"],
  ["--ink-3", "--surface", 4.5, "元信息 / 表面"],
  ["--accent-ink", "--accent", 4.5, "主色上的文字"],
  ["--danger", "--surface", 4.5, "错误文字"],
  ["--warn", "--surface", 4.5, "警告文字"],
  ["--ok", "--surface", 4.5, "成功文字"],
  ["--accent", "--surface", 3, "主色图形/焦点"],
  ["--rule-strong", "--bg", 3, "控件边框"],
];

function parseColor(value) {
  const text = value.trim();
  const hex = text.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const number = Number.parseInt(hex[1], 16);
    return [(number >> 16) & 255, (number >> 8) & 255, number & 255];
  }
  const rgb = text.match(/^rgba?\(([^)]+)\)$/i);
  if (rgb) {
    const parts = rgb[1].split(",").map((part) => Number.parseFloat(part));
    return [parts[0], parts[1], parts[2]];
  }
  return null;
}

function luminance([r, g, b]) {
  const channel = (value) => {
    const normalized = value / 255;
    return normalized <= 0.03928
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function ratio(foreground, background) {
  const l1 = luminance(foreground);
  const l2 = luminance(background);
  const light = Math.max(l1, l2);
  const dark = Math.min(l1, l2);
  return (light + 0.05) / (dark + 0.05);
}

const app = await startApp({ width: 1100, height: 760 });
let failures = 0;

try {
  // 先落到同源页面，localStorage 才可写。
  await app.navigate(`${app.base}/#/`);
  for (const mode of ["light", "dark"]) {
    await app.setTheme(mode);
    await app.navigate(`${app.base}/#/design?mode=${mode}&density=comfortable`);
    const tokens = await app.evaluate(`(() => {
      const style = getComputedStyle(document.documentElement);
      const names = ${JSON.stringify(PAIRS.flatMap(([fg, bg]) => [fg, bg]))};
      const out = {};
      for (const name of names) out[name] = style.getPropertyValue(name).trim();
      return out;
    })()`);

    console.log(`\n[${mode}]`);
    for (const [fg, bg, minimum, label] of PAIRS) {
      const foreground = parseColor(tokens[fg] ?? "");
      const background = parseColor(tokens[bg] ?? "");
      if (!foreground || !background) {
        console.log(`FAIL  ${label}: 无法解析 ${fg}=${tokens[fg]} / ${bg}=${tokens[bg]}`);
        failures += 1;
        continue;
      }
      const value = ratio(foreground, background);
      const pass = value >= minimum;
      if (!pass) failures += 1;
      console.log(
        `${pass ? "PASS" : "FAIL"}  ${value.toFixed(2)}:1 (>= ${minimum})  ${label}  [${fg} / ${bg}]`,
      );
    }
  }
} finally {
  await app.close();
}

if (failures > 0) {
  console.error(`\n对比度门禁失败：${failures} 项`);
  process.exit(1);
}
console.log("\n对比度门禁通过");
