"use client";
import { useEffect, useRef, useState } from "react";
import CoverSettings from "./CoverSettings";
import DeleteProjectPanel from "./DeleteProjectPanel";
import { api, downloadFile, post, postFile, put } from "../lib/api";
import { Project } from "../lib/types";
import { loadModelDefaults, saveModelDefaults } from "../lib/modelDefaults";
import { ensureNotificationPermission, notify } from "../lib/notify";
import { t } from "../lib/i18n";

type ImportJob = {
  id: number; mode: "novel" | "episodes"; source_filename: string;
  status: "queued" | "running" | "completed" | "error";
  total_episodes: number; processed_episodes: number; created_episodes: number; updated_episodes: number;
  last_message: string; progress_percent: number;
};

type BackupEntry = { timestamp: string; has_postgres: boolean; has_qdrant: boolean; size_bytes: number };
type BackupStatus = { enabled: boolean; interval_seconds: number; retention_count: number; backup_dir: string; backups: BackupEntry[] };
type BackupResult = { timestamp: string; postgres_ok: boolean; postgres_error: string; qdrant_ok: boolean; qdrant_error: string; duration_seconds: number };

type SystemSettings = {
  database_url_masked: string;
  qdrant_url: string; qdrant_url_is_override: boolean;
  ollama_url: string; ollama_url_is_override: boolean;
  ollama_model: string; ollama_model_is_override: boolean;
  ollama_embed_model: string; ollama_embed_model_is_override: boolean;
  controller_ollama_url: string; controller_ollama_url_is_override: boolean;
  controller_ollama_model: string; controller_ollama_model_is_override: boolean;
  cors_origins: string; // read-only — env/.env only, not editable from here
};

// A style guide is never required to write, but leaving it truly blank
// means "文章校正" (proofread) has nothing to check against — this generic
// baseline fills the field automatically the first time a project's
// Settings screen loads with no style guide saved yet, so proofreading
// always has *something* to work with. It's just a starting point in the
// (unsaved) form; explicit "スタイルガイド生成" below replaces it with one
// tailored to an actual use case, and either way nothing is written to the
// project until 保存 is clicked.
const DEFAULT_STYLE_GUIDE = [
  "・文体は「である調」で統一する",
  "・専門用語や造語は初出時に簡単な説明を添える",
  "・一文を短く区切り、読点を使いすぎない",
  "・表記ゆれ（漢字/ひらがな/カタカナ）を統一する",
  "・冗長な言い回しを避け、簡潔に書く",
].join("\n");

const STYLE_GUIDE_CATEGORIES: { key: string; label: string; hint: string }[] = [
  { key: "translation", label: t("翻訳文書・ローカライズ"), hint: t("複数の翻訳者が関わるため、表現や文体（です・ます調など）を揃えるために必要。") },
  { key: "technical", label: t("Webサイト・マニュアル・技術文書（テクニカルライティング）"), hint: t("読者が迷わないよう、専門用語の扱い、簡潔な表現、レイアウトを統一する。") },
  { key: "academic", label: t("学術論文・研究レポート"), hint: t("引用の形式や文献リストの書き方（APA、MLA、シカゴ・マニュアルなど）を統一するため。") },
  { key: "pr", label: t("広報・ニュース・プレスリリース"), hint: t("企業イメージや媒体の信頼性を保つため、用字用語のルール（記者ハンドブックなど）が必要。") },
];
const ACADEMIC_CITATION_STYLES = ["APA", "MLA", "シカゴ・マニュアル", "その他"];

