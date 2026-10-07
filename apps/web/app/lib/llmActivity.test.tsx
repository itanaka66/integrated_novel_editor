import { describe, it, expect, afterEach, vi } from "vitest";
import { beginActivity, endActivity, getActivities } from "./llmActivity";
import { api } from "./api";

afterEach(() => {
  for (const a of getActivities()) endActivity(a.id);
  vi.restoreAllMocks();
});

describe("llmActivity", () => {
  it("ignores endpoints that don't wait on an LLM", () => {
    expect(beginActivity("GET", "/projects")).toBeNull();
    expect(beginActivity("POST", "/projects", { name: "x" })).toBeNull();
    expect(getActivities()).toHaveLength(0);
  });

  it("labels /ai/generate by its mode, ignoring any query string", () => {
    const id = beginActivity("POST", "/ai/generate?x=1", { mode: "summary" });
    expect(id).not.toBeNull();
    expect(getActivities()[0].label).toBe("要約しています");
    endActivity(id);
    expect(getActivities()).toHaveLength(0);
  });

  it("tracks overlapping calls independently", () => {
    const a = beginActivity("POST", "/continuity/check");
    const b = beginActivity("POST", "/projects/3/chat");
    expect(getActivities()).toHaveLength(2);
    endActivity(a);
    expect(getActivities().map((x) => x.id)).toEqual([b]);
  });
});

describe("api() integration", () => {
  const originalFetch = global.fetch;
  afterEach(() => { global.fetch = originalFetch; });

  it("registers an LLM call while pending and clears it when it resolves", async () => {
    let release!: () => void;
    global.fetch = vi.fn().mockReturnValue(
      new Promise((resolve) => { release = () => resolve({ status: 200, json: () => Promise.resolve({ ok: 1 }) }); }),
    );
    const p = api("/ai/generate", { method: "POST", body: JSON.stringify({ mode: "continue" }) });
    expect(getActivities().map((a) => a.label)).toEqual(["続きを書いています"]);
    release();
    await p;
    expect(getActivities()).toHaveLength(0);
  });

  it("clears the activity even when the request fails", async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(api("/continuity/check", { method: "POST" })).rejects.toThrow();
    expect(getActivities()).toHaveLength(0);
  });
});
