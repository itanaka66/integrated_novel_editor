"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, fetchBlobUrl } from "../lib/api";
import { t } from "../lib/i18n";

type CoverImage = { filename: string; provider: string; selected: boolean; style: string; prompt: string };
type CoverJob = { id: number; status: string; filename: string | null; last_message: string };
type StyleOption = { key: string; label: string };
type CoverState = { prompt: string; style: string; custom_style: string; provider: string; overlay: boolean };

const PROVIDERS = [
  { key: "comfyui", label: t("ComfyUI（ローカル）") },
  { key: "higgsfield", label: t("Higgsfield（クラウド）") },
];
const JSON_HEADERS = { "Content-Type": "application/json" };

function useImageUrl(projectId: number, filename: string) {
  const [src, setSrc] = useState("");
  useEffect(() => {
    let url = "";
    let alive = true;
    fetchBlobUrl(`/projects/${projectId}/covers/${filename}`).then((u) => { url = u; if (alive) setSrc(u); }).catch(() => {});
    return () => { alive = false; if (url) URL.revokeObjectURL(url); };
  }, [projectId, filename]);
  return src;
}

function Thumb({ projectId, image, onOpen }: { projectId: number; image: CoverImage; onOpen: () => void }) {
  const src = useImageUrl(projectId, image.filename);
  return (
    <button onClick={onOpen} title={t("クリックで拡大")}
      style={{ padding: 0, border: image.selected ? "3px solid #2e7d32" : "1px solid #ccc", background: "none", width: 120 }}>
      {src ? <img src={src} alt={image.filename} style={{ width: "100%", display: "block" }} /> : <span>…</span>}
      <small>{image.selected ? t("✓ 採用中") : image.style || image.provider}</small>
    </button>
  );
}

function Viewer({ projectId, image, onClose, onSelect }: { projectId: number; image: CoverImage; onClose: () => void; onSelect: () => void }) {
  const src = useImageUrl(projectId, image.filename);
  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard" style={{ width: "min(640px, 94vw)" }} onClick={(e) => e.stopPropagation()}>
        {src ? <img src={src} alt={image.filename} style={{ width: "100%", maxHeight: "70vh", objectFit: "contain" }} /> : <p>…</p>}
        <small>{image.filename}{image.style ? ` · ${image.style}` : ""}</small>
        {image.prompt && <p style={{ fontSize: 12, color: "#566273", margin: 0 }}>{image.prompt}</p>}
        <div className="modalActions">
          <button onClick={onClose}>{t("閉じる")}</button>
          <button onClick={onSelect} disabled={image.selected}>{image.selected ? t("✓ 採用中") : t("この画像を表紙にする")}</button>
        </div>
      </div>
    </div>
  );
}

