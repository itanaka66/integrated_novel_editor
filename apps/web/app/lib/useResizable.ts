"use client";
import { useCallback, useEffect, useRef, useState } from "react";

// Drag-to-resize a single column width, persisted per `storageKey` in
// localStorage so it survives reloads. `grow` says which way the mouse has
// to move to make the panel bigger: "right" for a panel that sits left of
// its handle (a left sidebar/list — dragging right grows it), "left" for a
// panel that sits right of its handle (the right-hand AI panel — dragging
// left grows it, since the handle is on the panel's left edge).
export function useResizableWidth(storageKey: string, defaultWidth: number, min: number, max: number, grow: "left" | "right") {
  const [width, setWidth] = useState(defaultWidth);
  const dragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(defaultWidth);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      const n = raw ? Number(raw) : NaN;
      if (!Number.isNaN(n)) setWidth(Math.min(max, Math.max(min, n)));
    } catch {
      /* localStorage unavailable; default width stands */
    }
    // Only re-read on mount / a genuinely different storage key — min/max/
    // default changing shouldn't yank a value the user already resized.
  }, [storageKey]);

  const onMouseMove = useCallback((ev: MouseEvent) => {
    if (!dragging.current) return;
    const delta = ev.clientX - startX.current;
    const signed = grow === "right" ? delta : -delta;
    setWidth(Math.min(max, Math.max(min, startWidth.current + signed)));
  }, [grow, min, max]);

  const stopDrag = useCallback(() => {
    if (!dragging.current) return;
    dragging.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    window.removeEventListener("mousemove", onMouseMove);
    window.removeEventListener("mouseup", stopDrag);
    setWidth((w) => {
      try { localStorage.setItem(storageKey, String(w)); } catch { /* ignore */ }
      return w;
    });
  }, [onMouseMove, storageKey]);

  const startDrag = useCallback((ev: React.MouseEvent) => {
    ev.preventDefault();
    dragging.current = true;
    startX.current = ev.clientX;
    startWidth.current = width;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", stopDrag);
  }, [width, onMouseMove, stopDrag]);

  return { width, startDrag };
}
