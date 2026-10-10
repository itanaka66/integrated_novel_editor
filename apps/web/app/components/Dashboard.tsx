"use client";
import { useEffect, useState } from "react";
import { api, CurrentUser, getCurrentUser } from "../lib/api";
import { Project } from "../lib/types";
import NewProjectForm from "./NewProjectForm";
import ImportPanel from "./ImportPanel";
import AccountPanel from "./AccountPanel";
import { t } from "../lib/i18n";

type Twin = { metrics: { episodes: number; continuity_open: number }; health: { score: number; label: string } };

export default function Dashboard({ onOpen, onLogout }: { onOpen: (p: Project) => void; onLogout: () => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [twins, setTwins] = useState<Record<number, Twin>>({});
  const [showNew, setShowNew] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => { getCurrentUser().then(setUser); }, []);

  async function load() {
    setBusy(true);
    setError("");
    try {
      const list: Project[] = await api("/projects");
      setProjects(list);
      const entries = await Promise.all(list.map(async (p) => [p.id, await api(`/projects/${p.id}/story-twin`)] as const));
      setTwins(Object.fromEntries(entries));
    } catch {
      setError(t("作品一覧の読み込みに失敗しました。APIに接続できているか確認してください。"));
    } finally { setBusy(false); }
  }
  useEffect(() => { load(); }, []);

  // Translations hang under the work they were made from (parent = original).
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const ids = new Set(projects.map((p) => p.id));
  const childrenOf = (id: number) => projects.filter((c) => c.source_project_id === id);
  const roots = projects.filter((p) => !p.source_project_id || !ids.has(p.source_project_id));
  const toggle = (id: number) => setCollapsed((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  function renderWork(p: Project, depth: number, seen: Set<number>): React.ReactNode {
    const goal = p.episode_goal || 500;
    const eps = twins[p.id]?.metrics.episodes ?? 0;
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
            <span>{depth > 0 && p.language ? `${p.language} · ` : ""}{p.genre || t("未設定")}</span>
          </div>
          <div className="progress"><i style={{ width: `${pct}%` }} /></div>
          <div className="workCardFoot"><span>{t("進捗 {pct}%", { pct })}</span><span>{t("({eps}/{goal}話)", { eps, goal })}</span></div>
        </div>
        {open && kids.map((c) => renderWork(c, depth + 1, new Set(seen).add(p.id)))}
      </div>
    );
  }

  const focus = projects[0];
  const focusTwin = focus ? twins[focus.id] : null;

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
          <small>{t("マイ作品")}</small>
          {projects.length === 0 && !busy && <div className="card"><b>{t("まだ作品がありません")}</b><p>{t("「新規作品作成」から最初の作品を作りましょう。")}</p></div>}
          {roots.map((p) => renderWork(p, 0, new Set()))}
        </div>
        {focus && focusTwin && (
          <div className="dashboardStats card">
            <small>{t("執筆状況（{name}）", { name: focus.name })}</small>
            <div className="dashboardDonutRow">
              <div className={`health ${focusTwin.health.label}`}><b>{Math.min(100, Math.round((focusTwin.metrics.episodes / (focus.episode_goal || 500)) * 100))}%</b><span>{t("執筆状況")}</span></div>
              <div className="dashboardStatList">
                <div><small>{t("総話数")}</small><b>{focusTwin.metrics.episodes} / {focus.episode_goal || 500}</b></div>
                <div><small>{t("未解決の連続性課題")}</small><b>{focusTwin.metrics.continuity_open}</b></div>
                <div><small>{t("作品健全性スコア")}</small><b>{focusTwin.health.score}</b></div>
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
