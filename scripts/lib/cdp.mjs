import { spawn } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";

export const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");

export function findBrowser() {
  const candidates =
    process.platform === "win32"
      ? [
          process.env.EDGE_PATH,
          "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
          "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
          "C:/Program Files/Google/Chrome/Application/chrome.exe",
        ]
      : process.platform === "darwin"
        ? [
            process.env.CHROME_PATH,
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
          ]
        : [
            process.env.CHROME_PATH,
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
          ];
  return candidates.find((item) => item && existsSync(item));
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

async function isServerUp(base) {
  try {
    const response = await fetch(base, { signal: AbortSignal.timeout(1200) });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForServer(base) {
  for (let index = 0; index < 120; index += 1) {
    if (await isServerUp(base)) return true;
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

export async function startApp({ port = 5199, width = 1100, height = 760 } = {}) {
  const base = `http://127.0.0.1:${port}`;
  const browserPath = findBrowser();
  if (!browserPath) throw new Error("没有找到 Edge/Chrome");

  const profileDir = join(root, "tmp", `a11y-profile-${process.pid}`);
  mkdirSync(join(root, "tmp"), { recursive: true });
  rmSync(profileDir, { recursive: true, force: true });

  let server = null;
  if (!(await isServerUp(base))) {
    const devCommand = `npm run dev -- --host 127.0.0.1 --port ${port} --strictPort`;
    server = spawn(
      process.platform === "win32" ? "cmd.exe" : "sh",
      process.platform === "win32"
        ? ["/d", "/s", "/c", devCommand]
        : ["-c", devCommand],
      { cwd: root, stdio: "ignore", windowsHide: true },
    );
    if (!(await waitForServer(base))) {
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

  let browserCdp = null;
  let cdp = null;
  try {
    const version = await waitForDebugPort(debugBase);
    browserCdp = createCdp(version.webSocketDebuggerUrl);
    await browserCdp.ready;
    const target = await getPageTarget(debugBase);
    cdp = createCdp(target.webSocketDebuggerUrl);
    await cdp.ready;
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width,
      height,
      deviceScaleFactor: 1,
      mobile: false,
    });

    async function evaluate(expression) {
      const result = await cdp.send("Runtime.evaluate", {
        expression,
        awaitPromise: true,
        returnByValue: true,
      });
      if (result.exceptionDetails) {
        throw new Error(JSON.stringify(result.exceptionDetails));
      }
      return result.result.value;
    }

    async function navigate(url) {
      await cdp.send("Page.navigate", { url: "about:blank" });
      await sleep(80);
      await cdp.send("Page.navigate", { url });
      for (let index = 0; index < 150; index += 1) {
        if ((await evaluate("document.readyState")) === "complete") break;
        await sleep(100);
      }
      await evaluate("document.fonts.ready.then(() => true)");
      await sleep(500);
    }

    async function setTheme(theme) {
      await evaluate(
        `localStorage.setItem("echoes.theme", ${JSON.stringify(
          theme === "dark" ? "nocturne" : "paper",
        )})`,
      );
    }

    async function setViewport(nextWidth, nextHeight) {
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width: nextWidth,
        height: nextHeight,
        deviceScaleFactor: 1,
        mobile: false,
      });
    }

    async function close() {
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
      if (server) killTree(server);
      await sleep(600);
      try {
        rmSync(profileDir, { recursive: true, force: true });
      } catch {
        // profile 可能还被锁，忽略
      }
    }

    return { base, cdp, evaluate, navigate, setTheme, setViewport, close };
  } catch (error) {
    await sleep(200);
    killTree(browser);
    if (server) killTree(server);
    throw error;
  }
}
