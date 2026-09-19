import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { API_ROOT, checkSession, clearAuth, getAuth, logout, setAuth } from "./api";

describe("API_ROOT", () => {
  it("strips /api/v1 off NEXT_PUBLIC_API_URL's default", () => {
    // The default (no NEXT_PUBLIC_API_URL set) is http://localhost:8000/api/v1
    // — editor_common.oauth's routes live on the bare API origin instead.
    expect(API_ROOT).toBe("http://localhost:8000");
  });
});

describe("checkSession / logout", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    clearAuth();
    localStorage.clear();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("checkSession returns true when the API call succeeds (valid session cookie)", async () => {
    global.fetch = vi.fn().mockResolvedValue({ status: 200, json: () => Promise.resolve([]) });
    expect(await checkSession()).toBe(true);
  });

  it("checkSession returns false on a 401 (no session, no stored Basic Auth)", async () => {
    global.fetch = vi.fn().mockResolvedValue({ status: 401 });
    expect(await checkSession()).toBe(false);
  });

  it("checkSession returns false on a network error rather than throwing", async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(checkSession()).resolves.toBe(false);
  });

  it("logout clears the stored Basic Auth pair and hits /auth/logout with credentials", async () => {
    setAuth("admin", "novel");
    expect(getAuth()).not.toBeNull();
    global.fetch = vi.fn().mockResolvedValue({ status: 200 });

    await logout();

    expect(getAuth()).toBeNull();
    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/auth/logout",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("logout still clears local state even if the network call fails", async () => {
    setAuth("admin", "novel");
    global.fetch = vi.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(logout()).resolves.toBeUndefined();
    expect(getAuth()).toBeNull();
  });
});
