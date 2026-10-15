"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import PublishingDialog from "./PublishingDialog";
import PublishTargetsDialog, { usePublishTargets } from "./PublishTargetsDialog";
import { safeUrl } from "../lib/publishTargets";
import { Episode, Project } from "../lib/types";
import { Section } from "./Sidebar";
import CoverPanel from "./CoverPanel";
import { t } from "../lib/i18n";

const ICONS: { key: Section; label: string }[] = [
  { key: "write", label: t("✎ 執筆") },
  { key: "plot", label: t("◆ プロット") },
  { key: "characters", label: t("♟ 人物") },
  { key: "world", label: t("◈ 世界観") },
  { key: "timeline", label: t("⏱ 年表") },
  { key: "glossary", label: t("📖 用語集") },
  { key: "foreshadow", label: t("◎ 伏線") },
  { key: "analytics", label: t("📊 分析") },
  { key: "settings", label: t("⚙ 設定") },
];

const LANGUAGES: { code: string; label: string }[] = [
  { code: "ja", label: "日本語" }, { code: "en", label: "English" }, { code: "zh-CN", label: "简体中文" },
  { code: "ko", label: "한국어" }, { code: "es", label: "Español" }, { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" }, { code: "pt-BR", label: "Português (BR)" },
];
type TranslateJob = { id: number; project_id: number | null; language: string; status: string; progress_percent: number; last_message: string };

type DigestResult = { project: Project; source_episode_count: number; episode_count: number; source_chars: number; chars: number; source_numbers: number[] };

export default function ProjectHome({ project, onSection, onOpenProject }: { project: Project; onSection: (s: Section) => void; onOpenProject?: (p: Project) => void }) {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [tJob, setTJob] = useState<TranslateJob | null>(null);
  const [tError, setTError] = useState("");
  const [showPub, setShowPub] = useState(false);
  const [showTargets, setShowTargets] = useState(false);
  const [targets, setTargets] = usePublishTargets();
  type AllJob = { id: number; status: string; total_languages: number; done_languages: number; failed: string[]; current_language: string; last_message: string };
  const [allJob, setAllJob] = useState<AllJob | null>(null);
  const allActive = !!allJob && (allJob.status === "queued" || allJob.status === "running");
  const allRun = allActive ? { index: Math.min(allJob!.done_languages + 1, allJob!.total_languages), total: allJob!.total_languages, label: allJob!.current_language } : null;
  // The server keeps translating while this screen is closed (or you are logged
  // out), so on opening the screen again pick up the latest single-language job.
  useEffect(() => {
    let live = true;
    setTJob(null);
    api(`/projects/${project.id}/translate-jobs`).then((r) => {
      if (live && Array.isArray(r) && r.length > 0) setTJob(r[0]);
    }).catch(() => {});
    return () => { live = false; };
  }, [project.id]);
  // Pick up an all-language translation that is (or was) running on the server.
  useEffect(() => {
    let live = true;
    setAllJob(null);
    api(`/projects/${project.id}/translate-all`).then((j) => { if (live && j?.id) setAllJob(j); }).catch(() => {});
    return () => { live = false; };
  }, [project.id]);
  useEffect(() => {
    if (!allJob || !allActive) return;
    const timer = setInterval(async () => {
      try { const j = await api(`/translate-all-jobs/${allJob.id}`); if (j?.id) setAllJob(j); } catch { /* retry on next tick */ }
    }, 3000);
    return () => clearInterval(timer);
  }, [allJob, allActive]);
  const tBusy = !!allRun || (!!tJob && (tJob.status === "queued" || tJob.status === "running"));

  // Poll the background translation job until it finishes.
  useEffect(() => {
    if (!tJob || allRun || !tBusy) return;
    const timer = setInterval(async () => {
      try {
        const j = await api(`/translate-jobs/${tJob.id}`);
        if (j?.id) setTJob(j); else { setTError(j?.detail || t("進捗の取得に失敗しました")); setTJob(null); }
      } catch { /* transient; retry on next tick */ }
    }, 2000);
    return () => clearInterval(timer);
  }, [tJob, tBusy, allRun]);

  async function translate(code: string, label: string) {
    if (!window.confirm(t("作品全編を「{label}」に翻訳し、新しい作品として作成します（元の作品は変更されません）。エピソード数が多いと時間がかかります。よろしいですか？", { label }))) return;
    setTError(""); setTJob(null);
    try {
      const j = await api(`/projects/${project.id}/translate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ language: code }) });
      if (j?.id) setTJob(j); else setTError(j?.detail || t("翻訳を開始できませんでした"));
    } catch (e) { setTError(e instanceof Error ? e.message : t("翻訳を開始できませんでした")); }
  }
  // 全翻訳 runs on the server as one job (every other language, one after
  // another), so it carries on after logging out; this just watches it, and picks
  // it up again when the screen is opened later.
  async function translateAll() {
    const targets = LANGUAGES.filter((l) => l.code !== (project.language || "ja"));
    if (!window.confirm(t("作品全編を{n}言語（{labels}）に順番に翻訳し、それぞれ新しい作品として作成します（元の作品は変更されません）。サーバーで実行されるため、ログアウトしても続きます。よろしいですか？", { n: targets.length, labels: targets.map((l) => l.label).join("・") }))) return;
    setTError(""); setTJob(null);
    try {
      const j = await api(`/projects/${project.id}/translate-all`, { method: "POST" });
      if (j?.id) setAllJob(j); else setTError(j?.detail || t("翻訳を開始できませんでした"));
    } catch (e) { setTError(e instanceof Error ? e.message : t("翻訳を開始できませんでした")); }
  }
  async function cancelTranslation(kind: "translate" | "translate_all", id: number) {
    if (!window.confirm(t("翻訳をキャンセルします。翻訳済みの分は残り、次回は続きから翻訳します。よろしいですか？"))) return;
    try { await api("/background-jobs/cancel", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind, id }) }); } catch { /* already finished */ }
    try {
      if (kind === "translate_all") { const j = await api(`/translate-all-jobs/${id}`); if (j?.id) setAllJob(j); }
      else { const j = await api(`/translate-jobs/${id}`); if (j?.id) setTJob(j); }
    } catch { /* ignore */ }
  }
  async function openTranslated() {
    if (!tJob?.project_id || !onOpenProject) return;
    const p = await api(`/projects/${tJob.project_id}`);
    if (p?.id) onOpenProject(p);
  }

  const [digesting, setDigesting] = useState(false);
  const [digest, setDigest] = useState<DigestResult | null>(null);
  const [digestError, setDigestError] = useState("");

  async function makeDigest() {
    if (!window.confirm(t("クライマックス中心に約1/2の分量で、新しい作品「総集編」を作成します（元の作品は変更されません）。よろしいですか？"))) return;
    setDigesting(true); setDigestError(""); setDigest(null);
    try {
      const r = await api(`/projects/${project.id}/digest`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ratio: 0.5 }) });
      if (r?.project) setDigest(r); else setDigestError(r?.detail || t("総集編の作成に失敗しました"));
    } catch (e) {
      setDigestError(e instanceof Error ? e.message : t("総集編の作成に失敗しました"));
    } finally { setDigesting(false); }
  }
  useEffect(() => { api(`/projects/${project.id}/episodes`).then(setEpisodes); }, [project.id]);
  // The last digest made from this work is remembered on the server, so it is
  // still here after leaving the screen (its size reflects any edits since).
  useEffect(() => {
    let alive = true;
    setDigest(null);
    api(`/projects/${project.id}/digest`).then((r) => { if (alive && r?.project) setDigest(r); }).catch(() => {});
    return () => { alive = false; };
  }, [project.id]);
  const goal = project.episode_goal || 500;
  const pct = Math.min(100, Math.round((episodes.length / goal) * 100));
  const recent = [...episodes].sort((a, b) => b.number - a.number).slice(0, 5);

  return (
    <div className="panel projectHome">
      <div className="projectHomeHead">
        <div><small>{project.genre || t("未設定")}</small><h1>{project.name}</h1><p>{project.description || t("あらすじ未設定")}</p></div>
        <div className="projectHomeProgress"><span>{t("進捗 {pct}%", { pct })}</span><b>{t("({eps}/{goal}話)", { eps: episodes.length, goal })}</b></div>
      </div>
      <div className="iconGrid">
        {ICONS.map((x) => <button key={x.key} className="iconGridItem" onClick={() => onSection(x.key)}>{x.label}</button>)}
      </div>
      <div className="card">
        <small>{t("出版情報")}</small>
        <p>{t("タイトル・著者名・内容紹介文・キーワード・カテゴリー・読者対象をまとめて確認・編集します。")}</p>
        <button onClick={() => setShowPub(true)}>{t("出版情報を開く")}</button>
        <p style={{ margin: "10px 0 4px", fontSize: 13 }}>{t("投稿先")}</p>
        <div className="exportButtons">
          {targets.map((x, i) => safeUrl(x.postUrl || x.officialUrl) && <a key={i} className="button" href={safeUrl(x.postUrl || x.officialUrl)} target="_blank" rel="noopener noreferrer">{x.name} ↗</a>)}
          <button onClick={() => setShowTargets(true)}>{t("投稿先の詳細")}</button>
        </div>
      </div>
      {showTargets && <PublishTargetsDialog targets={targets} onChange={setTargets} onClose={() => setShowTargets(false)} />}
      {showPub && <PublishingDialog projectId={project.id} onClose={() => setShowPub(false)}
        onSaved={async () => { const p = await api(`/projects/${project.id}`); if (p?.id && onOpenProject) onOpenProject(p); }} />}
      <div className="card">
        <small>{t("多言語化（全編翻訳）")}</small>
        <p>{t("作品全編を選択した言語に翻訳し、新しい作品として作成します。")}</p>
        <div className="exportButtons">
          <button className="primary" onClick={translateAll} disabled={tBusy || episodes.length === 0}>{allRun ? t("全翻訳中 {i}/{n}（{label}）", { i: allRun.index, n: allRun.total, label: allRun.label }) : t("全翻訳")}</button>
          {LANGUAGES.map((l) => <button key={l.code} onClick={() => translate(l.code, l.label)} disabled={tBusy || episodes.length === 0}>{l.label}</button>)}
        </div>
        {tError && <p style={{ color: "#c0392b" }}>{tError}</p>}
        {allActive && allJob && <button type="button" style={{ color: "#c0392b" }} onClick={() => cancelTranslation("translate_all", allJob.id)}>{t("全翻訳をキャンセル")}</button>}
        {!allActive && tBusy && tJob && <button type="button" style={{ color: "#c0392b" }} onClick={() => cancelTranslation("translate", tJob.id)}>{t("翻訳をキャンセル")}</button>}
        {allJob && <p style={{ color: allJob.status === "error" || allJob.failed.length ? "#c0392b" : undefined }}>{allJob.last_message}</p>}
        {tJob && (
          <div className="resultCard">
            <b>{tJob.status === "completed" ? t("翻訳完了") : tJob.status === "error" ? t("翻訳エラー") : t("翻訳中 {pct}%", { pct: tJob.progress_percent })}</b>
            <p>{tJob.last_message}</p>
            {tJob.status === "completed" && onOpenProject && <button onClick={openTranslated}>{t("翻訳版を開く")}</button>}
          </div>
        )}
      </div>
      <div className="card">
        <small>{t("総集編")}</small>
        <p>{t("プロット終端・伏線回収・最終話などのクライマックス話を集め、約1/2の分量の新しい作品を作成します。")}</p>
        <button onClick={makeDigest} disabled={digesting || episodes.length === 0}>{digesting ? t("作成中...") : t("総集編作成")}</button>
        {digestError && <p style={{ color: "#c0392b" }}>{digestError}</p>}
        {digest && (
          <div className="resultCard">
            <b>{digest.project.name}</b>
            <p>{t("{src}話中{n}話（原作 第{nums}話）／ {chars}字（原作 {srcChars}字）", { src: digest.source_episode_count, n: digest.episode_count, nums: digest.source_numbers.join(t("・")), chars: digest.chars.toLocaleString(), srcChars: digest.source_chars.toLocaleString() })}</p>
            {onOpenProject && <button onClick={() => onOpenProject(digest.project)}>{t("総集編を開く")}</button>}
          </div>
        )}
      </div>
      <CoverPanel projectId={project.id} />
      <div className="card">
        <small>{t("最近の更新")}</small>
        {recent.length === 0 ? <p>{t("まだエピソードがありません。「執筆」から書き始めましょう。")}</p> :
          recent.map((e) => <div className="twinRow" key={e.id}><b>{t("第{n}話", { n: e.number })} {e.title}</b><span>{(e.summary || "").slice(0, 40) || t("概要未設定")}</span></div>)}
      </div>
    </div>
  );
}
