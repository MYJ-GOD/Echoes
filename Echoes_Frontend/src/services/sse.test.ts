import { describe, it, expect, vi, afterEach } from "vitest";
import { streamSSE } from "./sse";

/**
 * streamSSE 单元测试。
 * 保护本次修复：
 *  - data 行解析用 startsWith("data: ")，不再用 includes（避免误匹配）
 *  - 支持 AbortSignal 取消，signal 会透传给 fetch
 */

/** 把可迭代的字符串块包装成一个流式 Response 的 fetch mock。 */
function mockFetchStreaming(chunks: string[]) {
  return vi.fn(async (_url: string, init?: RequestInit) => {
    // 若传入已 abort 的 signal，模拟 fetch 抛 AbortError
    if (init?.signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    const encoder = new TextEncoder();
    let i = 0;
    const body = {
      getReader() {
        return {
          async read() {
            if (i < chunks.length) {
              const value = encoder.encode(chunks[i]);
              i += 1;
              return { value, done: false };
            }
            return { value: undefined, done: true };
          }
        };
      }
    };
    return { ok: true, status: 200, body } as unknown as Response;
  });
}

async function collect(gen: AsyncGenerator<string>): Promise<string[]> {
  const out: string[] = [];
  for await (const item of gen) out.push(item);
  return out;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("streamSSE 解析", () => {
  it("解析单个 data 事件", async () => {
    vi.stubGlobal("fetch", mockFetchStreaming(["data: hello\n\n"]));
    const result = await collect(streamSSE("/x", { method: "POST" }));
    expect(result).toEqual(["hello"]);
  });

  it("解析跨多个网络块拆分的事件", async () => {
    // 一个 SSE 帧被拆到两个 read() 里
    vi.stubGlobal("fetch", mockFetchStreaming(["data: hel", "lo\n\ndata: world\n\n"]));
    const result = await collect(streamSSE("/x", { method: "POST" }));
    expect(result).toEqual(["hello", "world"]);
  });

  it("处理结尾无双换行的残留 buffer", async () => {
    vi.stubGlobal("fetch", mockFetchStreaming(["data: tail-only"]));
    const result = await collect(streamSSE("/x", { method: "POST" }));
    expect(result).toEqual(["tail-only"]);
  });

  it("只产出 data: 行，忽略 event:/id: 等其它 SSE 字段行", async () => {
    vi.stubGlobal("fetch", mockFetchStreaming(["event: message\nid: 42\ndata: real\n\n"]));
    const result = await collect(streamSSE("/x", { method: "POST" }));
    expect(result).toEqual(["real"]);
  });

  it("非 2xx 响应抛错", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 500, body: null }) as unknown as Response)
    );
    await expect(collect(streamSSE("/x", { method: "POST" }))).rejects.toThrow(
      /SSE request failed: 500/
    );
  });
});

describe("streamSSE 取消", () => {
  it("signal 被透传给 fetch", async () => {
    const fetchMock = mockFetchStreaming(["data: x\n\n"]);
    vi.stubGlobal("fetch", fetchMock);
    const controller = new AbortController();
    await collect(streamSSE("/x", { method: "POST" }, controller.signal));

    const passedInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(passedInit.signal).toBe(controller.signal);
  });

  it("已 abort 的 signal 会让流立即抛 AbortError", async () => {
    vi.stubGlobal("fetch", mockFetchStreaming(["data: x\n\n"]));
    const controller = new AbortController();
    controller.abort();
    await expect(
      collect(streamSSE("/x", { method: "POST" }, controller.signal))
    ).rejects.toThrow(/Aborted/);
  });
});
