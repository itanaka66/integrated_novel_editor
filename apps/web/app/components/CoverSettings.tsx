"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { t } from "../lib/i18n";

type Fields = Record<string, string | number>;
type StyleCfg = { label: string; prompt_style: string; prompt_suffix: string; comfyui: Fields; higgsfield: Fields };
type Cfg = { comfyui: Fields; higgsfield: Fields; styles: Record<string, StyleCfg> };

const COMFY: [string, string, boolean][] = [
  ["checkpoint", t("チェックポイント"), false], ["width", t("幅"), true], ["height", t("高さ"), true], ["steps", t("ステップ数"), true],
  ["cfg", t("CFG"), true], ["sampler_name", t("サンプラー"), false], ["scheduler", t("スケジューラ"), false],
];
const HIGGS: [string, string][] = [["model", t("モデル")], ["resolution", t("解像度")], ["aspect_ratio", t("縦横比")]];
const JSON_HEADERS = { "Content-Type": "application/json" };

export default function CoverSettings() {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [open, setOpen] = useState("anime");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [test, setTest] = useState<{ ok: boolean; message: string; checkpoints: string[] } | null>(null);
  const [testing, setTesting] = useState(false);
  const [installed, setInstalled] = useState<string[]>([]);

  useEffect(() => {
    api("/cover/config").then((r) => { if (r?.styles) setCfg(r); else setErr(r?.detail || t("読み込めませんでした")); }).catch(() => setErr(t("読み込めませんでした")));
  }, []);

  // Offer the checkpoints ComfyUI actually has as suggestions (still free text).
  useEffect(() => {
    if (!cfg) return;
    api("/cover/test-comfyui", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ url: String(cfg.comfyui.url ?? "") }) })
      .then((r) => { if (Array.isArray(r?.checkpoints)) setInstalled(r.checkpoints); }).catch(() => {});
  }, [cfg !== null]);

  if (!cfg) return <p style={{ marginTop: 14 }}>{err || t("読み込み中...")}</p>;

  const setBase = (sec: "comfyui" | "higgsfield", k: string, v: string) => setCfg({ ...cfg, [sec]: { ...cfg[sec], [k]: v } });
  const setStyle = (key: string, patch: Partial<StyleCfg>) => setCfg({ ...cfg, styles: { ...cfg.styles, [key]: { ...cfg.styles[key], ...patch } } });
  const setOver = (key: string, sec: "comfyui" | "higgsfield", k: string, v: string) => setStyle(key, { [sec]: { ...cfg.styles[key][sec], [k]: v } } as Partial<StyleCfg>);

  async function save() {
    setMsg(""); setErr("");
    try {
      const r = await api("/cover/config", { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify(cfg) });
      if (r?.styles) { setCfg(r); setMsg(t("保存しました。次の生成から反映されます。")); } else setErr(r?.detail || t("保存できませんでした"));
    } catch (e) { setErr(e instanceof Error ? e.message : t("保存できませんでした")); }
  }

  async function testConnection() {
    setTesting(true); setTest(null);
    try {
      const r = await api("/cover/test-comfyui", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ url: String(cfg!.comfyui.url ?? ""), checkpoint: String(cfg!.comfyui.checkpoint ?? "") }) });
      if (Array.isArray(r?.checkpoints)) setInstalled(r.checkpoints);
      setTest(r?.message ? r : { ok: false, message: r?.detail || t("接続テストに失敗しました"), checkpoints: [] });
    } catch (e) { setTest({ ok: false, message: e instanceof Error ? e.message : t("接続テストに失敗しました"), checkpoints: [] }); }
    finally { setTesting(false); }
  }

  const s = cfg.styles[open];
  return (
    <div style={{ marginTop: 14 }}>
      <p style={{ fontSize: 12, color: "#566273" }}>{t("イメージごとに使う ComfyUI / Higgsfield の設定です。空欄は共通設定を使います。")}</p>

      <b>{t("共通設定")}</b>
      <div className="entityForm" style={{ marginTop: 6 }}>
        <label style={{ gridColumn: "1/-1" }}>{t("ComfyUI 接続先URL")}
          <input value={cfg.comfyui.url ?? ""} onChange={(e) => setBase("comfyui", "url", e.target.value)} placeholder={t("空欄の場合は環境変数 COMFYUI_URL（既定 http://localhost:8188）")} />
        </label>
        <div style={{ gridColumn: "1/-1" }}>
          <button type="button" onClick={testConnection} disabled={testing}>{testing ? t("確認中...") : t("接続テスト")}</button>
          {test && <span style={{ marginLeft: 10, color: test.ok ? "#2e7d32" : "#c0392b" }}>{test.message}</span>}
          {test && test.checkpoints.length > 0 && <div style={{ fontSize: 12, color: "#566273", marginTop: 4 }}>{t("利用可能なチェックポイント")}: {test.checkpoints.join(", ")}</div>}
        </div>
        {COMFY.map(([k, label, num]) => (
          <label key={k}>ComfyUI {label}<input type={num ? "number" : "text"} list={k === "checkpoint" ? "cover-ckpts" : undefined} value={cfg.comfyui[k] ?? ""} onChange={(e) => setBase("comfyui", k, e.target.value)} /></label>
        ))}
        <label style={{ gridColumn: "1/-1" }}>ComfyUI {t("ネガティブプロンプト")}<textarea value={String(cfg.comfyui.negative ?? "")} onChange={(e) => setBase("comfyui", "negative", e.target.value)} /></label>
        {HIGGS.map(([k, label]) => (
          <label key={k}>Higgsfield {label}<input value={cfg.higgsfield[k] ?? ""} onChange={(e) => setBase("higgsfield", k, e.target.value)} /></label>
        ))}
      </div>

      <div className="twinTabs" style={{ marginTop: 14 }}>
        {Object.entries(cfg.styles).map(([key, st]) => (
          <button key={key} className={open === key ? "on" : ""} onClick={() => setOpen(key)}>{st.label}</button>
        ))}
      </div>
      {s && (
        <div className="entityForm" style={{ marginTop: 6 }}>
          <label style={{ gridColumn: "1/-1" }}>{t("プロンプトの方向づけ")}<textarea value={s.prompt_style} onChange={(e) => setStyle(open, { prompt_style: e.target.value })} /></label>
          <label style={{ gridColumn: "1/-1" }}>{t("プロンプト末尾に付ける語句")}<input value={s.prompt_suffix} onChange={(e) => setStyle(open, { prompt_suffix: e.target.value })} /></label>
          {COMFY.map(([k, label, num]) => (
            <label key={k}>ComfyUI {label}<input type={num ? "number" : "text"} list={k === "checkpoint" ? "cover-ckpts" : undefined} value={s.comfyui[k] ?? ""} placeholder={k === "checkpoint" ? String(cfg.comfyui[k] || t("共通設定を使用")) : String(cfg.comfyui[k] ?? "")} onChange={(e) => setOver(open, "comfyui", k, e.target.value)} /></label>
          ))}
          <label style={{ gridColumn: "1/-1" }}>ComfyUI {t("ネガティブに追加")}<input value={s.comfyui.negative_extra ?? ""} onChange={(e) => setOver(open, "comfyui", "negative_extra", e.target.value)} /></label>
          {HIGGS.map(([k, label]) => (
            <label key={k}>Higgsfield {label}<input value={s.higgsfield[k] ?? ""} placeholder={String(cfg.higgsfield[k] ?? "")} onChange={(e) => setOver(open, "higgsfield", k, e.target.value)} /></label>
          ))}
        </div>
      )}

      <datalist id="cover-ckpts">{installed.map((c) => <option key={c} value={c} />)}</datalist>
      <div style={{ marginTop: 10 }}>
        <button className="primary" onClick={save}>{t("保存")}</button>
        {msg && <span style={{ marginLeft: 10, color: "#2e7d32" }}>{msg}</span>}
        {err && <span style={{ marginLeft: 10, color: "#c0392b" }}>{err}</span>}
      </div>
    </div>
  );
}
