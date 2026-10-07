"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import { getActivities, subscribeActivities } from "../lib/llmActivity";

const NO_ACTIVITIES: ReturnType<typeof getActivities> = [];

// Shown whenever one or more calls are waiting on the LLM, saying what each
// one is doing. Deliberately a floating card, not a modal overlay: a single
// generation can run for minutes, and blocking the whole app (including the
// text being edited) for that long would be worse than the silence it fixes.
// The bar is indeterminate — Ollama doesn't report progress for a request,
// only elapsed time is known.
export default function LlmActivityDialog() {
  const activities = useSyncExternalStore(subscribeActivities, getActivities, () => NO_ACTIVITIES);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (activities.length === 0) return;
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, [activities.length]);

  // Skip anything under 400ms old: a fast call (e.g. a cached embedding)
  // would otherwise flash the dialog up and away too quickly to read.
  const visible = activities.filter((a) => now - a.startedAt >= 400);
  if (visible.length === 0) return null;

  return (
    <div className="llmDialog" role="dialog" aria-live="polite" aria-label="AI処理中">
      <b>AI処理中</b>
      {visible.map((a) => (
        <div className="llmDialogRow" key={a.id}>
          <span>{a.label}…</span>
          <small>{Math.floor((now - a.startedAt) / 1000)}秒経過</small>
        </div>
      ))}
      <div className="llmBar" role="progressbar" aria-label="処理中"><i /></div>
    </div>
  );
}
