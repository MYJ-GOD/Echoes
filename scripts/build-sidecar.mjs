#!/usr/bin/env node
// Tauri beforeBuild：构建 sidecar ONEDIR（ADR-011）。dev 不走这里（用 sidecar/.venv）。
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const python =
  process.platform === "win32"
    ? join("sidecar", ".venv", "Scripts", "python.exe")
    : join("sidecar", ".venv", "bin", "python");

if (!existsSync(python)) {
  console.error(
    `[sidecar:build] 缺 ${python}；先 cd sidecar && uv sync --extra dev`,
  );
  process.exit(1);
}

const result = spawnSync(
  python,
  [join("sidecar", "scripts", "build_sidecar.py")],
  { stdio: "inherit" },
);
process.exit(result.status ?? 1);
