import { describe, it, expect, beforeEach } from "vitest";
import { clearDashboardCache, loadDashboardCache, saveDashboardCache } from "./dashboardCache";

describe("dashboardCache", () => {
  beforeEach(() => localStorage.clear());

  it("round-trips the cards and clears on demand", () => {
    expect(loadDashboardCache()).toBeNull();
    saveDashboardCache({ projects: [{ id: 1, name: "作品", description: "", genre: "", rules: "" }], counts: { "1": 12 } });
    expect(loadDashboardCache()?.counts["1"]).toBe(12);
    clearDashboardCache();
    expect(loadDashboardCache()).toBeNull();
  });

  it("ignores a corrupt or wrongly-shaped cache", () => {
    localStorage.setItem("ine-dashboard-cache-v1", "{not json");
    expect(loadDashboardCache()).toBeNull();
    localStorage.setItem("ine-dashboard-cache-v1", JSON.stringify({ projects: "x" }));
    expect(loadDashboardCache()).toBeNull();
  });
});
