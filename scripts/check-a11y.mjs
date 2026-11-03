#!/usr/bin/env node
/**
 * 可访问性门禁：用 axe-core 扫主壳、设置窗口与设计沙盒。
 * 用法：npm run check:a11y
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { startApp, root } from "./lib/cdp.mjs";

const ROUTES = [
  ["chat", "/"],
  ["history", "/history"],
  ["memory", "/memory"],
  ["memory-graph", "/memory?demo=1&graph=1"],
  ["voice", "/voice"],
  ["about", "/about"],
  ["settings", "/settings"],
  ["design", "/design"],
];

const axeSource = readFileSync(
  join(root, "node_modules", "axe-core", "axe.min.js"),
  "utf8",
);

const app = await startApp({ width: 1100, height: 760 });
const failures = [];

try {
  await app.navigate(`${app.base}/#/`);
  for (const theme of ["light", "dark"]) {
    await app.setTheme(theme);
    for (const [name, path] of ROUTES) {
      const url =
        name === "design"
          ? `${app.base}/#${path}?mode=${theme}&density=comfortable`
          : `${app.base}/#${path}`;
      await app.navigate(url);
      await app.evaluate(axeSource);
      const result = await app.evaluate(`axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] }
      }).then((report) => ({
        violations: report.violations.map((violation) => ({
          id: violation.id,
          impact: violation.impact,
          help: violation.help,
          nodes: violation.nodes.slice(0, 4).map((node) => ({
            target: node.target,
            summary: node.failureSummary,
          })),
        })),
      }))`);

      const serious = result.violations.filter(
        (violation) =>
          violation.impact === "serious" || violation.impact === "critical",
      );
      if (serious.length > 0) {
        failures.push({ theme, name, violations: serious });
        console.log(`\nFAIL ${theme} / ${name}`);
        for (const violation of serious) {
          console.log(`  [${violation.impact}] ${violation.id}: ${violation.help}`);
          for (const node of violation.nodes) {
            console.log(`    - ${node.target.join(" ")}`);
          }
        }
      } else {
        console.log(`PASS ${theme} / ${name}`);
      }
    }
  }
} finally {
  await app.close();
}

if (failures.length > 0) {
  console.error(`\naxe 门禁失败：${failures.length} 个页面/主题组合`);
  process.exit(1);
}
console.log("\naxe 门禁通过");
