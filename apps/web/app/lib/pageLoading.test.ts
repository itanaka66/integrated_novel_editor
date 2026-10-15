import { describe, it, expect } from "vitest";
import { beginPageLoad, getPendingLoads, isBlockingLoad } from "./pageLoading";

describe("pageLoading", () => {
  it("blocks only plain GET data reads, never polling or writes", () => {
    expect(isBlockingLoad("GET", "/projects/1/episodes")).toBe(true);
    expect(isBlockingLoad("GET", "/projects?limit=5")).toBe(true);
    expect(isBlockingLoad("POST", "/projects")).toBe(false);
    expect(isBlockingLoad("GET", "/llm/queue")).toBe(false);
    expect(isBlockingLoad("GET", "/background-jobs")).toBe(false);
    expect(isBlockingLoad("GET", "/translate-jobs/3")).toBe(false);
    expect(isBlockingLoad("GET", "/auto-write/7")).toBe(false);
  });

  it("counts in-flight loads and ends each only once", () => {
    const base = getPendingLoads();
    const a = beginPageLoad("GET", "/projects/1/plots")!;
    const b = beginPageLoad("GET", "/projects/1/world")!;
    expect(beginPageLoad("GET", "/llm/queue")).toBeNull();
    expect(getPendingLoads()).toBe(base + 2);
    a(); a();
    expect(getPendingLoads()).toBe(base + 1);
    b();
    expect(getPendingLoads()).toBe(base);
  });
});
