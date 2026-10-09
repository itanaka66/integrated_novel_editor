import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useIdleLogout, IDLE_LIMIT_MS } from "./useIdleLogout";

describe("useIdleLogout", () => {
  beforeEach(() => { vi.useFakeTimers(); localStorage.clear(); });
  afterEach(() => { vi.useRealTimers(); });

  it("logs out after 10 minutes without input", () => {
    const onIdle = vi.fn();
    renderHook(() => useIdleLogout(true, onIdle));
    act(() => { vi.advanceTimersByTime(IDLE_LIMIT_MS - 30000); });
    expect(onIdle).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(60000); });
    expect(onIdle).toHaveBeenCalled();
  });

  it("input resets the countdown", () => {
    const onIdle = vi.fn();
    renderHook(() => useIdleLogout(true, onIdle));
    act(() => { vi.advanceTimersByTime(IDLE_LIMIT_MS - 60000); });
    act(() => { window.dispatchEvent(new Event("keydown")); });
    act(() => { vi.advanceTimersByTime(IDLE_LIMIT_MS - 60000); });
    expect(onIdle).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(120000); });
    expect(onIdle).toHaveBeenCalled();
  });

  it("activity in another tab (shared timestamp) keeps this one signed in", () => {
    const onIdle = vi.fn();
    renderHook(() => useIdleLogout(true, onIdle));
    act(() => { vi.advanceTimersByTime(IDLE_LIMIT_MS - 60000); });
    localStorage.setItem("ine-last-activity", String(Date.now()));
    act(() => { vi.advanceTimersByTime(IDLE_LIMIT_MS - 60000); });
    expect(onIdle).not.toHaveBeenCalled();
  });

  it("does nothing while disabled (signed out)", () => {
    const onIdle = vi.fn();
    renderHook(() => useIdleLogout(false, onIdle));
    act(() => { vi.advanceTimersByTime(IDLE_LIMIT_MS * 2); });
    expect(onIdle).not.toHaveBeenCalled();
  });

  it("ignores a stale timestamp left over from an earlier session", () => {
    localStorage.setItem("ine-last-activity", String(Date.now() - IDLE_LIMIT_MS * 3));
    const onIdle = vi.fn();
    renderHook(() => useIdleLogout(true, onIdle));
    act(() => { vi.advanceTimersByTime(20000); });
    expect(onIdle).not.toHaveBeenCalled();
  });
});
