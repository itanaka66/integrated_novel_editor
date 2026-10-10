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

  useEffect(() => {
    api("/cover/config").then((r) => { if (r?.styles) setCfg(r); else setErr(r?.detail || t("読み込めませんでした")); }).catch(() => setErr(t("読み込めませんでした")));
  }, []);

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

  const s = cfg.styles[open];
  return (
    <div style={{ marginTop: 14 }}>
      <p style={{ fontSize: 12, color: "#566273" }}>{t("イメージごとに使う ComfyUI / Higgsfield の設定です。空欄は共通設定を使います。")}</p>

      <b>{t("共通設定")}</b>
      <div className="entityForm" style={{ marginTop: 6 }}>
        {COMFY.map(([k, label, num]) => (
          <label key={k}>ComfyUI {label}<input type={num ? "number" : "text"} value={cfg.comfyui[k] ?? ""} onChange={(e) => setBase("comfyui", k, e.target.value)} /></label>
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
            <label key={k}>ComfyUI {label}<input type={num ? "number" : "text"} value={s.comfyui[k] ?? ""} placeholder={String(cfg.comfyui[k] ?? "")} onChange={(e) => setOver(open, "comfyui", k, e.target.value)} /></label>
          ))}
          <label style={{ gridColumn: "1/-1" }}>ComfyUI {t("ネガティブに追加")}<input value={s.comfyui.negative_extra ?? ""} onChange={(e) => setOver(open, "comfyui", "negative_extra", e.target.value)} /></label>
          {HIGGS.map(([k, label]) => (
            <label key={k}>Higgsfield {label}<input value={s.higgsfield[k] ?? ""} placeholder={String(cfg.higgsfield[k] ?? "")} onChange={(e) => setOver(open, "higgsfield", k, e.target.value)} /></label>
          ))}
        </div>
      )}

      <div style={{ marginTop: 10 }}>
        <button className="primary" onClick={save}>{t("保存")}</button>
        {msg && <span style={{ marginLeft: 10, color: "#2e7d32" }}>{msg}</span>}
        {err && <span style={{ marginLeft: 10, color: "#c0392b" }}>{err}</span>}
      </div>
    </div>
  );
}
