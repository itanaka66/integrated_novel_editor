"use client";
import { useCallback, useEffect, useState } from "react";
import { api, fetchBlobUrl } from "../lib/api";
import { t } from "../lib/i18n";

type CoverImage = { filename: string; provider: string; selected: boolean };
type CoverJob = { id: number; status: string; filename: string | null; last_message: string };

const PROVIDERS = [
  { key: "comfyui", label: t("ComfyUI（ローカル）") },
  { key: "higgsfield", label: t("Higgsfield（クラウド）") },
];
const JSON_HEADERS = { "Content-Type": "application/json" };

function Thumb({ projectId, image, onSelect }: { projectId: number; image: CoverImage; onSelect: () => void }) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let url = "";
    let alive = true;
    fetchBlobUrl(`/projects/${projectId}/covers/${image.filename}`).then((u) => { url = u; if (alive) setSrc(u); }).catch(() => {});
    return () => { alive = false; if (url) URL.revokeObjectURL(url); };
  }, [projectId, image.filename]);
  return (
    <button onClick={onSelect} title={image.selected ? t("採用中の表紙") : t("この画像を表紙にする")}
      style={{ padding: 0, border: image.selected ? "3px solid #2e7d32" : "1px solid #ccc", background: "none", width: 120 }}>
      {src ? <img src={src} alt={image.filename} style={{ width: "100%", display: "block" }} /> : <span>…</span>}
      <small>{image.selected ? t("✓ 採用中") : image.provider}</small>
    </button>
  );
}

export default function CoverPanel({ projectId }: { projectId: number }) {
  const [prompt, setPrompt] = useState("");
  const [provider, setProvider] = useState("comfyui");
  const [images, setImages] = useState<CoverImage[]>([]);
  const [job, setJob] = useState<CoverJob | null>(null);
  const [busyPrompt, setBusyPrompt] = useState(false);
  const [error, setError] = useState("");
  const generating = !!job && (job.status === "queued" || job.status === "running");

  const reload = useCallback(() => api(`/projects/${projectId}/covers`).then((r) => { if (Array.isArray(r)) setImages(r); }), [projectId]);
  useEffect(() => { reload(); }, [reload]);

  useEffect(() => {
    if (!job || !generating) return;
    const timer = setInterval(async () => {
      try {
        const j = await api(`/cover-jobs/${job.id}`);
        if (!j?.id) { setError(j?.detail || t("進捗の取得に失敗しました")); setJob(null); return; }
        setJob(j);
        if (j.status === "completed") reload();
      } catch { /* transient; retry on next tick */ }
    }, 2000);
    return () => clearInterval(timer);
  }, [job, generating, reload]);

  async function makePrompt() {
    setBusyPrompt(true); setError("");
    try {
      const r = await api(`/projects/${projectId}/cover/prompt`, { method: "POST" });
      if (r?.prompt) setPrompt(r.prompt); else setError(r?.detail || t("プロンプトを生成できませんでした"));
    } catch (e) { setError(e instanceof Error ? e.message : t("プロンプトを生成できませんでした")); }
    finally { setBusyPrompt(false); }
  }
  async function generate() {
    setError(""); setJob(null);
    try {
      const j = await api(`/projects/${projectId}/cover/generate`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ provider, prompt }) });
      if (j?.id) setJob(j); else setError(j?.detail || t("生成を開始できませんでした"));
    } catch (e) { setError(e instanceof Error ? e.message : t("生成を開始できませんでした")); }
  }
  async function select(filename: string) {
    const r = await api(`/projects/${projectId}/cover`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ filename }) });
    if (Array.isArray(r)) setImages(r);
  }

  return (
    <div className="card">
      <small>{t("表紙生成（書籍出版用）")}</small>
      <p>{t("作品の内容から表紙イラストのプロンプトを作り、ComfyUI または Higgsfield で画像を生成します。採用した画像はEPUBの表紙に埋め込まれます。")}</p>
      <button onClick={makePrompt} disabled={busyPrompt}>{busyPrompt ? t("作成中...") : t("作品内容からプロンプトを作成")}</button>
      <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={4} style={{ width: "100%", marginTop: 8 }}
        placeholder={t("表紙のイメージ（英語プロンプト）。自動作成後に編集できます。")} />
      <div className="exportButtons">
        {PROVIDERS.map((p) => (
          <label key={p.key}><input type="radio" name={`cover-provider-${projectId}`} checked={provider === p.key} onChange={() => setProvider(p.key)} /> {p.label}</label>
        ))}
        <button onClick={generate} disabled={generating || !prompt.trim()}>{generating ? t("生成中...") : t("表紙を生成")}</button>
      </div>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}
      {job && <p style={{ color: job.status === "error" ? "#c0392b" : undefined }}>{job.last_message}</p>}
      {images.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          {images.map((im) => <Thumb key={im.filename} projectId={projectId} image={im} onSelect={() => select(im.filename)} />)}
        </div>
      )}
    </div>
  );
}
