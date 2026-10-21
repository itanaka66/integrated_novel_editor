import { describe, it, expect, vi, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useOfflineLogout } from "./useOfflineLogout";

describe("useOfflineLogout", () => {
  afterEach(() => vi.restoreAllMocks());

  it("calls onOffline when the browser goes offline", () => {
    const onOffline = vi.fn();
    renderHook(() => useOfflineLogout(true, onOffline));
    act(() => { window.dispatchEvent(new Event("offline")); });
    expect(onOffline).toHaveBeenCalledTimes(1);
  });

  it("does nothing while disabled (signed out)", () => {
    const onOffline = vi.fn();
    renderHook(() => useOfflineLogout(false, onOffline));
    act(() => { window.dispatchEvent(new Event("offline")); });
    expect(onOffline).not.toHaveBeenCalled();
  });

  it("removes the listener on unmount", () => {
    const onOffline = vi.fn();
    const { unmount } = renderHook(() => useOfflineLogout(true, onOffline));
    unmount();
    act(() => { window.dispatchEvent(new Event("offline")); });
    expect(onOffline).not.toHaveBeenCalled();
  });
});