export default function SettingsPanel({ project, onSaved, onDeleted }: { project: Project; onSaved: (p: Project) => void; onDeleted?: () => void }) {
  const [tab, setTab] = useState<"basic" | "ai" | "connection" | "import" | "backup" | "export" | "cover" | "delete">("basic");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importJob, setImportJob] = useState<ImportJob | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const importTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [form, setForm] = useState({ name: project.name, genre: project.genre, description: project.description, rules: project.rules, episode_goal: project.episode_goal ?? 500, style_guide: project.style_guide ?? "", author: project.author ?? "" });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [styleGuideBusy, setStyleGuideBusy] = useState(false);
  const [showStyleGuidePicker, setShowStyleGuidePicker] = useState(false);
  const [pendingAcademic, setPendingAcademic] = useState(false);
  const [academicDetail, setAcademicDetail] = useState(ACADEMIC_CITATION_STYLES[0]);

  useEffect(() => {
    if (tab !== "basic") return;
    if (!project.style_guide && !form.style_guide) setForm((f) => ({ ...f, style_guide: DEFAULT_STYLE_GUIDE }));
  }, [tab]);

  async function generateStyleGuide(category: string, detail?: string) {
    setStyleGuideBusy(true);
    try {
      const { style_guide }: { style_guide: string } = await post(`/projects/${project.id}/style-guide/generate`, { category, detail: detail || "" });
      setForm((f) => ({ ...f, style_guide }));
      setShowStyleGuidePicker(false);
      setPendingAcademic(false);
    } finally { setStyleGuideBusy(false); }
  }
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
  const [backupStatus, setBackupStatus] = useState<BackupStatus | null>(null);
  const [backupBusy, setBackupBusy] = useState(false);
  const [backupResult, setBackupResult] = useState<BackupResult | null>(null);

  async function loadBackupStatus() {
    setBackupStatus(await api("/backups"));
  }

  async function runBackupNow() {
    setBackupBusy(true); setBackupResult(null);
    try {
      const r: BackupResult = await post("/backups/run", {});
      setBackupResult(r);
      await loadBackupStatus();
    } finally { setBackupBusy(false); }
  }

  async function testConnection(resultKey: string, target: string, url?: string, model?: string) {
    setTestResults((prev) => ({ ...prev, [resultKey]: "testing" }));
    try {
      const r: TestResult = await post("/system-settings/test-connection", { target, url, model });
      setTestResults((prev) => ({ ...prev, [resultKey]: r }));
    } catch {
      setTestResults((prev) => ({ ...prev, [resultKey]: { ok: false, message: t("テストに失敗しました（通信エラー）。"), latency_ms: 0 } }));
    }
  }

  function TestButton({ target, resultKey, url, model }: { target: string; resultKey?: string; url?: string; model?: string }) {
    const key = resultKey ?? target;
    const result = testResults[key];
    return (
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        <button type="button" onClick={() => testConnection(key, target, url, model)} disabled={result === "testing"}>
          {result === "testing" ? t("テスト中...") : t("接続テスト")}
        </button>
        {result && result !== "testing" && (
          <span className={result.ok ? "savedNote" : "errorNote"}>
            {result.ok ? "✓" : "✗"} {result.message} ({result.latency_ms}ms)
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

  useEffect(() => {
    if (tab !== "backup") return;
    loadBackupStatus();
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
    ensureNotificationPermission();
    try {
      const j: ImportJob = await postFile(`/projects/${project.id}/import/episodes`, importFile);
      setImportJob(j);
      importTimer.current = setInterval(async () => {
        const latest: ImportJob = await api(`/import-jobs/${j.id}`);
        setImportJob(latest);
        if ((latest.status === "completed" || latest.status === "error") && importTimer.current) {
          clearInterval(importTimer.current);
          notify(
            latest.status === "completed" ? t("インポートが完了しました") : t("インポートでエラーが発生しました"),
            `${latest.source_filename}${latest.status === "completed" ? t("（新規{c}話・更新{u}話）", { c: latest.created_episodes, u: latest.updated_episodes }) : `: ${latest.last_message}`}`,
          );
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
      <h1>{t("設定")}</h1>
      <div className="twinTabs">
        <button className={tab === "basic" ? "on" : ""} onClick={() => setTab("basic")}>{t("基本設定")}</button>
        <button className={tab === "ai" ? "on" : ""} onClick={() => setTab("ai")}>{t("AI設定")}</button>
        <button className={tab === "connection" ? "on" : ""} onClick={() => setTab("connection")}>{t("接続設定")}</button>
        <button className={tab === "import" ? "on" : ""} onClick={() => setTab("import")}>{t("インポート")}</button>
        <button className={tab === "backup" ? "on" : ""} onClick={() => setTab("backup")}>{t("バックアップ")}</button>
        <button className={tab === "export" ? "on" : ""} onClick={() => setTab("export")}>{t("エクスポート")}</button>
        <button className={tab === "cover" ? "on" : ""} onClick={() => setTab("cover")}>{t("表紙画像")}</button>
        {onDeleted && <button className={tab === "delete" ? "on" : ""} onClick={() => setTab("delete")}>{t("作品の削除")}</button>}
      </div>
      {tab === "basic" && (
        <div className="entityForm" style={{ marginTop: 14 }}>
          <label>{t("作品名")}<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>{t("著者名")}<input value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} placeholder={t("表紙画像に入れる名前")} /></label>
          <label>{t("ジャンル")}<input value={form.genre} onChange={(e) => setForm({ ...form, genre: e.target.value })} /></label>
          <label>{t("総話数目標")}<input type="number" value={form.episode_goal} onChange={(e) => setForm({ ...form, episode_goal: Number(e.target.value) })} /></label>
          <label>{t("あらすじ")}<textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          <label>{t("作品ルール（詳細設定）")}<textarea value={form.rules} onChange={(e) => setForm({ ...form, rules: e.target.value })} /></label>
          <label style={{ gridColumn: "1/-1" }}>
            {t("スタイルガイド")}
            <textarea value={form.style_guide} onChange={(e) => setForm({ ...form, style_guide: e.target.value })} placeholder={t("「スタイルガイド生成」で作成するか、直接入力してください。")} style={{ minHeight: 120 }} />
          </label>
          <div style={{ gridColumn: "1/-1" }}>
            <button type="button" onClick={() => setShowStyleGuidePicker(true)} disabled={styleGuideBusy}>{styleGuideBusy ? t("生成中...") : t("📐 スタイルガイド生成")}</button>
          </div>
          <p style={{ gridColumn: "1/-1", color: "#687386", fontSize: 12, marginTop: -6 }}>
            {t("用途に近い種類を選ぶと、既存の本文サンプルの文体・表記の傾向も踏まえて、より適したスタイルガイドを生成します。生成後は自由に編集でき、保存すると執筆画面の「文章校正」で使われます。")}
          </p>
          <div className="entityFormActions">
            <button className="saveButton" onClick={save} disabled={busy}>{busy ? t("保存中...") : t("保存")}</button>
            {saved && <span className="savedNote">{t("保存しました")}</span>}
          </div>
        </div>
      )}
      {showStyleGuidePicker && (
        <div className="modalOverlay" onClick={() => { setShowStyleGuidePicker(false); setPendingAcademic(false); }}>
          <div className="modalCard" onClick={(ev) => ev.stopPropagation()}>
            <h1>{t("スタイルガイドの種類を選択")}</h1>
            <p style={{ color: "#687386", fontSize: 12 }}>{t("用途に近いものを選んでください。")}</p>
            {!pendingAcademic && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {STYLE_GUIDE_CATEGORIES.map((c) => (
                  <button
                    key={c.key}
                    type="button"
                    disabled={styleGuideBusy}
                    onClick={() => (c.key === "academic" ? setPendingAcademic(true) : generateStyleGuide(c.key))}
                    style={{ textAlign: "left" }}
                  >
                    <b>{c.label}</b>
                    <div style={{ fontSize: 11, color: "#687386", fontWeight: "normal" }}>{c.hint}</div>
                  </button>
                ))}
              </div>
            )}
            {pendingAcademic && (
              <>
                <label>
                  {t("引用形式")}
                  <select value={academicDetail} onChange={(e) => setAcademicDetail(e.target.value)}>
                    {ACADEMIC_CITATION_STYLES.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </label>
                <div className="modalActions">
                  <button type="button" onClick={() => setPendingAcademic(false)}>{t("戻る")}</button>
                  <button type="button" onClick={() => generateStyleGuide("academic", academicDetail)} disabled={styleGuideBusy}>{styleGuideBusy ? t("生成中...") : t("この形式で生成する")}</button>
                </div>
              </>
            )}
            <div className="modalActions">
              <button type="button" onClick={() => { setShowStyleGuidePicker(false); setPendingAcademic(false); }}>{t("キャンセル")}</button>
            </div>
          </div>
        </div>
      )}
      {tab === "ai" && (
        <div className="entityForm" style={{ marginTop: 14 }}>
          <label>{t("Writerモデル（既定値）")}<input value={defaults.writer} onChange={(e) => setDefaults({ ...defaults, writer: e.target.value })} placeholder="qwen3.8:27b" /></label>
          <label>{t("Controllerモデル（既定値）")}<input value={defaults.controller} onChange={(e) => setDefaults({ ...defaults, controller: e.target.value })} placeholder="qwen3:14b" /></label>
          <p style={{ gridColumn: "1/-1", color: "#687386", fontSize: 12 }}>
            {t("ここで保存した値は、このブラウザでの「自動執筆」開始フォームの初期値として使われます。実際のOllama接続先（A770 / RTX3090のURL）はサーバー側の環境変数（CONTROLLER_OLLAMA_URL / OLLAMA_URL）で設定してください。")}
          </p>
          <div className="entityFormActions">
            <button className="saveButton" onClick={() => { saveModelDefaults(defaults); setSaved(true); }}>{t("保存")}</button>
            {saved && <span className="savedNote">{t("保存しました")}</span>}
          </div>
        </div>
      )}
      {tab === "connection" && (
        <div className="entityForm" style={{ marginTop: 14 }}>
          {!sys && <p style={{ gridColumn: "1/-1" }}>{t("読み込み中...")}</p>}
          {sys && (
            <>
              <label>
                {t("SQL（データベース）")}<input value={sys.database_url_masked} readOnly disabled />
              </label>
              <div><TestButton target="database" /></div>
              <p style={{ gridColumn: "1/-1", color: "#687386", fontSize: 12, marginTop: -6 }}>
                {t("データベース接続先は稼働中のアプリから安全に切り替えられないため、読み取り専用です。変更するにはサーバーの環境変数 DATABASE_URL を編集して再起動してください。")}
              </p>

              <label>
                Qdrant URL {sys.qdrant_url_is_override && <span className="savedNote">{t("（上書き中）")}</span>}
                <input value={sysForm.qdrant_url} onChange={(e) => setSysForm({ ...sysForm, qdrant_url: e.target.value })} placeholder="http://qdrant:6333" />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <TestButton target="qdrant" url={sysForm.qdrant_url} />
                {sys.qdrant_url_is_override && <button type="button" onClick={() => resetField("qdrant_url")} disabled={sysBusy}>{t("既定値に戻す")}</button>}
              </div>

              <label>
                {t("Ollama 1（Writer）URL")} {sys.ollama_url_is_override && <span className="savedNote">{t("（上書き中）")}</span>}
                <input value={sysForm.ollama_url} onChange={(e) => setSysForm({ ...sysForm, ollama_url: e.target.value })} placeholder="http://ollama:11434" />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <TestButton target="ollama" url={sysForm.ollama_url} model={sysForm.ollama_model} />
                {sys.ollama_url_is_override && <button type="button" onClick={() => resetField("ollama_url")} disabled={sysBusy}>{t("既定値に戻す")}</button>}
              </div>

              <label>
                {t("Ollama 1（Writer）モデル")} {sys.ollama_model_is_override && <span className="savedNote">{t("（上書き中）")}</span>}
                <input value={sysForm.ollama_model} onChange={(e) => setSysForm({ ...sysForm, ollama_model: e.target.value })} />
              </label>
              {sys.ollama_model_is_override && <button type="button" onClick={() => resetField("ollama_model")} disabled={sysBusy}>{t("既定値に戻す")}</button>}

              <label>
                {t("Ollama 1（Writer）埋め込みモデル")} {sys.ollama_embed_model_is_override && <span className="savedNote">{t("（上書き中）")}</span>}
                <input value={sysForm.ollama_embed_model} onChange={(e) => setSysForm({ ...sysForm, ollama_embed_model: e.target.value })} />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <TestButton target="ollama" resultKey="ollama_embed" url={sysForm.ollama_url} model={sysForm.ollama_embed_model} />
                {sys.ollama_embed_model_is_override && <button type="button" onClick={() => resetField("ollama_embed_model")} disabled={sysBusy}>{t("既定値に戻す")}</button>}
              </div>

              <label>
                {t("Ollama 2（Controller）URL")} {sys.controller_ollama_url_is_override && <span className="savedNote">{t("（上書き中）")}</span>}
                <input value={sysForm.controller_ollama_url} onChange={(e) => setSysForm({ ...sysForm, controller_ollama_url: e.target.value })} placeholder="http://ollama:11434" />
              </label>
              <div style={{ display: "flex", gap: 8 }}>
                <TestButton target="controller_ollama" url={sysForm.controller_ollama_url} model={sysForm.controller_ollama_model} />
                {sys.controller_ollama_url_is_override && <button type="button" onClick={() => resetField("controller_ollama_url")} disabled={sysBusy}>{t("既定値に戻す")}</button>}
              </div>

              <label>
                {t("Ollama 2（Controller）モデル")} {sys.controller_ollama_model_is_override && <span className="savedNote">{t("（上書き中）")}</span>}
                <input value={sysForm.controller_ollama_model} onChange={(e) => setSysForm({ ...sysForm, controller_ollama_model: e.target.value })} />
              </label>
              {sys.controller_ollama_model_is_override && <button type="button" onClick={() => resetField("controller_ollama_model")} disabled={sysBusy}>{t("既定値に戻す")}</button>}

              <p style={{ gridColumn: "1/-1", color: "#687386", fontSize: 12 }}>
                {t("各項目を空欄にして保存すると、サーバーの環境変数の既定値に戻ります。Qdrant・Ollamaはいずれも保存すると次回の呼び出しから即座に反映されます（再起動不要）。")}
              </p>
              <div className="entityFormActions">
                <button className="saveButton" onClick={saveConnection} disabled={sysBusy}>{sysBusy ? t("保存中...") : t("保存")}</button>
                {sysSaved && <span className="savedNote">{t("保存しました")}</span>}
              </div>
            </>
          )}
        </div>
      )}
      {tab === "cover" && <CoverSettings />}
      {tab === "delete" && onDeleted && <DeleteProjectPanel project={project} onDeleted={onDeleted} />}
      {tab === "import" && (
        <div className="entityForm" style={{ marginTop: 14 }}>
          <p style={{ gridColumn: "1/-1" }}>
            {t("なろう形式のテキストファイル（本編・下書きのどちらでも可）から、この作品「{name}」にエピソードを追加インポートします。既存の話数と重複する場合は本文を上書きし、上書き前の内容は改訂履歴に保存されます。", { name: project.name })}
          </p>
          {(!importJob || importJob.status === "completed" || importJob.status === "error") && (
            <>
              <label>
                {t("ファイル *")}
                <input type="file" accept=".txt" onChange={(e) => setImportFile(e.target.files?.[0] ?? null)} />
              </label>
              <div className="entityFormActions">
                <button className="saveButton" onClick={startImport} disabled={importBusy || !importFile}>{importBusy ? t("開始中...") : t("インポート開始")}</button>
              </div>
            </>
          )}
          {importJob && (
            <div style={{ gridColumn: "1/-1" }}>
              <p><b>{importJob.source_filename}</b></p>
              <div className="progress"><i style={{ width: `${importJob.progress_percent}%` }} /></div>
              <p className="searchSource">
                {importJob.status === "queued" && t("キューに追加しました…")}
                {importJob.status === "running" && t("{done}/{total}話 処理中… {msg}", { done: importJob.processed_episodes, total: importJob.total_episodes, msg: importJob.last_message })}
                {importJob.status === "completed" && importJob.last_message}
                {importJob.status === "error" && t("エラー: {msg}", { msg: importJob.last_message })}
              </p>
            </div>
          )}
        </div>
      )}
      {tab === "backup" && (
        <div className="entityForm" style={{ marginTop: 14 }}>
          {!backupStatus && <p style={{ gridColumn: "1/-1" }}>{t("読み込み中...")}</p>}
          {backupStatus && (
            <>
              <p style={{ gridColumn: "1/-1" }}>
                {t("データベース（PostgreSQL）とQdrantのバックアップです。全プロジェクト共通のサーバー全体の機能で、この作品専用の設定ではありません。")}
              </p>
              <p style={{ gridColumn: "1/-1", color: "#687386", fontSize: 12 }}>
                {t("自動バックアップ：")}{backupStatus.enabled ? (
                  <span className="savedNote">✓ {t("有効（{h}時間ごと、直近{n}件を保持、保存先: {dir}）", { h: Math.round(backupStatus.interval_seconds / 3600), n: backupStatus.retention_count, dir: backupStatus.backup_dir })}</span>
                ) : (
                  <span>{t("無効（環境変数 BACKUP_ENABLED=true で有効化できます。詳しくは動作要件のドキュメントを参照してください）")}</span>
                )}
              </p>
              <div className="entityFormActions">
                <button className="saveButton" onClick={runBackupNow} disabled={backupBusy}>{backupBusy ? t("バックアップ中...") : t("今すぐバックアップ")}</button>
              </div>
              {backupResult && (
                <p style={{ gridColumn: "1/-1" }} className={backupResult.postgres_ok ? "savedNote" : "errorNote"}>
                  {backupResult.postgres_ok ? "✓" : "✗"} PostgreSQL: {backupResult.postgres_ok ? t("成功") : backupResult.postgres_error}
                  {" / "}Qdrant: {backupResult.qdrant_ok ? t("成功") : backupResult.qdrant_error}
                  {t("（{n}秒）", { n: backupResult.duration_seconds })}
                </p>
              )}
              <div style={{ gridColumn: "1/-1" }}>
                <small>{t("バックアップ履歴（最新{n}件）", { n: backupStatus.backups.length })}</small>
                {backupStatus.backups.length === 0 && <p className="searchSource">{t("まだバックアップがありません。")}</p>}
                {backupStatus.backups.map((b) => (
                  <div className="resultCard" key={b.timestamp}>
                    <b>{b.timestamp}</b>
                    <p>
                      PostgreSQL: {b.has_postgres ? "✓" : "—"} / Qdrant: {b.has_qdrant ? "✓" : "—"} / {(b.size_bytes / 1024 / 1024).toFixed(1)}MB
                    </p>
                  </div>
                ))}
              </div>
              <p style={{ gridColumn: "1/-1", color: "#687386", fontSize: 12 }}>
                {t("リストアは`scripts/restore.sh`から行います（確認プロンプトなしで現在のデータを置き換えるため、パスの確認を必ず行ってください）。詳しくは操作マニュアルの「バックアップとリストア」を参照してください。")}
              </p>
            </>
          )}
        </div>
      )}
      {tab === "export" && (
        <div className="exportSection">
          <p>{t("作品全体のエピソードを書き出します。伏線・キャラクター等の設定データは含まれません（本文のみ）。")}</p>
          <div className="exportButtons">
            <button onClick={() => exportAs("txt")} disabled={!!exporting}>{exporting === "txt" ? t("書き出し中...") : t("テキスト (.txt)")}</button>
            <button onClick={() => exportAs("md")} disabled={!!exporting}>{exporting === "md" ? t("書き出し中...") : "Markdown (.md)"}</button>
            <button onClick={() => exportAs("epub")} disabled={!!exporting}>{exporting === "epub" ? t("書き出し中...") : "EPUB (.epub)"}</button>
          </div>
        </div>
      )}
    </div>
  );
}
