#!/usr/bin/env node
/**
 * 13.2-1：IPC 类型生成/校验入口（跨平台薄壳）。
 *
 * 真正的生成逻辑在 sidecar/echoes_sidecar/ipc/tsexport.py——单一来源是 pydantic
 * 模型，本脚本只负责「找到能 import echoes_sidecar 的 python」并把参数转过去。
 *
 *   node scripts/gen-ipc-types.mjs            # 写回 src/lib/ipc_types.ts
 *   node scripts/gen-ipc-types.mjs --check    # 只比对（CI / npm run ipc:check）
 *
 * 解释器优先级：ECHOES_PYTHON 环境变量 → sidecar/.venv → PATH 里的 python/py。
 * 找不到可用解释器就非零退出（报错而非静默跳过——漂移守护不能假装通过）。
 */
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sidecarDir = join(repoRoot, "sidecar");
const outFile = join(repoRoot, "src", "lib", "ipc_types.ts");
const checkOnly = process.argv.includes("--check");

const looksLikePath = (cmd) => cmd.includes("/") || cmd.includes("\\");

function candidates() {
  const list = [];
  const env = process.env.ECHOES_PYTHON;
  if (env) list.push({ cmd: env, args: [] });
  if (process.platform === "win32") {
    list.push({ cmd: join(sidecarDir, ".venv", "Scripts", "python.exe"), args: [] });
    list.push({ cmd: "py", args: ["-3"] });
  } else {
    list.push({ cmd: join(sidecarDir, ".venv", "bin", "python"), args: [] });
  }
  list.push({ cmd: "python3", args: [] });
  list.push({ cmd: "python", args: [] });
  return list.filter((c) => !looksLikePath(c.cmd) || existsSync(c.cmd));
}

function probe(interpreter) {
  const result = spawnSync(
    interpreter.cmd,
    [...interpreter.args, "-c", "import pydantic, echoes_sidecar.ipc.tsexport"],
    { cwd: sidecarDir, encoding: "utf8" }
  );
  return result.status === 0;
}

const interpreter = candidates().find(probe);
if (!interpreter) {
  console.error(
    "找不到能 import echoes_sidecar 的 python。\n" +
      "请先 `cd sidecar && uv sync`（或设置 ECHOES_PYTHON 指向已装依赖的解释器）。"
  );
  process.exit(1);
}

const args = [
  ...interpreter.args,
  "-m",
  "echoes_sidecar.ipc.tsexport",
  "--out",
  outFile,
  ...(checkOnly ? ["--check"] : []),
];
const run = spawnSync(interpreter.cmd, args, { cwd: sidecarDir, stdio: "inherit" });
process.exit(run.status ?? 1);
