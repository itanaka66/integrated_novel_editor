"use client";
import { useState } from "react";
import { post } from "../lib/api";

export default function SearchPanel({ projectId }: { projectId: number }) {
  const [q, setQ] = useState(""), [r, setR] = useState<any[]>([]), [source, setSource] = useState(""), [busy, setBusy] = useState(false);

  async function search() {
    setBusy(true);
    try {
      const x = await post("/rag/search", { project_id: projectId, query: q, limit: 8 });
      setR(x.results || []); setSource(x.source || "");
    } finally { setBusy(false); }
  }
  async function reindex() { const x = await post("/rag/index", { project_id: projectId }); alert(`索引を再構築しました (${x.indexed ?? 0}件)`); }

  return (
    <div className="panel">
      <small>SEARCH</small>
      <h1>検索</h1>
      <p>本文をベクトル検索（Qdrant）します。接続できない場合はPostgreSQLの全文一致にフォールバックします。</p>
      <div className="ragbar">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="過去本文を意味検索" onKeyDown={(e) => e.key === "Enter" && search()} />
        <button onClick={search}>{busy ? "検索中…" : "検索"}</button>
        <button onClick={reindex}>再構築</button>
      </div>
      {source && <p className="searchSource">検索元：{source === "qdrant" ? "セマンティック検索 (Qdrant)" : "全文一致 (PostgreSQL フォールバック)"}</p>}
      {r.map((x, i) => (
        <div className="resultCard" key={i}>
          <b>{x.title}</b>
          <p>{x.text}</p>
        </div>
      ))}
    </div>
  );
}
