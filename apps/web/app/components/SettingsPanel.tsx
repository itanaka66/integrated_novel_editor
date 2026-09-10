"use client";
import { useState } from "react";
import { downloadFile, put } from "../lib/api";
import { Project } from "../lib/types";
import { loadModelDefaults, saveModelDefaults } from "../lib/modelDefaults";

export default function SettingsPanel({ project, onSaved }: { project: Project; onSaved: (p: Project) => void }) {
  const [tab, setTab] = useState<"basic" | "ai" | "export">("basic");
  const [exporting, setExporting] = useState<string | null>(null);
  const [form, setForm] = useState({ name: project.name, genre: project.genre, description: project.description, rules: project.rules, episode_goal: project.episode_goal ?? 500 });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [defaults, setDefaults] = useState(loadModelDefaults());

  async function exportAs(format: "txt" | "md" | "epub") {
    setExporting(format);
    try {
      await downloadFile(`/projects/${project.id}/export?format=${format}`, `${project.name}.${format}`);
    } finally { setExporting(null); }
  }

  async function save() {
    setBusy(true); setSaved(false);
    try {
      const x = await put(`/projects/${project.id}`, form);
      onSaved(x);
      setSaved(true);
    } finally { setBusy(false); }
  }

  return (
    <div className="panel">
      <small>SETTINGS</small>
      <h1>設定</h1>
      <div className="twinTabs">
        <button className={tab === "basic" ? "on" : ""} onClick={() => setTab("basic")}>基本設定</button>
        <button className={tab === "ai" ? "on" : ""} onClick={() => setTab("ai")}>AI設定</button>
        <button className={tab === "export" ? "on" : ""} onClick={() => setTab("export")}>エクスポート</button>
      </div>
      {tab === "basic" && (
        <div className="entityForm" style={{ marginTop: 14 }}>
          <label>作品名<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>ジャンル<input value={form.genre} onChange={(e) => setForm({ ...form, genre: e.target.value })} /></label>
          <label>総話数目標<input type="number" value={form.episode_goal} onChange={(e) => setForm({ ...form, episode_goal: Number(e.target.value) })} /></label>
          <label>あらすじ<textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          <label>作品ルール（詳細設定）<textarea value={form.rules} onChange={(e) => setForm({ ...form, rules: e.target.value })} /></label>
          <div className="entityFormActions">
            <button onClick={save} disabled={busy}>{busy ? "保存中..." : "保存"}</button>
            {saved && <span className="savedNote">保存しました</span>}
          </div>
        </div>
      )}
      {tab === "ai" && (
        <div className="entityForm" style={{ marginTop: 14 }}>
          <label>Writerモデル（既定値）<input value={defaults.writer} onChange={(e) => setDefaults({ ...defaults, writer: e.target.value })} placeholder="qwen3.8:27b" /></label>
          <label>Controllerモデル（既定値）<input value={defaults.controller} onChange={(e) => setDefaults({ ...defaults, controller: e.target.value })} placeholder="qwen3:14b" /></label>
          <p style={{ gridColumn: "1/-1", color: "#687386", fontSize: 12 }}>
            ここで保存した値は、このブラウザでの「自動執筆」開始フォームの初期値として使われます。実際のOllama接続先（A770 / RTX3090のURL）はサーバー側の環境変数（CONTROLLER_OLLAMA_URL / OLLAMA_URL）で設定してください。
          </p>
          <div className="entityFormActions">
            <button onClick={() => { saveModelDefaults(defaults); setSaved(true); }}>保存</button>
            {saved && <span className="savedNote">保存しました</span>}
          </div>
        </div>
      )}
      {tab === "export" && (
        <div className="exportSection">
          <p>作品全体のエピソードを書き出します。伏線・キャラクター等の設定データは含まれません（本文のみ）。</p>
          <div className="exportButtons">
            <button onClick={() => exportAs("txt")} disabled={!!exporting}>{exporting === "txt" ? "書き出し中..." : "テキスト (.txt)"}</button>
            <button onClick={() => exportAs("md")} disabled={!!exporting}>{exporting === "md" ? "書き出し中..." : "Markdown (.md)"}</button>
            <button onClick={() => exportAs("epub")} disabled={!!exporting}>{exporting === "epub" ? "書き出し中..." : "EPUB (.epub)"}</button>
          </div>
        </div>
      )}
    </div>
  );
}
