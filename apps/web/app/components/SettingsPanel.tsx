"use client";
import { useEffect, useRef, useState } from "react";
import { api, downloadFile, post, postFile, put } from "../lib/api";
import { Project } from "../lib/types";
import { loadModelDefaults, saveModelDefaults } from "../lib/modelDefaults";

type ImportJob = {
  id: number; mode: "novel" | "episodes"; source_filename: string;
  status: "queued" | "running" | "completed" | "error";
  total_episodes: number; processed_episodes: number; created_episodes: number; updated_episodes: number;
  last_message: string; progress_percent: number;
};

type SystemSettings = {
  database_url_masked: string;
  qdrant_url: string; qdrant_url_is_override: boolean;
  ollama_url: string; ollama_url_is_override: boolean;
  ollama_model: string; ollama_model_is_override: boolean;
  ollama_embed_model: string; ollama_embed_model_is_override: boolean;
  controller_ollama_url: string; controller_ollama_url_is_override: boolean;
  controller_ollama_model: string; controller_ollama_model_is_override: boolean;
};

export default function SettingsPanel({ project, onSaved }: { project: Project; onSaved: (p: Project) => void }) {
  const [tab, setTab] = useState<"basic" | "ai" | "connection" | "import" | "export">("basic");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importJob, setImportJob] = useState<ImportJob | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const importTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [form, setForm] = useState({ name: project.name, genre: project.genre, description: project.description, rules: project.rules, episode_goal: project.episode_goal ?? 500 });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [defaults, setDefaults] = useState(loadModelDefaults());
  const [sys, setSys] = useState<SystemSettings | null>(null);
  const [sysForm, setSysForm] = useState({
    qdrant_url: "", ollama_url: "", ollama_model: "", ollama_embed_model: "",
    controller_ollama_url: "", controller_ollama_model: "",
  });
  const [sysBusy, setSysBusy] = useState(false);
  const [sysSaved, setSysSaved] = useState(false);
  type TestResult = { ok: boolean; message: string; latency_ms: number };
  const [testResults, setTestResults] = useState<Record<string, TestResult | "testing" | undefined>>({});

  async function testConnection(resultKey: string, target: string, url?: string, model?: string) {
    setTestResults((prev) => ({ ...prev, [resultKey]: "testing" }));
    try {
      const r: TestResult = await post("/system-settings/test-connection", { target, url, model });
      setTestResults((prev) => ({ ...prev, [resultKey]: r }));
    } catch {
      setTestResults((prev) => ({ ...prev, [resultKey]: { ok: false, message: "テストに失敗しました（通信エラー）。", latency_ms: 0 } }));
    }
  }

  function TestButton({ target, resultKey, url, model }: { target: string; resultKey?: string; url?: string; model?: string }) {
    const key = resultKey ?? target;
    const result = testResults[key];
    return (
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        <button type="button" onClick={() => testConnection(key, target, url, model)} disabled={result === "testing"}>
          {result === "testing" ? "テスト中..." : "接続テスト"}
        </button>
        {result && result !== "testing" && (
          <span className={result.ok ? "savedNote" : "errorNote"}>
            {result.ok ? "✓" : "✗"} {result.message}（{result.latency_ms}ms）
          </span>
        )}
      </span>
    );
  }

  useEffect(() => {
    if (tab !== "connection") return;
    api("/system-settings").then((s: SystemSettings) => {
      setSys(s);
      setSysForm({
        qdrant_url: s.qdrant_url, ollama_url: s.ollama_url, ollama_model: s.ollama_model,
        ollama_embed_model: s.ollama_embed_model, controller_ollama_url: s.controller_ollama_url,
        controller_ollama_model: s.controller_ollama_model,
      });
    });
  }, [tab]);

  async function saveConnection() {
    setSysBusy(true); setSysSaved(false);
    try {
      const s: SystemSettings = await put("/system-settings", sysForm);
      setSys(s);
      setSysForm({
        qdrant_url: s.qdrant_url, ollama_url: s.ollama_url, ollama_model: s.ollama_model,
        ollama_embed_model: s.ollama_embed_model, controller_ollama_url: s.controller_ollama_url,
        controller_ollama_model: s.controller_ollama_model,
      });
      setSysSaved(true);
    } finally { setSysBusy(false); }
  }

  async function resetField(field: keyof typeof sysForm) {
    setSysBusy(true); setSysSaved(false);
    try {
      const s: SystemSettings = await put("/system-settings", { [field]: "" });
      setSys(s);
      setSysForm({
        qdrant_url: s.qdrant_url, ollama_url: s.ollama_url, ollama_model: s.ollama_model,
        ollama_embed_model: s.ollama_embed_model, controller_ollama_url: s.controller_ollama_url,
        controller_ollama_model: s.controller_ollama_model,
      });
      setSysSaved(true);
    } finally { setSysBusy(false); }
  }

  useEffect(() => () => { if (importTimer.current) clearInterval(importTimer.current); }, []);

  async function startImport() {
    if (!importFile) return;
    setImportBusy(true);
    try {
      const j: ImportJob = await postFile(`/projects/${project.id}/import/episodes`, importFile);
      setImportJob(j);
      importTimer.current = setInterval(async () => {
        const latest: ImportJob = await api(`/import-jobs/${j.id}`);
        setImportJob(latest);
        if ((latest.status === "completed" || latest.status === "error") && importTimer.current) {
          clearInterval(importTimer.current);
        }
      }, 2000);
    } finally { setImportBusy(false); }
  }

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
        <button className={tab === "connection" ? "on" : ""} onClick={() => setTab("connection")}>接続設定</button>
        <button className={tab === "import" ? "on" : ""} onClick={() => setTab("import")}>インポート</button>
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
      {tab === "connection" && (
        <div className="entityForm" style={{ marginTop: 14 }}>
          {!sys && <p style={{ gridColumn: "1/-1" }}>読み込み中...</p>}
          {sys && (
            <>
              <label>
                SQL（データベース）<input value={sys.database_url_masked} readOnly disabled />
              </label>
              <div><TestButton target="database" /></div>
              <p style={{ gridColumn: "1/-1", color: "#687386", fontSize: 12, marginTop: -6 }}>
                データベース接続先は稼働中のアプリから安全に切り替えられないため、読み取り専用です。変更するにはサーバーの環境変数 <code>DATABASE_URL</code> を編集して再起動してください。
              </p>

              <label>
                Qdrant URL {sys.qdrant_url_is_override && <span className="savedNote">（上書き中）</span>}
                <input value={sysForm.qdrant_url} onChange={(e) => setSysForm({ ...sysForm, qdrant_url: e.target.value })} placeholder="http://qdrant:6333" />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <TestButton target="qdrant" url={sysForm.qdrant_url} />
                {sys.qdrant_url_is_override && <button type="button" onClick={() => resetField("qdrant_url")} disabled={sysBusy}>既定値に戻す</button>}
              </div>

              <label>
                Ollama 1（Writer）URL {sys.ollama_url_is_override && <span className="savedNote">（上書き中）</span>}
                <input value={sysForm.ollama_url} onChange={(e) => setSysForm({ ...sysForm, ollama_url: e.target.value })} placeholder="http://ollama:11434" />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <TestButton target="ollama" url={sysForm.ollama_url} model={sysForm.ollama_model} />
                {sys.ollama_url_is_override && <button type="button" onClick={() => resetField("ollama_url")} disabled={sysBusy}>既定値に戻す</button>}
              </div>

              <label>
                Ollama 1（Writer）モデル {sys.ollama_model_is_override && <span className="savedNote">（上書き中）</span>}
                <input value={sysForm.ollama_model} onChange={(e) => setSysForm({ ...sysForm, ollama_model: e.target.value })} />
              </label>
              {sys.ollama_model_is_override && <button type="button" onClick={() => resetField("ollama_model")} disabled={sysBusy}>既定値に戻す</button>}

              <label>
                Ollama 1（Writer）埋め込みモデル {sys.ollama_embed_model_is_override && <span className="savedNote">（上書き中）</span>}
                <input value={sysForm.ollama_embed_model} onChange={(e) => setSysForm({ ...sysForm, ollama_embed_model: e.target.value })} />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <TestButton target="ollama" resultKey="ollama_embed" url={sysForm.ollama_url} model={sysForm.ollama_embed_model} />
                {sys.ollama_embed_model_is_override && <button type="button" onClick={() => resetField("ollama_embed_model")} disabled={sysBusy}>既定値に戻す</button>}
              </div>

              <label>
                Ollama 2（Controller）URL {sys.controller_ollama_url_is_override && <span className="savedNote">（上書き中）</span>}
                <input value={sysForm.controller_ollama_url} onChange={(e) => setSysForm({ ...sysForm, controller_ollama_url: e.target.value })} placeholder="http://ollama:11434" />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <TestButton target="controller_ollama" url={sysForm.controller_ollama_url} model={sysForm.controller_ollama_model} />
                {sys.controller_ollama_url_is_override && <button type="button" onClick={() => resetField("controller_ollama_url")} disabled={sysBusy}>既定値に戻す</button>}
              </div>

              <label>
                Ollama 2（Controller）モデル {sys.controller_ollama_model_is_override && <span className="savedNote">（上書き中）</span>}
                <input value={sysForm.controller_ollama_model} onChange={(e) => setSysForm({ ...sysForm, controller_ollama_model: e.target.value })} />
              </label>
              {sys.controller_ollama_model_is_override && <button type="button" onClick={() => resetField("controller_ollama_model")} disabled={sysBusy}>既定値に戻す</button>}

              <p style={{ gridColumn: "1/-1", color: "#687386", fontSize: 12 }}>
                各項目を空欄にして保存すると、サーバーの環境変数の既定値に戻ります。Qdrant・Ollamaはステートレスなクライアントのため、保存すると次回の呼び出しから即座に反映されます（再起動不要）。
              </p>
              <div className="entityFormActions">
                <button onClick={saveConnection} disabled={sysBusy}>{sysBusy ? "保存中..." : "保存"}</button>
                {sysSaved && <span className="savedNote">保存しました</span>}
              </div>
            </>
          )}
        </div>
      )}
      {tab === "import" && (
        <div className="entityForm" style={{ marginTop: 14 }}>
          <p style={{ gridColumn: "1/-1" }}>
            なろう形式のテキストファイル（本編・下書きのどちらでも可）から、この作品「{project.name}」にエピソードを追加インポートします。既存の話数と重複する場合は本文を上書きし、上書き前の内容は改訂履歴に保存されます。
          </p>
          {(!importJob || importJob.status === "completed" || importJob.status === "error") && (
            <>
              <label>
                ファイル *
                <input type="file" accept=".txt" onChange={(e) => setImportFile(e.target.files?.[0] ?? null)} />
              </label>
              <div className="entityFormActions">
                <button onClick={startImport} disabled={importBusy || !importFile}>{importBusy ? "開始中..." : "インポート開始"}</button>
              </div>
            </>
          )}
          {importJob && (
            <div style={{ gridColumn: "1/-1" }}>
              <p><b>{importJob.source_filename}</b></p>
              <div className="progress"><i style={{ width: `${importJob.progress_percent}%` }} /></div>
              <p className="searchSource">
                {importJob.status === "queued" && "キューに追加しました…"}
                {importJob.status === "running" && `${importJob.processed_episodes}/${importJob.total_episodes}話 処理中… ${importJob.last_message}`}
                {importJob.status === "completed" && importJob.last_message}
                {importJob.status === "error" && `エラー: ${importJob.last_message}`}
              </p>
            </div>
          )}
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
