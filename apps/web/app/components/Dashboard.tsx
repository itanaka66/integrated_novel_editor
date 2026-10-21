"use client";
import { useEffect, useState } from "react";
import { api, CurrentUser, getCurrentUser } from "../lib/api";
import { Project } from "../lib/types";
import NewProjectForm from "./NewProjectForm";
import ImportPanel from "./ImportPanel";
import AccountPanel from "./AccountPanel";
import { t } from "../lib/i18n";
import { loadDashboardCache, saveDashboardCache, Twin } from "../lib/dashboardCache";

const QUIET = { headers: { "X-Quiet": "1" } };

export default function Dashboard({ onOpen, onLogout }: { onOpen: (p: Project) => void; onLogout: () => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [focusTwin, setFocusTwin] = useState<{ id: number; twin: Twin } | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => { getCurrentUser().then(setUser); }, []);

  // Cached cards draw immediately; the real numbers are fetched quietly behind
  // them (one episode-count query, plus the detailed stats for just the most
  // recent work). With no cache yet, this is a normal blocking first load.
  async function load() {
    const cached = loadDashboardCache();
    if (cached) {
      setProjects(cached.projects); setCounts(cached.counts); setFocusTwin(cached.focus ?? null); setBusy(false);
    } else setBusy(true);
    setError("");
    try {
      const opts = cached ? QUIET : undefined;
      const [list, c]: [Project[], { counts: Record<string, number> }] = await Promise.all([api("/projects", opts), api("/projects/episode-counts", opts)]);
      setProjects(list); setCounts(c.counts);
      const first = list[0];
      let focus: { id: number; twin: Twin } | null = null;
      if (first) {
        try { focus = { id: first.id, twin: await api(`/projects/${first.id}/story-twin`, QUIET) }; } catch { /* stats are optional */ }
      }
      setFocusTwin(focus);
      saveDashboardCache({ projects: list, counts: c.counts, focus: focus ?? undefined });
    } catch {
      if (!cached) setError(t("作品一覧の読み込みに失敗しました。APIに接続できているか確認してください。"));
    } finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);

  // Translations hang under the work they were made from (parent = original).
  const COLLAPSED_KEY = "ine-dashboard-collapsed-v1";
  const [collapsed, setCollapsed] = useState<Set<number>>(() => {
    try {
      const raw = localStorage.getItem(COLLAPSED_KEY);
      if (!raw) return new Set<number>();
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? new Set<number>(arr) : new Set<number>();
    } catch { return new Set<number>(); }
  });
  useEffect(() => {
    try { localStorage.setItem(COLLAPSED_KEY, JSON.stringify([...collapsed])); } catch { /* storage full/blocked */ }
  }, [collapsed]);
  const ids = new Set(projects.map((p) => p.id));
  const childrenOf = (id: number) => projects.filter((c) => c.source_project_id === id);
  const roots = projects.filter((p) => !p.source_project_id || !ids.has(p.source_project_id));
  const toggle = (id: number) => setCollapsed((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  function renderWork(p: Project, depth: number, seen: Set<number>, parent?: Project): React.ReactNode {
    const goal = p.episode_goal || 500;
    const eps = counts[String(p.id)] ?? 0;
    const pct = Math.min(100, Math.round((eps / goal) * 100));
    const kids = seen.has(p.id) ? [] : childrenOf(p.id);
    const open = !collapsed.has(p.id);
    return (
      <div key={p.id} style={{ marginLeft: depth * 22 }}>
        <div className="workCard" onClick={() => onOpen(p)} style={depth > 0 ? { borderLeft: "3px solid #8aa4c8" } : undefined}>
          <div className="workCardHead">
            <b>
              {kids.length > 0 && (
                <button type="button" aria-label={open ? t("折りたたむ") : t("展開")} onClick={(e) => { e.stopPropagation(); toggle(p.id); }}
                  style={{ marginRight: 6, padding: "0 6px" }}>{open ? "▾" : "▸"}</button>
              )}
              {depth > 0 && "└ "}{p.name}
            </b>
            <span>{depth > 0 ? `${parent && p.language === parent.language ? t("総集編") : p.language ?? ""} · ` : ""}{p.genre || t("未設定")}</span>
          </div>
          <div className="progress"><i style={{ width: `${pct}%` }} /></div>
          <div className="workCardFoot"><span>{t("進捗 {pct}%", { pct })}</span><span>{t("({eps}/{goal}話)", { eps, goal })}</span></div>
        </div>
        {open && kids.map((c) => renderWork(c, depth + 1, new Set(seen).add(p.id), p))}
      </div>
    );
  }

  // Work that keeps running on the server whether or not anyone is logged in.
  type BgJob = { kind: string; id: number | null; label: string; project_name: string | null; status: string; message: string; done: number | null; total: number | null };
  const [bgJobs, setBgJobs] = useState<BgJob[]>([]);
  useEffect(() => {
    let live = true;
    const poll = () => api("/background-jobs").then((r) => { if (live && Array.isArray(r?.jobs)) setBgJobs(r.jobs); }).catch(() => {});
    poll();
    const timer = setInterval(poll, 5000);
    return () => { live = false; clearInterval(timer); };
  }, []);

  async function cancelJob(j: BgJob) {
    if (j.id == null || !window.confirm(t("「{label}」をキャンセルします。ここまでの結果は残ります。よろしいですか？", { label: `${j.label}${j.project_name ? `「${j.project_name}」` : ""}` }))) return;
    try { await api("/background-jobs/cancel", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: j.kind, id: j.id }) }); } catch { /* already finished */ }
    api("/background-jobs").then((r) => { if (Array.isArray(r?.jobs)) setBgJobs(r.jobs); }).catch(() => {});
  }
  async function cancelAll() {
    if (!window.confirm(t("実行中のAI処理をすべてキャンセルします。ここまでの結果は残ります。よろしいですか？"))) return;
    for (const j of bgJobs) {
      if (j.id == null) continue;
      try { await api("/background-jobs/cancel", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind: j.kind, id: j.id }) }); } catch { /* ignore */ }
    }
    api("/background-jobs").then((r) => { if (Array.isArray(r?.jobs)) setBgJobs(r.jobs); }).catch(() => {});
  }

  const focus = projects[0];
  const focusStats = focus && focusTwin && focusTwin.id === focus.id ? focusTwin.twin : null;

  return (
    <div className="dashboard">
      <header className="dashboardHeader">
        <div><small>DASHBOARD</small><h1>{t("こんにちは、{name}さん", { name: user?.username ?? t("ユーザー") })}</h1></div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setShowImport(true)}>{t("ファイルからインポート")}</button>
          <button className="add" onClick={() => setShowNew(true)}>{t("＋ 新規作品作成")}</button>
          <button onClick={() => setShowAccount(true)}>{t("⚙ アカウント設定")}</button>
          <button onClick={onLogout}>{t("⏻ ログアウト")}</button>
        </div>
      </header>
      {error && <p className="errorNote">{error}</p>}
      {busy && projects.length === 0 ? <p className="loading">{t("読み込み中...")}</p> : null}
      <div className="dashboardGrid">
        <div className="dashboardWorks">
          {bgJobs.length > 0 && (
            <div className="card">
              <small>{t("サーバーで実行中の処理（ログアウトしても続行されます）")}</small>
              {bgJobs.length > 1 && <button type="button" style={{ marginLeft: 10, color: "#c0392b" }} onClick={cancelAll}>{t("すべてキャンセル")}</button>}
              {bgJobs.map((j, i) => (
                <p key={i} style={{ margin: "4px 0" }}>
                  <b>{j.label}</b>{j.project_name ? `「${j.project_name}」` : ""}
                  {j.total ? ` ${j.done ?? 0}/${j.total}` : ""} <small>{j.message}</small>
                  {j.id != null && <button type="button" style={{ marginLeft: 8, color: "#c0392b" }} onClick={() => cancelJob(j)}>{t("キャンセル")}</button>}
                </p>
              ))}
            </div>
          )}
          <small>{t("マイ作品")}</small>
          {projects.length === 0 && !busy && <div className="card"><b>{t("まだ作品がありません")}</b><p>{t("「新規作品作成」から最初の作品を作りましょう。")}</p></div>}
          {roots.map((p) => renderWork(p, 0, new Set()))}
        </div>
        {focus && focusStats && (
          <div className="dashboardStats card">
            <small>{t("執筆状況（{name}）", { name: focus.name })}</small>
            <div className="dashboardDonutRow">
              <div className={`health ${focusStats.health.label}`}><b>{Math.min(100, Math.round((focusStats.metrics.episodes / (focus.episode_goal || 500)) * 100))}%</b><span>{t("執筆状況")}</span></div>
              <div className="dashboardStatList">
                <div><small>{t("総話数")}</small><b>{focusStats.metrics.episodes} / {focus.episode_goal || 500}</b></div>
                <div><small>{t("未解決の連続性課題")}</small><b>{focusStats.metrics.continuity_open}</b></div>
                <div><small>{t("作品健全性スコア")}</small><b>{focusStats.health.score}</b></div>
              </div>
            </div>
            <p className="dashboardNote">{t("※ AI利用状況（トークン使用量）の集計は今後実装予定です。")}</p>
          </div>
        )}
      </div>
      {showNew && <NewProjectForm onCancel={() => setShowNew(false)} onCreated={(p) => { setShowNew(false); onOpen(p); }} />}
      {showImport && <ImportPanel onCancel={() => setShowImport(false)} onImported={(p) => { setShowImport(false); onOpen(p); }} />}
      {showAccount && <AccountPanel isAdmin={!!user?.isAdmin} onCancel={() => setShowAccount(false)} />}
    </div>
  );
}
