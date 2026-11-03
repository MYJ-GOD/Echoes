#!/usr/bin/env node
/**
 * 记忆页专项门禁：三栏布局、搜索、折叠、新建/批量/合并、图谱切换、窄屏。
 * 用法：npm run check:memory
 */
import { startApp } from "./lib/cdp.mjs";

const app = await startApp({ width: 1100, height: 760 });
const results = [];
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function check(name, pass, detail = "") {
  results.push({ name, pass: Boolean(pass), detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? `  (${detail})` : ""}`);
}

async function clickText(text, selector = "button") {
  return app.evaluate(`(() => {
    const target = Array.from(document.querySelectorAll(${JSON.stringify(selector)}))
      .find((item) => item.textContent.trim() === ${JSON.stringify(text)});
    if (!target) return false;
    target.click();
    return true;
  })()`);
}

try {
  await app.navigate(`${app.base}/#/memory?demo=1`);
  await sleep(600);

  // 1. 三栏骨架
  const layout = await app.evaluate(`(() => {
    const pick = (selector) => document.querySelector(selector);
    return {
      rail: Boolean(pick(".memory__rail")),
      detail: Boolean(pick(".memory__detail")),
      related: Boolean(pick(".memory__related")),
      columns: getComputedStyle(pick(".memory")).gridTemplateColumns,
      items: document.querySelectorAll(".mem-item").length,
    };
  })()`);
  check(
    "三栏骨架（左树 / 中详情 / 右关联）",
    layout.rail && layout.detail && layout.related && layout.items === 3,
    JSON.stringify(layout),
  );

  // 2. 默认选中第一条，详情可见
  const detail = await app.evaluate(`(() => ({
    fact: document.querySelector(".mem-detail__fact")?.textContent.trim() ?? "",
    props: document.querySelectorAll(".mem-props > div").length,
    active: document.querySelector(".mem-item.is-active")?.dataset.memoryId ?? "",
  }))()`);
  check(
    "默认选中首条并显示详情与属性",
    detail.active === "demo-1" &&
      detail.fact.includes("爵士") &&
      detail.props === 5,
    JSON.stringify(detail),
  );

  // 3. 搜索过滤
  await app.evaluate(`(() => {
    const input = document.querySelector(".memory__rail-search input");
    input.value = "猫";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  })()`);
  await sleep(350);
  const searched = await app.evaluate(
    `document.querySelectorAll(".mem-item").length`,
  );
  check("搜索「猫」只剩一条", searched === 1, `rows=${searched}`);

  await app.evaluate(`(() => {
    const input = document.querySelector(".memory__rail-search input");
    input.value = "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
  })()`);
  await sleep(300);

  // 4. 分组折叠
  await app.evaluate(`document.querySelector(".mem-group__head")?.click()`);
  await sleep(300);
  const collapsed = await app.evaluate(`(() => {
    const head = document.querySelector(".mem-group__head");
    const list = head.parentElement.querySelector(".mem-list");
    return {
      expanded: head.getAttribute("aria-expanded"),
      hidden: getComputedStyle(list).display === "none",
    };
  })()`);
  check(
    "分组头可折叠",
    collapsed.expanded === "false" && collapsed.hidden === true,
    JSON.stringify(collapsed),
  );
  await app.evaluate(
    `document.querySelector(".mem-group__head")?.click()`,
  );
  await sleep(200);

  // 5. 新建表单
  await clickText("新建");
  await sleep(300);
  const create = await app.evaluate(`(() => ({
    title: document.querySelector(".mem-form__title")?.textContent.trim() ?? "",
    textarea: Boolean(document.querySelector(".mem-form textarea")),
  }))()`);
  check(
    "新建打开中栏表单",
    create.title === "新建记忆" && create.textarea,
    JSON.stringify(create),
  );
  await clickText("取消");
  await sleep(250);

  // 6. 批量导入表单
  await clickText("批量");
  await sleep(300);
  const bulk = await app.evaluate(
    `document.querySelector(".mem-form__title")?.textContent.trim() ?? ""`,
  );
  check("批量导入打开中栏表单", bulk === "批量导入", bulk);
  await clickText("取消");
  await sleep(250);

  // 7. 合并模式与多选
  await clickText("合并");
  await sleep(350);
  const mergeStart = await app.evaluate(
    `document.querySelectorAll(".mem-item__check").length`,
  );
  await app.evaluate(`(() => {
    const boxes = document.querySelectorAll(".mem-item__check input");
    boxes[0].click();
    boxes[1].click();
  })()`);
  await sleep(350);
  const merge = await app.evaluate(`(() => ({
    checked: document.querySelectorAll(".mem-item__check input:checked").length,
    footer: document.querySelector(".memory__merge")?.textContent.replace(/\\s+/g, " ").trim() ?? "",
  }))()`);
  check(
    "合并模式：行首复选框 + 已选计数",
    mergeStart === 3 && merge.checked === 2 && merge.footer.includes("已选 2 条"),
    JSON.stringify(merge),
  );
  await clickText("退出合并");
  await sleep(300);

  // 8. 图谱切换
  await clickText("图谱");
  await sleep(1200);
  const graph = await app.evaluate(`(() => {
    const canvas = document.querySelector(".graph__canvas");
    const hud = document.querySelector(".graph__hud")?.textContent.replace(/\\s+/g, " ").trim() ?? "";
    return {
      canvas: Boolean(canvas),
      width: canvas?.width ?? 0,
      height: canvas?.height ?? 0,
      hud,
      relatedHidden: !document.querySelector(".memory__related"),
    };
  })()`);
  check(
    "图谱模式：canvas 挂载并铺满中+右栏",
    graph.canvas &&
      graph.width > 300 &&
      graph.height > 300 &&
      graph.hud.includes("3 个节点") &&
      graph.hud.includes("3 条连线") &&
      graph.relatedHidden,
    JSON.stringify(graph),
  );

  // 9. 图谱空态
  await app.navigate(`${app.base}/#/memory?graph=1`);
  await sleep(900);
  const empty = await app.evaluate(`(() => ({
    empty: Boolean(document.querySelector(".graph__empty")),
    text: document.querySelector(".graph__empty-title")?.textContent.trim() ?? "",
  }))()`);
  check(
    "无数据时图谱显示空态",
    empty.empty && empty.text.includes("没有"),
    JSON.stringify(empty),
  );

  // 10. 窄屏隐藏右栏
  await app.navigate(`${app.base}/#/memory?demo=1`);
  await sleep(500);
  await app.setViewport(800, 600);
  await sleep(400);
  const narrow = await app.evaluate(`(() => ({
    display: getComputedStyle(document.querySelector(".memory__related")).display,
    detail: Boolean(document.querySelector(".memory__detail")),
  }))()`);
  check(
    "800×600 隐藏右栏、保留详情",
    narrow.display === "none" && narrow.detail,
    JSON.stringify(narrow),
  );

  // 11. 键盘可以到达记忆条目
  await app.setViewport(1100, 760);
  await app.navigate(`${app.base}/#/memory?demo=1`);
  await sleep(600);
  await app.evaluate(`document.querySelector(".memory__rail-search input")?.focus()`);
  let reached = false;
  const trail = [];
  for (let index = 0; index < 10; index += 1) {
    await app.cdp.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Tab",
      code: "Tab",
      windowsVirtualKeyCode: 9,
    });
    await app.cdp.send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Tab",
      code: "Tab",
      windowsVirtualKeyCode: 9,
    });
    const info = await app.evaluate(`(() => {
      const el = document.activeElement;
      return {
        tag: el?.tagName ?? "",
        cls: typeof el?.className === "string" ? el.className.slice(0, 40) : "",
        text: (el?.textContent ?? "").trim().slice(0, 20),
        inItem: Boolean(el?.closest(".mem-item")),
      };
    })()`);
    trail.push(info);
    if (info.inItem) {
      reached = true;
      break;
    }
  }
  check("Tab 可以到达记忆条目", reached, JSON.stringify(trail));
} finally {
  await app.close();
}

const failed = results.filter((item) => !item.pass);
if (failed.length > 0) {
  console.error(`\n记忆页门禁失败：${failed.length} 项`);
  process.exit(1);
}
console.log("\n记忆页门禁通过");
