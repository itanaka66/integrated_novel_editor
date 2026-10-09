"use client";
import { useEffect, useState } from "react";
import { api, post } from "../lib/api";
import { Project } from "../lib/types";
import { t } from "../lib/i18n";

type TextSearchMatch = { episode_id: number; number: number; title: string; count: number; snippets: string[] };
type TextReplaceEpisodeResult = { episode_id: number; number: number; title: string; replaced_count: number };

export default function SearchPanel({ projectId }: { projectId: number }) {
  const [mode, setMode] = useState<"semantic" | "replace">("semantic");
  const [q, setQ] = useState(""), [r, setR] = useState<any[]>([]), [source, setSource] = useState(""), [busy, setBusy] = useState(false);
  const [allProjects, setAllProjects] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);

  const [findQ, setFindQ] = useState("");
  const [replaceQ, setReplaceQ] = useState("");
  const [caseSensitive, setCaseSensitive] = useState(true);
  const [matches, setMatches] = useState<TextSearchMatch[]>([]);
  const [totalMatches, setTotalMatches] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [findBusy, setFindBusy] = useState(false);
  const [replaceBusy, setReplaceBusy] = useState(false);
  const [replaceResult, setReplaceResult] = useState<{ episodes: TextReplaceEpisodeResult[]; total_replaced: number } | null>(null);
  const [searched, setSearched] = useState(false);

  useEffect(() => { api("/projects").then(setProjects); }, []);
  const nameOf = (pid: number) => projects.find((p) => p.id === pid)?.name || `#${pid}`;

  async function search() {
    setBusy(true);
    try {
      const x = allProjects
        ? await post("/rag/search-all", { query: q, limit: 12 })
        : await post("/rag/search", { project_id: projectId, query: q, limit: 8 });
      setR(x.results || []); setSource(x.source || "");
    } finally { setBusy(false); }
  }
  async function reindex() { const x = await post("/rag/index", { project_id: projectId }); alert(t("索引を再構築しました ({n}件)", { n: x.indexed ?? 0 })); }

  async function findAll() {
    if (!findQ) return;
    setFindBusy(true); setReplaceResult(null);
    try {
      const x = await api(`/projects/${projectId}/text-search?${new URLSearchParams({ query: findQ, case_sensitive: String(caseSensitive) })}`);
      setMatches(x.matches || []); setTotalMatches(x.total_matches || 0);
      setSelected(new Set((x.matches || []).map((m: TextSearchMatch) => m.episode_id)));
      setSearched(true);
    } finally { setFindBusy(false); }
  }

  function toggleSelected(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function replaceAll() {
    if (!findQ || selected.size === 0) return;
    if (!confirm(t("選択した{n}話で「{find}」を「{replace}」に置換します。元に戻したい場合は各話の改訂履歴から復元できます。よろしいですか？", { n: selected.size, find: findQ, replace: replaceQ }))) return;
    setReplaceBusy(true);
    try {
      const x = await post(`/projects/${projectId}/text-replace`, {
        query: findQ, replacement: replaceQ, case_sensitive: caseSensitive, episode_ids: Array.from(selected),
      });
      setReplaceResult(x);
      setMatches([]); setTotalMatches(0); setSelected(new Set()); setSearched(false);
    } finally { setReplaceBusy(false); }
  }

  return (
    <div className="panel">
      <small>SEARCH</small>
      <h1>{t("検索")}</h1>
      <div className="twinTabs">
        <button className={mode === "semantic" ? "on" : ""} onClick={() => setMode("semantic")}>{t("意味検索")}</button>
        <button className={mode === "replace" ? "on" : ""} onClick={() => setMode("replace")}>{t("検索・全置換")}</button>
      </div>
      {mode === "semantic" && (
        <>
          <p>{t("本文をベクトル検索（Qdrant）します。接続できない場合はPostgreSQLの全文一致にフォールバックします。")}</p>
          <label className="searchAllToggle">
            <input type="checkbox" checked={allProjects} onChange={(e) => setAllProjects(e.target.checked)} /> {t("すべての作品を検索対象にする")}
          </label>
          <div className="ragbar">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={allProjects ? t("全作品の本文を意味検索") : t("この作品の本文を意味検索")} onKeyDown={(e) => e.key === "Enter" && search()} />
            <button onClick={search}>{busy ? t("検索中…") : t("検索")}</button>
            {!allProjects && <button onClick={reindex}>{t("再構築")}</button>}
          </div>
          {source && <p className="searchSource">{t("検索元：")}{source === "qdrant" ? t("セマンティック検索 (Qdrant)") : t("全文一致 (PostgreSQL フォールバック)")}</p>}
          {r.map((x, i) => (
            <div className="resultCard" key={i}>
              <b>{x.title}</b>
              {allProjects && <span className="resultProject">{x.project_name || nameOf(x.project_id)}</span>}
              <p>{x.text}</p>
            </div>
          ))}
        </>
      )}
      {mode === "replace" && (
        <>
          <p>{t("この作品内の全話本文を対象に、文字列を検索・一括置換します。置換前の内容は改訂履歴に自動保存されます。")}</p>
          <div className="ragbar">
            <input value={findQ} onChange={(e) => setFindQ(e.target.value)} placeholder={t("検索する文字列")} onKeyDown={(e) => e.key === "Enter" && findAll()} />
            <input value={replaceQ} onChange={(e) => setReplaceQ(e.target.value)} placeholder={t("置換後の文字列")} />
            <button onClick={findAll} disabled={!findQ}>{findBusy ? t("検索中…") : t("検索")}</button>
          </div>
          <label className="searchAllToggle">
            <input type="checkbox" checked={caseSensitive} onChange={(e) => setCaseSensitive(e.target.checked)} /> {t("大文字・小文字を区別する")}
          </label>
          {totalMatches > 0 && (
            <>
              <p className="searchSource">{t("{n}話で合計{total}件ヒット。置換したい話を選択してください。", { n: matches.length, total: totalMatches })}</p>
              {matches.map((m) => (
                <div className="resultCard" key={m.episode_id}>
                  <label style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                    <input type="checkbox" checked={selected.has(m.episode_id)} onChange={() => toggleSelected(m.episode_id)} />
                    <b>{t("第{n}話", { n: m.number })} {m.title}</b>
                    <span className="resultProject">{t("{n}件", { n: m.count })}</span>
                  </label>
                  {m.snippets.map((s, i) => <p key={i}>{s}</p>)}
                </div>
              ))}
              <div className="entityFormActions">
                <button onClick={replaceAll} disabled={replaceBusy || selected.size === 0}>{replaceBusy ? t("置換中…") : t("選択した{n}話を置換", { n: selected.size })}</button>
              </div>
            </>
          )}
          {searched && !findBusy && totalMatches === 0 && replaceResult === null && (
            <p className="searchSource">{t("一致する話がありませんでした。")}</p>
          )}
          {replaceResult && (
            <p className="searchSource">
              {t("{n}話・合計{total}件を置換しました。", { n: replaceResult.episodes.length, total: replaceResult.total_replaced })}
            </p>
          )}
        </>
      )}
    </div>
  );
}
