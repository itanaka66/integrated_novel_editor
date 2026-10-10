"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import { api } from "../lib/api";
import { getActivities, subscribeActivities } from "../lib/llmActivity";
import { t } from "../lib/i18n";

const NO_ACTIVITIES: ReturnType<typeof getActivities> = [];

type QueueEntry = {
  id: number;
  position: number;
  state: "running" | "waiting";
  kind_label: string;
  model: string;
  purpose: string | null;
  project_name?: string | null;
  elapsed_seconds: number;
};

// Floating dialog listing the server's LLM queue (GET /api/v1/llm/queue):
// what's running on Ollama right now and what's waiting behind it, from
// every source — this tab's manual AI actions, auto-write jobs, other
// browsers. Falls back to this tab's own in-flight calls (lib/llmActivity.ts)
// for the moment before the first poll catches up. Deliberately not a modal:
// a generation can run for minutes, and auto-write for hours. The bar is
// indeterminate — Ollama reports no progress per request, only elapsed time.
export default function LlmActivityDialog() {
  const local = useSyncExternalStore(subscribeActivities, getActivities, () => NO_ACTIVITIES);
  const [entries, setEntries] = useState<QueueEntry[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    let alive = true;
    const poll = () => {
      api("/llm/queue")
        .then((r) => { if (alive && r && Array.isArray(r.entries)) setEntries(r.entries); })
        .catch(() => {});
    };
    poll();
    const t = setInterval(poll, 2000);
    return () => { alive = false; clearInterval(t); };
  }, [local.length]);

  useEffect(() => {
    if (local.length === 0) return;
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, [local.length]);

  // Skip local calls under 400ms old so a fast one doesn't flash the dialog.
  const localVisible = local.filter((a) => now - a.startedAt >= 400);

  const rows: { key: string; state: "running" | "waiting"; head: string; detail: string; seconds: number }[] =
    entries.length > 0
      ? entries.map((e) => ({
          key: `s${e.id}`,
          state: e.state,
          head: `${e.position}. ${e.project_name ? `「${e.project_name}」 ` : ""}${e.purpose ?? t("AI処理")}`,
          detail: `${e.kind_label} · ${e.model}`,
          seconds: e.elapsed_seconds,
        }))
      : localVisible.map((a, i) => ({
          key: `l${a.id}`,
          state: "running" as const,
          head: `${i + 1}. ${a.label}`,
          detail: "",
          seconds: Math.floor((now - a.startedAt) / 1000),
        }));

  if (rows.length === 0) return null;

  const running = rows.filter((r) => r.state === "running").length;
  const waiting = rows.length - running;

  return (
    <div className="llmDialog" role="dialog" aria-live="polite" aria-label={t("AI処理中")}>
      <div className="llmDialogHead">
        <b>{t("AI処理中・LLMキュー")}</b>
        <small>{t("実行中 {n}", { n: running })}{waiting > 0 ? t(" / 待機 {n}", { n: waiting }) : ""}</small>
        <button type="button" className="llmDialogToggle" onClick={() => setCollapsed((c) => !c)} aria-label={collapsed ? t("展開") : t("折りたたむ")}>
          {collapsed ? t("＋") : "−"}
        </button>
      </div>
      {!collapsed && (
        <ul className="llmQueue">
          {rows.map((r) => (
            <li key={r.key} className={r.state === "waiting" ? "waiting" : "running"}>
              <span className="llmQueueState">{r.state === "running" ? t("実行中") : t("待機中")}</span>
              <span className="llmQueueMain">
                {r.head}
                {r.detail && <small>{r.detail}</small>}
              </span>
              <small>{t("{n}秒", { n: r.seconds })}{r.state === "waiting" ? t("待ち") : ""}</small>
            </li>
          ))}
        </ul>
      )}
      <div className="llmBar" role="progressbar" aria-label={t("処理中")}><i /></div>
    </div>
  );
}
