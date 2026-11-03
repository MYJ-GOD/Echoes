#!/usr/bin/env node
/**
 * 键盘路径门禁：主壳 Tab、命令面板、设置导航、记忆对话框焦点陷阱/恢复。
 * 用法：npm run check:keys
 */
import { startApp } from "./lib/cdp.mjs";

const app = await startApp({ width: 1100, height: 760 });
const results = [];

function check(name, condition, detail = "") {
  results.push({ name, pass: Boolean(condition), detail });
  console.log(`${condition ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function press(key, code, vk, modifiers = 0) {
  const params = {
    key,
    code,
    windowsVirtualKeyCode: vk,
    nativeVirtualKeyCode: vk,
    modifiers,
  };
  await app.cdp.send("Input.dispatchKeyEvent", { type: "keyDown", ...params });
  await app.cdp.send("Input.dispatchKeyEvent", { type: "keyUp", ...params });
  await sleep(120);
}

async function active() {
  return app.evaluate(`(() => {
    const element = document.activeElement;
    if (!element) return null;
    const style = getComputedStyle(element);
    return {
      tag: element.tagName,
      text: (element.textContent || "").trim().slice(0, 40),
      href: element.getAttribute?.("href") ?? "",
      role: element.getAttribute?.("role") ?? "",
      outlineWidth: style.outlineWidth,
      outlineStyle: style.outlineStyle,
      insideDialog: Boolean(element.closest?.(".ds-dialog")),
      insidePalette: Boolean(element.closest?.(".palette")),
      insideSettingsNav: Boolean(element.closest?.(".settings__nav")),
      insideSettingsTitlebar: Boolean(element.closest?.(".settings__titlebar")),
    };
  })()`);
}

try {
  // 1. 主壳 Tab 顺序与焦点环
  await app.navigate(`${app.base}/#/`);
  await app.evaluate("document.body.focus()");
  await press("Tab", "Tab", 9);
  const first = await active();
  check(
    "主壳第一次 Tab 落在可聚焦控件",
    first?.tag === "A" || first?.tag === "BUTTON",
    JSON.stringify(first),
  );
  check(
    "键盘焦点有可见轮廓",
    Number.parseFloat(first?.outlineWidth ?? "0") >= 1 &&
      first?.outlineStyle !== "none",
    `${first?.outlineWidth} ${first?.outlineStyle}`,
  );

  const tabOrder = [first];
  for (let index = 0; index < 8; index += 1) {
    await press("Tab", "Tab", 9);
    tabOrder.push(await active());
  }
  check(
    "Tab 顺序覆盖侧栏入口",
    tabOrder.some((item) => item?.href === "#/history") &&
      tabOrder.some((item) => item?.href === "#/memory"),
    tabOrder.map((item) => item?.href || item?.text).join(" → "),
  );

  // 2. 命令面板：打开、焦点、关闭后恢复
  await app.evaluate(`document.querySelector('a[href="#/history"]')?.focus()`);
  await press("P", "KeyP", 80, 10);
  await sleep(300);
  const paletteOpen = await active();
  check(
    "Ctrl+Shift+P 打开面板并聚焦输入框",
    paletteOpen?.tag === "INPUT" && paletteOpen?.insidePalette,
    JSON.stringify(paletteOpen),
  );
  await press("Escape", "Escape", 27);
  await sleep(300);
  const restored = await active();
  check(
    "Esc 关闭面板后焦点回到触发前元素",
    restored?.tag === "A" && restored?.href === "#/history",
    JSON.stringify(restored),
  );

  // 3. 命令面板执行命令
  await press("P", "KeyP", 80, 10);
  await sleep(250);
  await app.cdp.send("Input.insertText", { text: "历史" });
  await sleep(350);
  await press("Enter", "Enter", 13);
  await sleep(500);
  const hash = await app.evaluate("location.hash");
  check("命令面板 Enter 执行导航", String(hash).includes("/history"), String(hash));

  // 4. 设置窗口导航键盘：标题栏控件（最小化/关闭）在最前，其后才是分组导航。
  await app.navigate(`${app.base}/#/settings`);
  await app.evaluate("document.body.focus()");
  await press("Tab", "Tab", 9);
  const settingsFirst = await active();
  check(
    "设置窗口第一次 Tab 落在标题栏或分组导航",
    settingsFirst?.tag === "BUTTON" &&
      (settingsFirst?.insideSettingsNav || settingsFirst?.insideSettingsTitlebar),
    JSON.stringify(settingsFirst),
  );
  // 逐次 Tab，直到焦点进入分组导航（Tab 顺序不许跳过导航）。
  let insideNav = null;
  for (let index = 0; index < 6 && !insideNav; index += 1) {
    const current = await active();
    if (current?.insideSettingsNav) {
      insideNav = current;
      break;
    }
    await press("Tab", "Tab", 9);
  }
  check("设置分组导航可由 Tab 到达", insideNav?.tag === "BUTTON", JSON.stringify(insideNav));
  await press("Tab", "Tab", 9);
  const settingsSecond = await active();
  check(
    "设置导航可以继续 Tab",
    settingsSecond?.tag === "BUTTON" && settingsSecond?.insideSettingsNav,
    JSON.stringify(settingsSecond),
  );

  // 5. 记忆对话框：焦点进入、Tab 陷阱、Esc 恢复
  await app.navigate(`${app.base}/#/memory?demo=1`);
  await sleep(400);
  await app.evaluate(`(() => {
    const button = Array.from(document.querySelectorAll("button"))
      .find((item) => item.textContent.trim() === "编辑");
    if (!button) return false;
    window.__editButton = button;
    button.focus();
    button.click();
    return true;
  })()`);
  await sleep(400);
  const dialogFocus = await active();
  check(
    "编辑对话框打开后焦点进入对话框",
    dialogFocus?.insideDialog === true,
    JSON.stringify(dialogFocus),
  );
  for (let index = 0; index < 6; index += 1) {
    await press("Tab", "Tab", 9);
  }
  const trapped = await active();
  check(
    "Tab 被锁定在对话框内",
    trapped?.insideDialog === true,
    JSON.stringify(trapped),
  );
  await press("Escape", "Escape", 27);
  await sleep(350);
  const afterDialog = await app.evaluate(
    "document.activeElement === window.__editButton",
  );
  const dialogGone = await app.evaluate("!document.querySelector('.ds-dialog')");
  check(
    "Esc 关闭对话框并恢复触发按钮焦点",
    afterDialog === true && dialogGone === true,
    `focus=${afterDialog} gone=${dialogGone}`,
  );
} finally {
  await app.close();
}

const failed = results.filter((item) => !item.pass);
if (failed.length > 0) {
  console.error(`\n键盘门禁失败：${failed.length} 项`);
  process.exit(1);
}
console.log("\n键盘门禁通过");
