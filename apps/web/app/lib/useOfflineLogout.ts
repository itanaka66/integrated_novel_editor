"use client";
import { useEffect, useRef } from "react";

// Signs the user out as soon as the browser loses network connectivity.
// Uses the browser's native `offline` event, which fires reliably on both
// Wi-Fi drops and cable unplugs. Does nothing while disabled (signed out).
export function useOfflineLogout(enabled: boolean, onOffline: () => void) {
  const onOfflineRef = useRef(onOffline);
  onOfflineRef.current = onOffline;

  useEffect(() => {
    if (!enabled) return;
    const handler = () => onOfflineRef.current();
    window.addEventListener("offline", handler);
    return () => window.removeEventListener("offline", handler);
  }, [enabled]);
}
