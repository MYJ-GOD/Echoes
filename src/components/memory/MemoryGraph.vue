<script setup lang="ts">
/**
 * 记忆关系图谱：Canvas 渲染 + d3-force 布局。
 *
 * 边只来自真实数据：同一轮回复共被引用（co-used）或同一次会话提取
 * （same-session）。没有边时不伪造关系，直接显示孤点。
 */
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import type { MemoryGraphEdge, MemoryGraphNode } from "../../lib/ipc";

const props = withDefaults(
  defineProps<{
    nodes: MemoryGraphNode[];
    edges: MemoryGraphEdge[];
    selectedId?: string;
    loading?: boolean;
  }>(),
  { selectedId: "", loading: false },
);

const emit = defineEmits<{ select: [id: string] }>();

interface SimNode extends MemoryGraphNode, SimulationNodeDatum {}
interface SimLink extends SimulationLinkDatum<SimNode> {
  kind: MemoryGraphEdge["kind"];
  weight: number;
}

interface Palette {
  edge: string;
  ink: string;
  ink2: string;
  ink3: string;
  bg: string;
  accent: string;
  signal: string;
  warn: string;
}

const wrap = ref<HTMLDivElement | null>(null);
const canvas = ref<HTMLCanvasElement | null>(null);

let ctx: CanvasRenderingContext2D | null = null;
let simulation: Simulation<SimNode, SimLink> | null = null;
let simNodes: SimNode[] = [];
let simLinks: SimLink[] = [];
let adjacency = new Map<string, Set<string>>();
let width = 0;
let height = 0;
let hoverId = "";
let dragging: SimNode | null = null;
let panning = false;
let moved = false;
let last = { x: 0, y: 0 };
let resizeObserver: ResizeObserver | null = null;
let skinObserver: MutationObserver | null = null;
const transform = { x: 0, y: 0, k: 1 };
let palette: Palette = {
  edge: "#677066",
  ink: "#1b1e1b",
  ink2: "#535a54",
  ink3: "#677066",
  bg: "#f1f1ec",
  accent: "#2f5d50",
  signal: "#b4532f",
  warn: "#8a5a1d",
};

const nodeCount = computed(() => props.nodes.length);
const edgeCount = computed(() => props.edges.length);

const categoryColor: Record<string, keyof Palette> = {
  preference: "accent",
  identity: "signal",
  event: "warn",
  other: "ink3",
};

const legend = computed(() => {
  const seen = new Set(props.nodes.map((node) => node.category));
  return (["preference", "identity", "event", "other"] as const)
    .filter((key) => seen.has(key))
    .map((key) => ({
      key,
      color: categoryColor[key],
      label:
        key === "preference"
          ? "偏好"
          : key === "identity"
            ? "人物 / 属性"
            : key === "event"
              ? "事件"
              : "其他",
    }));
});

function readPalette(): void {
  const element = wrap.value;
  if (!element) return;
  const style = getComputedStyle(element);
  const value = (name: string, fallback: string) =>
    style.getPropertyValue(name).trim() || fallback;
  palette = {
    edge: value("--ink-3", palette.edge),
    ink: value("--ink", palette.ink),
    ink2: value("--ink-2", palette.ink2),
    ink3: value("--ink-3", palette.ink3),
    bg: value("--bg", palette.bg),
    accent: value("--accent", palette.accent),
    signal: value("--signal", palette.signal),
    warn: value("--warn", palette.warn),
  };
}

function colorOf(node: SimNode): string {
  const key = categoryColor[node.category] ?? "ink3";
  return palette[key];
}

function radius(node: SimNode): number {
  return 5 + Math.min(node.degree, 10);
}

function truncate(text: string, length: number): string {
  return text.length > length ? `${text.slice(0, length)}…` : text;
}

function buildAdjacency(): void {
  adjacency = new Map();
  for (const edge of props.edges) {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, new Set());
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, new Set());
    adjacency.get(edge.source)?.add(edge.target);
    adjacency.get(edge.target)?.add(edge.source);
  }
}