export default function CoverPanel({ projectId }: { projectId: number }) {
  const [styles, setStyles] = useState<StyleOption[]>([]);
  const [state, setState] = useState<CoverState>({ prompt: "", style: "", custom_style: "", provider: "comfyui", overlay: true });
  const [loaded, setLoaded] = useState(false);
  const [saved, setSaved] = useState(false);
  const [images, setImages] = useState<CoverImage[]>([]);
  const [viewing, setViewing] = useState<string | null>(null);
  const [job, setJob] = useState<CoverJob | null>(null);
  const [busyPrompt, setBusyPrompt] = useState(false);
  const [error, setError] = useState("");
  const generating = !!job && (job.status === "queued" || job.status === "running");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const reload = useCallback(() => api(`/projects/${projectId}/covers`).then((r) => { if (Array.isArray(r)) setImages(r); }), [projectId]);
  useEffect(() => { reload(); }, [reload]);

  // The prompt, style and engine live on the server (a file per project), so
  // coming back to this screen — or reloading — shows what was there.
  useEffect(() => {
    let alive = true;
    api("/cover/styles").then((r) => { if (alive && r?.styles) setStyles(r.styles); }).catch(() => {});
    api(`/projects/${projectId}/cover/state`).then((r) => { if (alive && r && typeof r.prompt === "string") { setState(r); setLoaded(true); } }).catch(() => setLoaded(true));
    return () => { alive = false; };
  }, [projectId]);

  function persist(next: CoverState, delay = 0) {
    setState(next);
    setSaved(false);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      api(`/projects/${projectId}/cover/state`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(next) })
        .then((r) => { if (r && typeof r.prompt === "string") setSaved(true); }).catch(() => {});
    }, delay);
  }
  // Flush a pending edit if the user leaves the screen before the debounce fires.
  useEffect(() => () => { if (saveTimer.current) clearTimeout(saveTimer.current); }, []);

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
      const r = await api(`/projects/${projectId}/cover/prompt`, { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ style: state.style, custom_style: state.custom_style }) });
      if (r?.prompt) { setState((s) => ({ ...s, prompt: r.prompt })); setSaved(true); } else setError(r?.detail || t("プロンプトを生成できませんでした"));
    } catch (e) { setError(e instanceof Error ? e.message : t("プロンプトを生成できませんでした")); }
    finally { setBusyPrompt(false); }
  }
  async function generate() {
    setError(""); setJob(null);
    try {
      const j = await api(`/projects/${projectId}/cover/generate`, {
        method: "POST", headers: JSON_HEADERS,
        body: JSON.stringify({ provider: state.provider, prompt: state.prompt, style: state.style, custom_style: state.custom_style, overlay: state.overlay }),
      });
      if (j?.id) setJob(j); else setError(j?.detail || t("生成を開始できませんでした"));
    } catch (e) { setError(e instanceof Error ? e.message : t("生成を開始できませんでした")); }
  }
  async function select(filename: string) {
    const r = await api(`/projects/${projectId}/cover`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ filename }) });
    if (Array.isArray(r)) setImages(r);
  }
  const open = images.find((im) => im.filename === viewing) ?? null;

  return (
    <div className="card">
      <small>{t("表紙生成（書籍出版用）")}</small>
      <p>{t("作品の内容から表紙イラストのプロンプトを作り、ComfyUI または Higgsfield で画像を生成します。採用した画像はEPUBの表紙に埋め込まれます。")}</p>

      <b style={{ fontSize: 13 }}>{t("どんなイメージにしますか？")}</b>
      <div className="exportButtons" role="radiogroup" aria-label={t("表紙のイメージ")}>
        {styles.map((s) => (
          <label key={s.key}>
            <input type="radio" name={`cover-style-${projectId}`} checked={state.style === s.key} onChange={() => persist({ ...state, style: s.key })} /> {s.label}
          </label>
        ))}
      </div>
      {state.style === "other" && (
        <input value={state.custom_style} onChange={(e) => persist({ ...state, custom_style: e.target.value }, 700)} style={{ width: "100%", marginTop: 6 }}
          placeholder={t("イメージを自由に記入（例：水彩画、浮世絵、ドット絵）")} />
      )}

      <button onClick={makePrompt} disabled={busyPrompt || !loaded} style={{ marginTop: 8 }}>{busyPrompt ? t("作成中...") : t("作品内容からプロンプトを作成")}</button>
      <textarea value={state.prompt} onChange={(e) => persist({ ...state, prompt: e.target.value }, 700)} rows={4} style={{ width: "100%", marginTop: 8 }}
        placeholder={t("表紙のイメージ（英語プロンプト）。自動作成後に編集できます。")} />
      <small className="searchSource">{saved ? t("自動保存しました") : t("編集は自動保存されます")}</small>

      <label style={{ display: "block", marginTop: 8 }}><input type="checkbox" checked={state.overlay} onChange={(e) => persist({ ...state, overlay: e.target.checked })} /> {t("タイトルと著者名を画像に入れる")}</label>
      <div className="exportButtons">
        {PROVIDERS.map((p) => (
          <label key={p.key}><input type="radio" name={`cover-provider-${projectId}`} checked={state.provider === p.key} onChange={() => persist({ ...state, provider: p.key })} /> {p.label}</label>
        ))}
        <button onClick={generate} disabled={generating || !state.prompt.trim()}>{generating ? t("生成中...") : t("表紙を生成")}</button>
      </div>
      {error && <p style={{ color: "#c0392b" }}>{error}</p>}
      {job && <p style={{ color: job.status === "error" ? "#c0392b" : undefined }}>{job.last_message}</p>}
      {images.length > 0 && (
        <>
          <small className="searchSource">{t("生成した画像はサーバーのディスクに自動保存されます。クリックで拡大します。")}</small>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
            {images.map((im) => <Thumb key={im.filename} projectId={projectId} image={im} onOpen={() => setViewing(im.filename)} />)}
          </div>
        </>
      )}
      {open && <Viewer projectId={projectId} image={open} onClose={() => setViewing(null)} onSelect={() => select(open.filename)} />}
    </div>
  );
}
