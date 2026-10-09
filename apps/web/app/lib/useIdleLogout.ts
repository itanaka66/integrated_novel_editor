"use client";
import { useEffect, useRef } from "react";

export const IDLE_LIMIT_MS = 10 * 60 * 1000;
const KEY = "ine-last-activity";
const EVENTS = ["mousemove", "mousedown", "keydown", "wheel", "scroll", "touchstart"] as const;

function readLast(): number | null {
  try {
    const v = Number(localStorage.getItem(KEY));
    return v > 0 ? v : null;
  } catch {
    return null;
  }
}

// Calls onIdle once there has been no user input for `limitMs`. The last
// activity time lives in localStorage rather than in this component, so
// activity in any open tab keeps every tab signed in (otherwise a tab you
// aren't looking at would sign you out of the one you are). It's compared
// against the clock rather than counted down with a timer, so a laptop that
// slept, or a background tab whose timers were throttled, still logs out as
// soon as it wakes up instead of after another full interval.
export function useIdleLogout(enabled: boolean, onIdle: () => void, limitMs = IDLE_LIMIT_MS) {
  const onIdleRef = useRef(onIdle);
  onIdleRef.current = onIdle;

  useEffect(() => {
    if (!enabled) return;
    let lastWrite = 0;
    const touch = () => {
      const now = Date.now();
      if (now - lastWrite < 5000) return; // mousemove fires constantly
      lastWrite = now;
      try { localStorage.setItem(KEY, String(now)); } catch { /* storage unavailable */ }
    };
    // Starts fresh at sign-in/mount: a stale value from a previous session
    // must not log the user straight back out.
    lastWrite = 0;
    touch();

    // Without storage the shared timestamp can't be kept, so track locally.
    let local = Date.now();
    const onInput = () => { local = Date.now(); touch(); };
    const check = () => {
      const last = readLast() ?? local;
      if (Date.now() - Math.max(last, local) >= limitMs) {
        onIdleRef.current();
      }
    };
    for (const e of EVENTS) window.addEventListener(e, onInput, { passive: true });
    document.addEventListener("visibilitychange", check);
    window.addEventListener("focus", check);
    const timer = setInterval(check, 15000);
    return () => {
      for (const e of EVENTS) window.removeEventListener(e, onInput);
      document.removeEventListener("visibilitychange", check);
      window.removeEventListener("focus", check);
      clearInterval(timer);
    };
  }, [enabled, limitMs]);
}
