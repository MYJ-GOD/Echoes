#!/usr/bin/env node
/**
 * Echoes · 视觉回归截图（D1）
 *
 * 不新增依赖：Node 24 自带 fetch / WebSocket，用 Edge/Chrome 的 CDP 截图。
 *
 * 用法：
 *   npm run ui:shots
 *   npm run ui:shots -- --theme both --size 1100x760,800x600
 *   npm run ui:shots -- --keep-server
 *
 * 输出：tmp/ui-shots/<YYYY-MM-DD>/<name>.png + manifest.json
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);

function arg(name, fallback) {
  const index = args.indexOf(`--${name}`);
  if (index === -1) return fallback;
  return args[index + 1] ?? fallback;
}

const port = Number(arg("port", "5199"));
const base = `http://127.0.0.1:${port}`;
const keepServer = args.includes("--keep-server");
const showPalette = args.includes("--palette");
const paletteQuery = arg("palette-query", "");
const themeArg = arg("theme", "both");
const sizeArg = arg("size", "1100x760,800x600");
const routeArg = arg("routes", "design");
const settingsSectionArg = arg("settings-section", "");
const memoryDialog = arg("memory-dialog", "");
const outDir = resolve(root, arg("out", join("tmp", "ui-shots", new Date().toISOString().slice(0, 10))));
const profileDir = join(outDir, ".edge-profile");

const routeMap = {
  design: "/design",
  chat: "/",
  "chat-demo": "/?demo=1",
  "palette-demo": "/?palette-demo=1",
  history: "/history",
  memory: "/memory",
  "memory-demo": "/memory?demo=1",
  "memory-graph": "/memory?demo=1&graph=1",
  voice: "/voice",
  about: "/about",
  settings: "/settings",
  "settings-window": "__settings_window__",
};

const routeNames = routeArg
  .split(",")
  .map((item) => item.trim())
  .filter((item) => item && routeMap[item] !== undefined);

const settingsSectionLabels = {
  appearance: "外观",
  persona: "人设",
  engine: "引擎与启动",
  voice: "声音与设备",
  data: "数据与隐私",
  shortcuts: "快捷键",
  about: "关于",
};
const settingsSection =
  settingsSectionArg && settingsSectionLabels[settingsSectionArg]
    ? settingsSectionArg
    : "";

const sizes = sizeArg
  .split(",")
  .map((item) => item.trim())
  .filter(Boolean)
  .map((item) => {
    const [width, height] = item.split("x").map(Number);
    return { width, height };
  })
  .filter((item) => Number.isFinite(item.width) && Number.isFinite(item.height));

const themes = themeArg === "both" ? ["light", "dark"] : [themeArg];

function findBrowser() {
  const candidates =
    process.platform === "win32"
      ? [
          process.env.EDGE_PATH,
          "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
          "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
          "C:/Program Files/Google/Chrome/Application/chrome.exe",
          "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        ]
      : process.platform === "darwin"
        ? [
            process.env.CHROME_PATH,
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
          ]
        : [
            process.env.CHROME_PATH,
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
          ];
  return candidates.find((item) => item && existsSync(item));
}

async function isServerUp() {
  try {
    const response = await fetch(base, { signal: AbortSignal.timeout(1200) });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForServer() {
  for (let index = 0; index < 120; index += 1) {
    if (await isServerUp()) return true;
    await sleep(500);
  }
  return false;
}

function killTree(child) {
  if (!child || child.killed) return;
  if (process.platform === "win32") {
    spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      windowsHide: true,
    });
  } else {
    try {
      process.kill(-child.pid, "SIGTERM");
    } catch {
      child.kill("SIGTERM");
    }
  }
}

async function getFreePort() {
  return new Promise((resolvePromise, reject) => {
    const probe = createServer();
    probe.unref();
    probe.on("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const address = probe.address();
      const port = typeof address === "object" && address ? address.port : 0;
      probe.close(() => resolvePromise(port));
    });
  });
}

async function waitForDebugPort(httpBase) {
  for (let index = 0; index < 100; index += 1) {
    try {
      const response = await fetch(`${httpBase}/json/version`, {
        signal: AbortSignal.timeout(1000),
      });
      if (response.ok) return await response.json();
    } catch {
      // 还没起来
    }
    await sleep(200);
  }
  throw new Error("等待 DevTools 端口超时");
}

async function getPageTarget(httpBase) {
  for (let index = 0; index < 60; index += 1) {
    const response = await fetch(`${httpBase}/json/list`);
    const list = await response.json();
    const page = list.find((item) => item.type === "page");
    if (page) return page;
    await sleep(200);
  }
  throw new Error("没有找到页面 target");
}

function createCdp(wsUrl) {
  const socket = new WebSocket(wsUrl);
  let nextId = 0;
  const pending = new Map();

  socket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    if (!message.id || !pending.has(message.id)) return;
    const { resolve: resolvePromise, reject } = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) reject(new Error(JSON.stringify(message.error)));
    else resolvePromise(message.result);
  };

  const ready = new Promise((resolvePromise, reject) => {
    socket.onopen = resolvePromise;
    socket.onerror = reject;
  });

  function send(method, params = {}) {
    const id = (nextId += 1);
    socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolvePromise, reject) => {
      pending.set(id, { resolve: resolvePromise, reject });
    });
  }

  return { socket, ready, send };
}

async function main() {
  if (sizes.length === 0) throw new Error("--size 需要形如 1100x760,800x600");
  const browserPath = findBrowser();
  if (!browserPath) throw new Error("没有找到 Edge/Chrome，可用 EDGE_PATH 或 CHROME_PATH 指定");

  mkdirSync(outDir, { recursive: true });
  try {
    rmSync(profileDir, { recursive: true, force: true });
  } catch {
    // 上一轮的浏览器可能还没完全退出，换个目录继续。
  }

  let server = null;
  if (!(await isServerUp())) {
    const devCommand = `npm run dev -- --host 127.0.0.1 --port ${port} --strictPort`;
    server = spawn(
      process.platform === "win32" ? "cmd.exe" : "sh",
      process.platform === "win32"
        ? ["/d", "/s", "/c", devCommand]
        : ["-c", devCommand],
      {
        cwd: root,
        stdio: "ignore",
        windowsHide: true,
      },
    );
    if (!(await waitForServer())) {
      killTree(server);
      throw new Error(`开发服务器没有在 ${base} 起来`);
    }
  }

  const debugPort = await getFreePort();
  const debugBase = `http://127.0.0.1:${debugPort}`;
  const browser = spawn(
    browserPath,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${profileDir}`,
      "--hide-scrollbars",
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "ignore"], windowsHide: true },
  );

  const shots = [];
  let cdp = null;
  let browserCdp = null;

  try {
    const versionInfo = await waitForDebugPort(debugBase);
    console.log(`[ui-shot] ${versionInfo.Browser ?? "DevTools"} @ ${debugPort}`);
    browserCdp = createCdp(versionInfo.webSocketDebuggerUrl);
    await browserCdp.ready;
    const target = await getPageTarget(debugBase);
    console.log(`[ui-shot] page target: ${target.url || target.id}`);
    cdp = createCdp(target.webSocketDebuggerUrl);
    await cdp.ready;
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");

    async function evaluate(expression) {
      const result = await cdp.send("Runtime.evaluate", {
        expression,
        awaitPromise: true,
        returnByValue: true,
      });
      if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
      return result.result.value;
    }

    async function navigate(url) {
      // 先回 about:blank，确保 hash-only 跳转也会重新执行 main.ts（读取主题）。
      await cdp.send("Page.navigate", { url: "about:blank" });
      await sleep(80);
      await cdp.send("Page.navigate", { url });
      for (let index = 0; index < 150; index += 1) {
        const state = await evaluate("document.readyState");
        if (state === "complete") break;
        await sleep(100);
      }
      await evaluate("document.fonts.ready.then(() => true)");
      await sleep(700);
    }

    // 先落到同源页面，后面的 localStorage 主题切换才生效。
    await navigate(`${base}/#/`);

    for (const routeName of routeNames) {
      for (const theme of themes) {
        for (const size of sizes) {
          await cdp.send("Emulation.setDeviceMetricsOverride", {
            width: size.width,
            height: size.height,
            deviceScaleFactor: 1,
            mobile: false,
          });

          await evaluate(
            `localStorage.setItem("echoes.theme", ${JSON.stringify(
              theme === "dark" ? "nocturne" : "paper",
            )})`,
          );

          const path = routeMap[routeName];
          const query =
            routeName === "design" ? `?mode=${theme}&density=comfortable` : "";
          const url =
            routeName === "settings-window"
              ? `${base}/#/settings`
              : `${base}/#${path}${query}`;
          const sectionSuffix =
            routeName === "settings-window" && settingsSection
              ? `-${settingsSection}`
              : "";
          const paletteSuffix = showPalette ? "-palette" : "";
          const dialogSuffix = memoryDialog ? `-dialog-${memoryDialog}` : "";
          const name = `${routeName}${sectionSuffix}${paletteSuffix}${dialogSuffix}-${theme}-${size.width}x${size.height}`;
          await navigate(url);

          if (routeName === "memory-demo" && memoryDialog) {
            const label =
              memoryDialog === "edit"
                ? "编辑"
                : memoryDialog === "delete"
                  ? "删除"
                  : memoryDialog;
            await evaluate(`(() => {
              const target = Array.from(document.querySelectorAll("button"))
                .find((item) => item.textContent.trim() === ${JSON.stringify(label)});
              if (target) target.click();
              return Boolean(target);
            })()`);
            await sleep(300);
          }

          if (
            (showPalette && routeName === "chat") ||
            routeName === "palette-demo"
          ) {
            await evaluate(`window.dispatchEvent(new KeyboardEvent("keydown", {
              key: "p", ctrlKey: true, shiftKey: true, bubbles: true
            }))`);
            await sleep(300);
            if (paletteQuery) {
              await evaluate(`(() => {
                const input = document.querySelector(".palette__input");
                if (!input) return false;
                input.value = ${JSON.stringify(paletteQuery)};
                input.dispatchEvent(new Event("input", { bubbles: true }));
                return true;
              })()`);
              await sleep(500);
            }
          }

          if (routeName === "settings-window" && settingsSection) {
            const label = settingsSectionLabels[settingsSection];
            await evaluate(`(() => {
              const target = Array.from(document.querySelectorAll(".settings__nav-item"))
                .find((item) => item.textContent.trim() === ${JSON.stringify(label)});
              if (target) target.click();
              return Boolean(target);
            })()`);
            await sleep(300);
          }

          const { data } = await cdp.send("Page.captureScreenshot", {
            format: "png",
            fromSurface: true,
          });
          writeFileSync(join(outDir, `${name}.png`), Buffer.from(data, "base64"));
          shots.push({
            name,
            route: routeName,
            url,
            width: size.width,
            height: size.height,
            theme,
          });
          console.log(`[ui-shot] ${name}.png`);
        }
      }
    }

    if (routeNames.includes("design")) {
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width: 1100,
        height: 760,
        deviceScaleFactor: 1,
        mobile: false,
      });
      await evaluate(`localStorage.setItem("echoes.theme", "paper")`);
      const compactName = "design-light-1100x760-compact";
      await navigate(`${base}/#/design?mode=light&density=compact`);
      const compact = await cdp.send("Page.captureScreenshot", {
        format: "png",
        fromSurface: true,
      });
      writeFileSync(join(outDir, `${compactName}.png`), Buffer.from(compact.data, "base64"));
      shots.push({
        name: compactName,
        route: "design",
        url: `${base}/#/design?mode=light&density=compact`,
        width: 1100,
        height: 760,
        theme: "light",
        density: "compact",
      });
      console.log(`[ui-shot] ${compactName}.png`);
    }

    writeFileSync(
      join(outDir, "manifest.json"),
      `${JSON.stringify({ generatedAt: new Date().toISOString(), base, shots }, null, 2)}\n`,
    );
    console.log(`[ui-shot] 输出目录：${outDir}`);
  } finally {
    try {
      await browserCdp?.send("Browser.close");
    } catch {
      // ignore
    }
    try {
      cdp?.socket.close();
      browserCdp?.socket.close();
    } catch {
      // ignore
    }
    killTree(browser);
    if (server && !keepServer) killTree(server);
    await sleep(800);
    try {
      rmSync(profileDir, { recursive: true, force: true });
    } catch (error) {
      console.warn(`[ui-shot] 清理浏览器 profile 失败（可忽略）：${error.message}`);
    }
  }
}

main().catch((error) => {
  console.error(`[ui-shot] ${error.stack || error.message}`);
  process.exit(1);
});