function resize(): void {
  const element = wrap.value;
  const target = canvas.value;
  if (!element || !target) return;
  const rect = element.getBoundingClientRect();
  width = Math.max(1, rect.width);
  height = Math.max(1, rect.height);
  const dpr = window.devicePixelRatio || 1;
  target.width = Math.round(width * dpr);
  target.height = Math.round(height * dpr);
  target.style.width = `${width}px`;
  target.style.height = `${height}px`;
  ctx = target.getContext("2d");
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}

function draw(): void {
  if (!ctx) return;
  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.translate(transform.x, transform.y);
  ctx.scale(transform.k, transform.k);

  const focus = hoverId || props.selectedId;
  const neighbors = focus ? (adjacency.get(focus) ?? new Set<string>()) : null;

  for (const link of simLinks) {
    const source = link.source as SimNode;
    const target = link.target as SimNode;
    if (typeof source !== "object" || typeof target !== "object") continue;
    const active =
      !focus || source.id === focus || target.id === focus;

    ctx.beginPath();
    ctx.moveTo(source.x ?? 0, source.y ?? 0);
    ctx.lineTo(target.x ?? 0, target.y ?? 0);
    ctx.lineWidth =
      link.kind === "co-used" ? Math.min(1 + link.weight * 0.35, 3) : 1;
    ctx.strokeStyle = link.kind === "co-used" ? palette.edge : palette.ink3;
    ctx.globalAlpha = active ? (link.kind === "co-used" ? 0.5 : 0.28) : 0.06;
    if (link.kind === "same-session") ctx.setLineDash([3, 4]);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.globalAlpha = 1;

  for (const node of simNodes) {
    const x = node.x ?? 0;
    const y = node.y ?? 0;
    const r = radius(node);
    const isFocus = focus === node.id;
    const isNeighbor = neighbors?.has(node.id) ?? false;
    const dim = focus !== "" && !isFocus && !isNeighbor;
    const selected = props.selectedId === node.id;

    ctx.globalAlpha = dim ? 0.24 : 1;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = colorOf(node);
    ctx.fill();

    if (selected || isFocus) {
      ctx.beginPath();
      ctx.arc(x, y, r + 4, 0, Math.PI * 2);
      ctx.strokeStyle = palette.accent;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(x, y, r + 1.5, 0, Math.PI * 2);
    ctx.strokeStyle = palette.bg;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  for (const node of simNodes) {
    if (focus !== node.id && hoverId !== node.id && node.degree < 2) continue;
    const x = node.x ?? 0;
    const y = node.y ?? 0;
    const dim =
      focus !== "" &&
      focus !== node.id &&
      !(neighbors?.has(node.id) ?? false);
    ctx.globalAlpha = dim ? 0.28 : 1;
    ctx.fillStyle = palette.ink2;
    ctx.font =
      '12px "Segoe UI Variable Text", "Microsoft YaHei UI", system-ui, sans-serif';
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const label = truncate(node.fact, 16);
    const labelX = x;
    const labelY = y + radius(node) + 7;
    ctx.lineWidth = 3;
    ctx.strokeStyle = palette.bg;
    ctx.strokeText(label, labelX, labelY);
    ctx.fillText(label, labelX, labelY);
  }

  ctx.restore();
  ctx.globalAlpha = 1;
}

function build(): void {
  simulation?.stop();
  if (!width || !height) {
    resize();
    if (!width || !height) return;
  }
  simNodes = props.nodes.map((node) => ({ ...node }));
  simLinks = props.edges.map((edge) => ({
    source: edge.source,
    target: edge.target,
    kind: edge.kind,
    weight: edge.weight,
  }));
  buildAdjacency();
  resetZoom();

  const linkForce = forceLink<SimNode, SimLink>(simLinks)
    .id((node) => node.id)
    .distance((link) => (link.kind === "co-used" ? 110 : 78))
    .strength((link) => (link.kind === "co-used" ? 0.45 : 0.2));

  simulation = forceSimulation<SimNode>(simNodes)
    .force("link", linkForce)
    .force(
      "charge",
      forceManyBody<SimNode>()
        .strength(-220)
        .distanceMax(Math.max(width, height) * 0.9),
    )
    .force(
      "collide",
      forceCollide<SimNode>()
        .radius((node) => radius(node) + 7)
        .iterations(2),
    )
    .force("center", forceCenter(width / 2, height / 2))
    .on("tick", draw)
    .on("end", draw);

  simulation.alpha(1).restart();
}

function pick(mx: number, my: number): SimNode | null {
  const x = (mx - transform.x) / transform.k;
  const y = (my - transform.y) / transform.k;
  for (let index = simNodes.length - 1; index >= 0; index -= 1) {
    const node = simNodes[index];
    const r = radius(node) + 5;
    const dx = (node.x ?? 0) - x;
    const dy = (node.y ?? 0) - y;
    if (dx * dx + dy * dy <= r * r) return node;
  }
  return null;
}

function localPoint(event: PointerEvent): { x: number; y: number } {
  const rect = canvas.value?.getBoundingClientRect();
  return {
    x: event.clientX - (rect?.left ?? 0),
    y: event.clientY - (rect?.top ?? 0),
  };
}

function onPointerDown(event: PointerEvent): void {
  const point = localPoint(event);
  last = point;
  moved = false;
  const node = pick(point.x, point.y);
  canvas.value?.setPointerCapture(event.pointerId);
  if (node) {
    dragging = node;
    node.fx = node.x;
    node.fy = node.y;
    simulation?.alphaTarget(0.15).restart();
  } else {
    panning = true;
  }
}

function onPointerMove(event: PointerEvent): void {
  const point = localPoint(event);
  const dx = point.x - last.x;
  const dy = point.y - last.y;
  if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;

  if (dragging) {
    dragging.fx = (point.x - transform.x) / transform.k;
    dragging.fy = (point.y - transform.y) / transform.k;
    draw();
  } else if (panning) {
    transform.x += dx;
    transform.y += dy;
    draw();
  } else {
    const node = pick(point.x, point.y);
    const next = node?.id ?? "";
    if (next !== hoverId) {
      hoverId = next;
      if (canvas.value) {
        canvas.value.style.cursor = next ? "pointer" : "grab";
      }
      draw();
    }
  }
  last = point;
}

function onPointerUp(event: PointerEvent): void {
  const point = localPoint(event);
  const target = dragging ?? pick(point.x, point.y);
  if (dragging) {
    dragging.fx = null;
    dragging.fy = null;
    simulation?.alphaTarget(0);
  }
  dragging = null;
  panning = false;
  canvas.value?.releasePointerCapture(event.pointerId);
  if (!moved && target) emit("select", target.id);
  draw();
}

function onWheel(event: WheelEvent): void {
  event.preventDefault();
  const point = localPoint(event as unknown as PointerEvent);
  const factor = Math.exp(-event.deltaY * 0.0015);
  const next = Math.min(3, Math.max(0.35, transform.k * factor));
  transform.x = point.x - ((point.x - transform.x) / transform.k) * next;
  transform.y = point.y - ((point.y - transform.y) / transform.k) * next;
  transform.k = next;
  draw();
}

function resetView(): void {
  resetZoom();
  simulation?.alpha(0.7).restart();
  draw();
}

/** 节点少时放大一点，别让三两个点缩在画布正中。 */
function resetZoom(): void {
  if (!width || !height) return;
  const k = props.nodes.length <= 12 ? 1.2 : 1;
  transform.k = k;
  transform.x = (width / 2) * (1 - k);
  transform.y = (height / 2) * (1 - k);
}

function zoomBy(factor: number): void {
  const next = Math.min(3, Math.max(0.35, transform.k * factor));
  const cx = width / 2;
  const cy = height / 2;
  transform.x = cx - ((cx - transform.x) / transform.k) * next;
  transform.y = cy - ((cy - transform.y) / transform.k) * next;
  transform.k = next;
  draw();
}

onMounted(() => {
  readPalette();
  resize();
  resizeObserver = new ResizeObserver(() => {
    resize();
    simulation?.force("center", forceCenter(width / 2, height / 2));
    simulation?.alpha(0.3).restart();
  });
  if (wrap.value) resizeObserver.observe(wrap.value);

  const skin = wrap.value?.closest(".ds-skin");
  if (skin) {
    skinObserver = new MutationObserver(() => {
      readPalette();
      draw();
    });
    skinObserver.observe(skin, {
      attributes: true,
      attributeFilter: ["data-mode", "data-density"],
    });
  }

  build();
});

onBeforeUnmount(() => {
  simulation?.stop();
  simulation = null;
  resizeObserver?.disconnect();
  skinObserver?.disconnect();
});

watch(
  () => [props.nodes, props.edges],
  () => {
    hoverId = "";
    build();
  },
);
</script>

<template>
  <div ref="wrap" class="graph">
    <canvas
      ref="canvas"
      class="graph__canvas"
      role="img"
      :aria-label="`记忆关系图谱，${nodeCount} 个节点，${edgeCount} 条连线`"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @pointerleave="hoverId = ''; draw()"
      @wheel.prevent="onWheel"
    ></canvas>

    <div class="graph__hud">
      <span class="graph__stat">{{ nodeCount }} 个节点</span>
      <span class="graph__stat">{{ edgeCount }} 条连线</span>
      <span v-if="loading" class="graph__stat">读取中…</span>
      <span
        v-for="item in legend"
        :key="item.key"
        class="graph__legend"
      >
        <span class="graph__dot" :style="{ background: `var(--${item.color})` }"></span>
        {{ item.label }}
      </span>
      <span class="graph__hint">拖拽节点 · 滚轮缩放</span>
      <button type="button" class="graph__btn" @click="zoomBy(1.25)">
        放大
      </button>
      <button type="button" class="graph__btn" @click="zoomBy(0.8)">
        缩小
      </button>
      <button type="button" class="graph__btn" @click="resetView">
        重置
      </button>
    </div>

    <div v-if="nodeCount === 0" class="graph__empty">
      <p class="graph__empty-title">还没有可以连起来的记忆。</p>
      <p class="graph__empty-desc">
        先在左侧新建几条，或多聊几轮；同一轮回复引用过的记忆会自动连线。
      </p>
    </div>
  </div>
</template>

<style scoped>
.graph {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: var(--bg);
}

.graph__canvas {
  display: block;
  width: 100%;
  height: 100%;
  cursor: grab;
  touch-action: none;
}

.graph__hud {
  position: absolute;
  top: var(--space-2);
  left: var(--space-2);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  max-width: calc(100% - var(--space-4));
  padding: 4px 8px;
  border: 1px solid var(--rule);
  border-radius: var(--radius-control);
  background: var(--surface);
  color: var(--ink-3);
  font-family: var(--font-mono);
  font-size: 10px;
  line-height: 16px;
  pointer-events: auto;
}

.graph__stat {
  color: var(--ink-2);
}

.graph__legend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.graph__dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.graph__hint {
  color: var(--ink-3);
}

.graph__btn {
  padding: 0 6px;
  border: 1px solid var(--rule);
  border-radius: 3px;
  background: var(--surface-2);
  color: var(--ink-2);
  font-family: inherit;
  font-size: 10px;
  line-height: 16px;
  cursor: pointer;
}

.graph__btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.graph__empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-6);
  text-align: center;
  pointer-events: none;
}

.graph__empty-title {
  color: var(--ink);
  font-family: var(--font-voice);
  font-size: var(--text-display);
  line-height: var(--text-display-line);
}

.graph__empty-desc {
  max-width: 38ch;
  color: var(--ink-2);
  font-size: 13px;
  line-height: 20px;
}
</style>
