"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Episode, Project } from "../lib/types";
import { Section } from "./Sidebar";

const ICONS: { key: Section; label: string }[] = [
  { key: "write", label: "✎ 執筆" },
  { key: "plot", label: "◆ プロット" },
  { key: "characters", label: "♟ 人物" },
  { key: "world", label: "◈ 世界観" },
  { key: "timeline", label: "⏱ 年表" },
  { key: "glossary", label: "📖 用語集" },
  { key: "foreshadow", label: "◎ 伏線" },
  { key: "analytics", label: "📊 分析" },
  { key: "settings", label: "⚙ 設定" },
];

type DigestResult = { project: Project; source_episode_count: number; episode_count: number; source_chars: number; chars: number; source_numbers: number[] };

export default function ProjectHome({ project, onSection, onOpenProject }: { project: Project; onSection: (s: Section) => void; onOpenProject?: (p: Project) => void }) {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [digesting, setDigesting] = useState(false);
  const [digest, setDigest] = useState<DigestResult | null>(null);
  const [digestError, setDigestError] = useState("");

  async function makeDigest() {
    if (!window.confirm("クライマックス中心に約1/2の分量で、新しい作品「総集編」を作成します（元の作品は変更されません）。よろしいですか？")) return;
    setDigesting(true); setDigestError(""); setDigest(null);
    try {
      const r = await api(`/projects/${project.id}/digest`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ratio: 0.5 }) });
      if (r?.project) setDigest(r); else setDigestError(r?.detail || "総集編の作成に失敗しました");
    } catch (e) {
      setDigestError(e instanceof Error ? e.message : "総集編の作成に失敗しました");
    } finally { setDigesting(false); }
  }
  useEffect(() => { api(`/projects/${project.id}/episodes`).then(setEpisodes); }, [project.id]);
  const goal = project.episode_goal || 500;
  const pct = Math.min(100, Math.round((episodes.length / goal) * 100));
  const recent = [...episodes].sort((a, b) => b.number - a.number).slice(0, 5);

  return (
    <div className="panel projectHome">
      <div className="projectHomeHead">
        <div><small>{project.genre || "未設定"}</small><h1>{project.name}</h1><p>{project.description || "あらすじ未設定"}</p></div>
        <div className="projectHomeProgress"><span>進捗 {pct}%</span><b>({episodes.length}/{goal}話)</b></div>
      </div>
      <div className="iconGrid">
        {ICONS.map((x) => <button key={x.key} className="iconGridItem" onClick={() => onSection(x.key)}>{x.label}</button>)}
      </div>
      <div className="card">
        <small>総集編</small>
        <p>プロット終端・伏線回収・最終話などのクライマックス話を集め、約1/2の分量の新しい作品を作成します。</p>
        <button onClick={makeDigest} disabled={digesting || episodes.length === 0}>{digesting ? "作成中..." : "総集編作成"}</button>
        {digestError && <p style={{ color: "#c0392b" }}>{digestError}</p>}
        {digest && (
          <div className="resultCard">
            <b>{digest.project.name}</b>
            <p>{digest.source_episode_count}話中{digest.episode_count}話（原作 第{digest.source_numbers.join("・")}話）／ {digest.chars.toLocaleString()}字（原作 {digest.source_chars.toLocaleString()}字）</p>
            {onOpenProject && <button onClick={() => onOpenProject(digest.project)}>総集編を開く</button>}
          </div>
        )}
      </div>
      <div className="card">
        <small>最近の更新</small>
        {recent.length === 0 ? <p>まだエピソードがありません。「執筆」から書き始めましょう。</p> :
          recent.map((e) => <div className="twinRow" key={e.id}><b>第{e.number}話 {e.title}</b><span>{(e.summary || "").slice(0, 40) || "概要未設定"}</span></div>)}
      </div>
    </div>
  );
}
