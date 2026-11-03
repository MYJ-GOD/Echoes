/**
 * 窗口几何记忆：尺寸 + 位置 + 最大化。
 *
 * 存 localStorage（纯本机展示状态，不进 sidecar 契约），无 Tauri 运行时整段跳过。
 * 坐标一律用物理像素：`outerPosition/outerSize` 给的是物理值，回填时也走
 * `PhysicalPosition/PhysicalSize`，避免 100% / 150% 缩放下越存越偏。
 */
import {
  availableMonitors,
  getCurrentWindow,
  PhysicalPosition,
  PhysicalSize,
} from "@tauri-apps/api/window";

import { isTauriRuntime } from "./ipc";

const KEY = "echoes.window";
const MIN_W = 640;
const MIN_H = 480;
/** 保存/回填时要求至少这么多像素落在某块屏幕内，防止拔掉副屏后窗口跑到看不见的地方 */
const VISIBLE_MARGIN = 48;

interface SavedGeometry {
  x: number;
  y: number;
  w: number;
  h: number;
  max: boolean;
}

function read(): SavedGeometry | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<SavedGeometry>;
    const nums = [parsed.x, parsed.y, parsed.w, parsed.h];
    if (nums.some((n) => typeof n !== "number" || !Number.isFinite(n))) {
      return null;
    }
    if ((parsed.w as number) < MIN_W || (parsed.h as number) < MIN_H) return null;
    return {
      x: parsed.x as number,
      y: parsed.y as number,
      w: parsed.w as number,
      h: parsed.h as number,
      max: parsed.max === true,
    };
  } catch {
    return null;
  }
}

function write(geometry: SavedGeometry): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(geometry));
  } catch {
    // 存储不可用：本次会话不记忆
  }
}

/** 上次的窗口是否还落在某块屏幕的可视范围内。 */
async function isOnScreen(g: SavedGeometry): Promise<boolean> {
  const monitors = await availableMonitors();
  if (monitors.length === 0) return true; // 拿不到屏幕信息时按信任处理
  return monitors.some((m) => {
    const mx = m.position.x;
    const my = m.position.y;
    const mw = m.size.width;
    const mh = m.size.height;
    return (
      g.x + g.w > mx + VISIBLE_MARGIN &&
      g.x < mx + mw - VISIBLE_MARGIN &&
      g.y + g.h > my + VISIBLE_MARGIN &&
      g.y < my + mh - VISIBLE_MARGIN
    );
  });
}

export async function restoreWindowGeometry(): Promise<void> {
  if (!isTauriRuntime()) return;
  const saved = read();
  if (!saved) return;
  const win = getCurrentWindow();
  try {
    const w = Math.max(MIN_W, Math.round(saved.w));
    const h = Math.max(MIN_H, Math.round(saved.h));
    await win.setSize(new PhysicalSize(w, h));
    if (await isOnScreen({ ...saved, w, h })) {
      await win.setPosition(
        new PhysicalPosition(Math.round(saved.x), Math.round(saved.y))
      );
    }
    if (saved.max) await win.maximize();
  } catch {
    // 回填失败就用 tauri.conf 里的默认几何，不影响使用
  }
}

/**
 * 订阅尺寸/位置变化并防抖落盘。返回退订函数。
 * 最大化时只记 `max=true`，不覆盖「还原后」的正常几何。
 */
export async function trackWindowGeometry(): Promise<() => void> {
  if (!isTauriRuntime()) return () => {};
  const win = getCurrentWindow();
  let timer: number | null = null;

  const flush = async (): Promise<void> => {
    try {
      const max = await win.isMaximized();
      const prev = read();
      if (max) {
        if (prev) write({ ...prev, max: true });
        return;
      }
      const pos = await win.outerPosition();
      const size = await win.outerSize();
      write({ x: pos.x, y: pos.y, w: size.width, h: size.height, max: false });
    } catch {
      // 窗口正在销毁等情况：忽略
    }
  };

  const schedule = (): void => {
    if (timer !== null) window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      timer = null;
      void flush();
    }, 400);
  };

  const unMoved = await win.onMoved(schedule);
  const unResized = await win.onResized(schedule);

  return () => {
    unMoved();
    unResized();
    if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }
  };
}
