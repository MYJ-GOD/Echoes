#!/usr/bin/env node
/**
 * 记忆图谱布局基准：只测 d3-force 的 CPU 时间，不含 Canvas 绘制。
 * 参数与 MemoryGraph.vue 保持一致。
 * 用法：node scripts/bench-memory-graph.mjs
 */
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
} from "d3-force";

const WIDTH = 900;
const HEIGHT = 650;
const TICKS = 300;

function build(nodes, links) {
  return forceSimulation(nodes)
    .force(
      "link",
      forceLink(links)
        .id((node) => node.id)
        .distance((link) => (link.kind === "co-used" ? 110 : 78))
        .strength((link) => (link.kind === "co-used" ? 0.45 : 0.2)),
    )
    .force("charge", forceManyBody().strength(-220).distanceMax(800))
    .force(
      "collide",
      forceCollide().radius((node) => 5 + Math.min(node.degree, 10) + 7),
    )
    .force("center", forceCenter(WIDTH / 2, HEIGHT / 2));
}

function run(count) {
  const nodes = Array.from({ length: count }, (_, index) => ({
    id: `n${index}`,
    degree: 0,
  }));
  const links = [];
  for (let index = 0; index < count - 1; index += 1) {
    links.push({
      source: `n${index}`,
      target: `n${index + 1}`,
      kind: "same-session",
    });
    nodes[index].degree += 1;
    nodes[index + 1].degree += 1;
    if (index + 5 < count) {
      links.push({
        source: `n${index}`,
        target: `n${index + 5}`,
        kind: "co-used",
      });
      nodes[index].degree += 1;
      nodes[index + 5].degree += 1;
    }
  }

  const simulation = build(nodes, links);
  simulation.stop();

  const started = performance.now();
  for (let tick = 0; tick < TICKS; tick += 1) simulation.tick();
  const total = performance.now() - started;

  console.log(
    `${String(count).padStart(3)} 节点 / ${String(links.length).padStart(3)} 边：` +
      `${TICKS} tick ${total.toFixed(1)}ms，` +
      `单 tick ${(total / TICKS).toFixed(2)}ms`,
  );
  return total;
}

console.log("记忆图谱力导向布局基准（无渲染）");
const results = [50, 100, 200, 300, 500].map(run);
const worst = Math.max(...results);
console.log(
  worst < 800
    ? `\n通过：最慢一组 ${worst.toFixed(0)}ms（一次性布局）`
    : `\n偏慢：最慢一组 ${worst.toFixed(0)}ms`,
);
