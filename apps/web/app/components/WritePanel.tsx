"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { marked } from "marked";
import { api, post, put } from "../lib/api";
import { Episode, Project } from "../lib/types";
import { computeQualityIssues } from "../lib/qualityCheck";
import { useResizableWidth } from "../lib/useResizable";
import ProofreadPanel from "./ProofreadPanel";
import { t } from "../lib/i18n";

const CUSTOM_ACTIONS = [
  { label: t("⏱ 時系列チェック"), prompt: "時系列的に矛盾がないかチェックしてください。エピソード番号、世界内時間、出来事の前後関係、人物の移動・年齢・経過時間を確認し、矛盾があれば根拠となるエピソード番号と修正案を示してください。" },
  { label: t("♟ 人物状態チェック"), prompt: "キャラクターの状態に矛盾がないかチェックしてください。生死、年齢、現在地、負傷・健康状態、感情、目標、知識、能力、人間関係の変化を過去の状態履歴と比較し、不整合と修正案を示してください。" },
  { label: t("🌐 世界観チェック"), prompt: "世界観設定に矛盾がないかチェックしてください。場所、組織、アイテム、技術、魔法、文明レベル、設定ルールを過去の正本設定と比較し、矛盾の根拠と修正案を示してください。" },
  { label: t("◎ 伏線チェック"), prompt: "伏線の状態をチェックしてください。設置済みの伏線、回収済みの伏線、未回収の伏線、予定より早すぎる・遅すぎる回収、設定と矛盾する回収を整理し、優先して確認すべき伏線を示してください。" },
  { label: t("◆ プロット整合"), prompt: "現在のエピソードが全体プロットと整合しているかチェックしてください。目的、対立、進行状況、予定している展開、キャラクターの成長との矛盾を確認し、必要なら修正案を提示してください。" },
  { label: t("✎ 文章品質チェック"), prompt: "このエピソードを長編小説の編集者としてチェックしてください。設定・時系列・人物描写の一貫性に加え、冗長表現、説明過多、視点の乱れ、会話の不自然さ、読者の没入を妨げる箇所を指摘し、具体的な改善案を示してください。" },
];

type Revision = { id: number; title: string; summary: string; created_at: string };

export default function WritePanel({ project }: { project: Project }) {
  const [es, setEs] = useState<Episode[]>([]);
  const [e, setE] = useState<Episode | null>(null);
  const [ai, setAi] = useState("");
  const [busy, setBusy] = useState(false);
  const [inst, setInst] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [preview, setPreview] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [showChecks, setShowChecks] = useState(false);
  const [showProofread, setShowProofread] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const episodeList = useResizableWidth("ine-write-episodelist-width", 190, 150, 400, "right");
  const rightPanel = useResizableWidth("ine-write-rightpanel-width", 280, 220, 560, "left");

  const qualityIssues = useMemo(() => computeQualityIssues(es), [es]);

  async function load() {
    const d = await api(`/projects/${project.id}/episodes`);
    setEs(d);
    setE(d[0] || null);
  }
  useEffect(() => { load(); }, [project.id]);

  function toggleSelected(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function deleteSelected() {
    if (selectedIds.size === 0) return;
    if (!confirm(t("選択した{n}件のエピソードを削除しますか？残りのエピソードの話数は自動的に詰められます。", { n: selectedIds.size }))) return;
    setBulkBusy(true);
    try {
      const result = await post(`/projects/${project.id}/episodes/bulk-delete`, { episode_ids: Array.from(selectedIds) });
      const newEs: Episode[] = result.episodes;
      setEs(newEs);
      setSelectedIds(new Set());
      setE((cur) => (cur ? newEs.find((x) => x.id === cur.id) ?? newEs[0] ?? null : newEs[0] ?? null));
    } finally {
      setBulkBusy(false);
    }
  }

  function jumpToIssue(episodeId: number | null) {
    if (episodeId === null) return;
    const target = es.find((x) => x.id === episodeId);
    if (target) { setE(target); setShowChecks(false); }
  }

  async function addEpisode() {
    const number = (es[es.length - 1]?.number || 0) + 1;
    const title = prompt(t("エピソードタイトル"), `第${number}話`);
    if (!title) return;
    await post(`/projects/${project.id}/episodes`, { number, title, summary: "", content: "" });
    await load();
  }

  async function save() {
    if (!e) return;
    setBusy(true);
    try {
      const x = await put(`/episodes/${e.id}`, e);
      setE(x); setEs(es.map((v) => (v.id === x.id ? x : v))); setWarnings(x.warnings || []);
    } finally { setBusy(false); }
  }

  async function openHistory() {
    if (!e) return;
    setRevisions(await api(`/episodes/${e.id}/revisions`));
    setShowHistory(true);
  }
  async function restoreRevision(revisionId: number) {
    if (!e) return;
    if (!confirm(t("この版に復元しますか？現在の内容は履歴として保存されます。"))) return;
    const x = await post(`/episodes/${e.id}/revisions/${revisionId}/restore`, {});
    setE(x); setEs(es.map((v) => (v.id === x.id ? x : v))); setShowHistory(false);
  }

  function wrapSelection(before: string, after: string = before) {
    if (!e) return;
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart, end = ta.selectionEnd;
    const selected = e.content.slice(start, end);
    const next = e.content.slice(0, start) + before + selected + after + e.content.slice(end);
    setE({ ...e, content: next });
    requestAnimationFrame(() => {
      ta.focus();
      ta.setSelectionRange(start + before.length, start + before.length + selected.length);
    });
  }
  function insertLinePrefix(prefix: string) {
    if (!e) return;
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const lineStart = e.content.lastIndexOf("\n", start - 1) + 1;
    const next = e.content.slice(0, lineStart) + prefix + e.content.slice(lineStart);
    setE({ ...e, content: next });
    requestAnimationFrame(() => { ta.focus(); ta.setSelectionRange(start + prefix.length, start + prefix.length); });
  }

  const wordCount = (e?.content || "").replace(/\s/g, "").length;

  async function aiRun(mode: string, instructionOverride?: string) {
    if (!e) return;
    setBusy(true);
    try {
      const instruction = instructionOverride ?? (inst || "作品設定を守ってください");
      setInst(instruction);
      const x = await post("/ai/generate", { project_id: project.id, episode_id: e.id, instruction, mode, rag_limit: 6 });
      setAi(x.text || x.detail);
    } finally { setBusy(false); }
  }

  if (!e) return <div className="panel"><p>{t("エピソードがまだありません。")}</p><button className="add" onClick={addEpisode}>{t("＋ エピソードを追加")}</button></div>;

  return (
    <div className="writeLayout" style={{ "--ep-w": `${episodeList.width}px`, "--right-w": `${rightPanel.width}px` } as React.CSSProperties}>
      <aside className="writeEpisodeList">
        <div className="section">EPISODES</div>
        <div className="episodes">
          {es.map((x) => (
            <div className={e.id === x.id ? "epRow active" : "epRow"} key={x.id}>
              <input type="checkbox" checked={selectedIds.has(x.id)} onChange={() => toggleSelected(x.id)} onClick={(ev) => ev.stopPropagation()} />
              <button className="ep" onClick={() => setE(x)}>#{String(x.number).padStart(3, "0")} {x.title}</button>
            </div>
          ))}
        </div>
        <button className="newEpisode" onClick={addEpisode}>{t("＋ 新規エピソード")}</button>
        <button className="newEpisode" onClick={deleteSelected} disabled={selectedIds.size === 0 || bulkBusy}>
          {bulkBusy ? t("削除中...") : t("選択した{n}件を削除（話数を自動調整）", { n: selectedIds.size || "" })}
        </button>
        <button className="newEpisode" onClick={() => setShowChecks(true)}>
          ⚠ {t("品質チェック")}{qualityIssues.length > 0 ? `（${qualityIssues.length}）` : ""}
        </button>
      </aside>
      <div className="resizeHandle" onMouseDown={episodeList.startDrag} />
      <section className="main">
        <div className="writeHead">
          <div><small>EPISODE {e.number}</small><input value={e.title} onChange={(x) => setE({ ...e, title: x.target.value })} /></div>
          <div className="writeHeadActions">
            <button className="historyButton" onClick={openHistory}>{t("🕘 履歴")}</button>
            <button className="historyButton" onClick={() => setShowProofread(true)} title={t("スタイルガイドと照合し、差分を1件ずつ確認しながら修正します")}>{t("📐 文章校正")}</button>
            <button onClick={async () => { await save(); await post(`/episodes/${e.id}/character-states`, {}); }}>{busy ? t("保存中") : t("保存＋人物状態更新")}</button>
          </div>
        </div>
        {warnings.length > 0 && <div className="saveWarnings">{warnings.map((w, i) => <p key={i}>⚠ {w}</p>)}</div>}
        <div className="summary"><small>SUMMARY</small><input value={e.summary} onChange={(x) => setE({ ...e, summary: x.target.value })} /></div>
        <div className="editorToolbar">
          <button onClick={() => wrapSelection("**")} title={t("太字")}>B</button>
          <button onClick={() => wrapSelection("*")} title={t("斜体")}><i>I</i></button>
          <button onClick={() => insertLinePrefix("## ")} title={t("見出し")}>H</button>
          <button onClick={() => insertLinePrefix("> ")} title={t("引用")}>❝</button>
          <button className={preview ? "on" : ""} onClick={() => setPreview((p) => !p)}>{preview ? t("編集に戻る") : t("プレビュー")}</button>
          <span className="wordCount">{t("{n}文字", { n: wordCount.toLocaleString() })}</span>
        </div>
        {preview ? (
          // Single-user app; the content is always this same user's own
          // Markdown (never third-party input), so raw HTML rendering here
          // carries no cross-user XSS risk.
          <div className="novelPreview" dangerouslySetInnerHTML={{ __html: marked.parse(e.content || "", { async: false }) as string }} />
        ) : (
          <textarea ref={textareaRef} className="novel" value={e.content} onChange={(x) => setE({ ...e, content: x.target.value })} />
        )}
      </section>
      <div className="resizeHandle" onMouseDown={rightPanel.startDrag} />
      <aside className="right">
        <b>AI EDITOR-IN-CHIEF</b>
        <p className="context">{t("Context Builder：本文、人物、世界観、プロット、伏線、RAGを統合")}</p>
        <button className="check" onClick={async () => { setBusy(true); const x = await post("/continuity/check", { project_id: project.id, episode_id: e.id }); setAi(JSON.stringify(x.issues || x.detail, null, 2)); setBusy(false); }}>{t("⚠ 連続性を監査")}</button>
        <div className="actions">
          <button onClick={() => aiRun("continue")}>{t("▶ 続きを書く")}</button>
          <button onClick={() => aiRun("plot")}>{t("◆ 次の展開")}</button>
          <button onClick={() => aiRun("summary")}>{t("要約")}</button>
          <button onClick={() => aiRun("proofread")}>{t("校正")}</button>
        </div>
        <div className="customTitle"><small>QUICK CUSTOM CHECKS</small><span>{t("ボタンを押すと専用プロンプトを送信")}</span></div>
        <div className="customActions">{CUSTOM_ACTIONS.map((a) => <button key={a.label} disabled={busy} onClick={() => { setInst(a.prompt); aiRun("custom", a.prompt); }}>{a.label}</button>)}</div>
        <textarea className="instruction" value={inst} onChange={(x) => setInst(x.target.value)} placeholder={t("AIへの指示")} />
        <div className="result"><small>AI RESULT</small><pre>{busy ? t("AI処理中...") : ai || t("結果がここに表示されます")}</pre></div>
        {ai && <button className="adopt" onClick={() => { setE({ ...e, content: e.content + "\n\n" + ai }); setAi(""); }}>{t("＋ 本文に追加")}</button>}
      </aside>
      {showChecks && (
        <div className="modalOverlay" onClick={() => setShowChecks(false)}>
          <div className="modalCard" onClick={(ev) => ev.stopPropagation()}>
            <h1>{t("品質チェック")}</h1>
            <p style={{ color: "#687386", fontSize: 12, margin: 0 }}>
              {t("タイトルの空欄・重複・話数の不一致、本文への英単語の混在を、保存操作なしでその場でチェックします。クリックすると該当エピソードを開きます。")}
            </p>
            {qualityIssues.length === 0 ? (
              <p className="savedNote">{t("問題は見つかりませんでした。")}</p>
            ) : (
              <div className="revisionList">
                {qualityIssues.map((issue, i) => (
                  <div className="revisionRow" key={i} style={{ cursor: issue.episodeId !== null ? "pointer" : "default" }} onClick={() => jumpToIssue(issue.episodeId)}>
                    <div><span>{issue.message}</span></div>
                  </div>
                ))}
              </div>
            )}
            <div className="modalActions"><button onClick={() => setShowChecks(false)}>{t("閉じる")}</button></div>
          </div>
        </div>
      )}
      {showProofread && e && (
        <ProofreadPanel
          episodeId={e.id}
          content={e.content}
          onApply={(next) => setE({ ...e, content: next })}
          onClose={() => setShowProofread(false)}
        />
      )}
      {showHistory && (
        <div className="modalOverlay" onClick={() => setShowHistory(false)}>
          <div className="modalCard" onClick={(ev) => ev.stopPropagation()}>
            <h1>{t("変更履歴")}</h1>
            <p style={{ color: "#687386", fontSize: 12, margin: 0 }}>{t("本文を上書き保存するたびに、直前の版が最大20件まで保存されます。")}</p>
            {revisions.length === 0 ? (
              <p>{t("まだ履歴はありません（本文が変更されて保存されると記録されます）。")}</p>
            ) : (
              <div className="revisionList">
                {revisions.map((r) => (
                  <div className="revisionRow" key={r.id}>
                    <div><b>{r.title}</b><span>{new Date(r.created_at).toLocaleString("ja-JP")}</span></div>
                    <button onClick={() => restoreRevision(r.id)}>{t("この版に復元")}</button>
                  </div>
                ))}
              </div>
            )}
            <div className="modalActions"><button onClick={() => setShowHistory(false)}>{t("閉じる")}</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
