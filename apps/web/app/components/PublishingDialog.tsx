"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { t } from "../lib/i18n";

type Pub = { title: string; subtitle: string; author: string; description: string; keywords: string[]; category: string; adult: boolean; age_min: string; age_max: string };

const MAX_KEYWORDS = 7;
const MAX_DESCRIPTION = 4000;
const JSON_HEADERS = { "Content-Type": "application/json" };

// Everything the store page (e.g. Amazon KDP) asks for, in one place.
export default function PublishingDialog({ projectId, onClose, onSaved }: { projectId: number; onClose: () => void; onSaved?: (title: string, author: string) => void }) {
  const [pub, setPub] = useState<Pub | null>(null);
  const [keywords, setKeywords] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    api(`/projects/${projectId}/publishing`).then((r) => {
      if (r?.title !== undefined) { setPub(r); setKeywords((r.keywords || []).join("\n")); } else setErr(r?.detail || t("読み込めませんでした"));
    }).catch(() => setErr(t("読み込めませんでした")));
  }, [projectId]);

  const kws = keywords.split("\n").map((k) => k.trim()).filter(Boolean);
  const set = (patch: Partial<Pub>) => setPub((p) => (p ? { ...p, ...patch } : p));

  async function save() {
    if (!pub) return;
    setMsg(""); setErr("");
    try {
      const r = await api(`/projects/${projectId}/publishing`, { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ ...pub, keywords: kws }) });
      if (r?.title !== undefined) { setPub(r); setKeywords((r.keywords || []).join("\n")); setMsg(t("保存しました")); onSaved?.(r.title, r.author); } else setErr(r?.detail || t("保存できませんでした"));
    } catch (e) { setErr(e instanceof Error ? e.message : t("保存できませんでした")); }
  }

  async function copyAll() {
    if (!pub) return;
    const text = [
      `${t("タイトル")}: ${pub.title}`, `${t("サブタイトル")}: ${pub.subtitle}`, `${t("著者名")}: ${pub.author}`,
      `${t("内容紹介文")}:\n${pub.description}`, `${t("キーワード")}: ${kws.join(" / ")}`, `${t("カテゴリー")}: ${pub.category}`,
      `${t("成人向けコンテンツ")}: ${pub.adult ? t("あり") : t("なし")}`, `${t("読者対象年齢")}: ${pub.age_min || "-"} 〜 ${pub.age_max || "-"}`,
    ].join("\n");
    try { await navigator.clipboard.writeText(text); setMsg(t("コピーしました")); } catch { setErr(t("コピーできませんでした")); }
  }

  const over = !!pub && pub.description.length > MAX_DESCRIPTION;
  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard" style={{ width: "min(680px, 94vw)", maxHeight: "90vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{t("出版情報")}</h3>
        <p style={{ fontSize: 12, color: "#566273", margin: "4px 0" }}>{t("電子書籍ストア（Amazon KDPなど）の登録に必要な情報をまとめます。")}</p>
        {!pub && <p>{err || t("読み込み中...")}</p>}
        {pub && (
          <div className="entityForm">
            <label>{t("タイトル")} *<input value={pub.title} onChange={(e) => set({ title: e.target.value })} /></label>
            <label>{t("サブタイトル")}<input value={pub.subtitle} onChange={(e) => set({ subtitle: e.target.value })} /></label>
            <label>{t("著者名")}（{t("ペンネーム可")}）<input value={pub.author} onChange={(e) => set({ author: e.target.value })} /></label>
            <label>{t("カテゴリー")}<input value={pub.category} onChange={(e) => set({ category: e.target.value })} placeholder={t("例）フィクション > SF")} /></label>
            <label style={{ gridColumn: "1/-1" }}>{t("内容紹介文")}（{t("販売ページに表示されます")}）
              <textarea rows={6} value={pub.description} onChange={(e) => set({ description: e.target.value })} />
              <small style={{ color: over ? "#c0392b" : "#566273" }}>{pub.description.length} / {MAX_DESCRIPTION}</small>
            </label>
            <label style={{ gridColumn: "1/-1" }}>{t("キーワード")}（{t("1行に1つ、最大{n}つ", { n: MAX_KEYWORDS })}）
              <textarea rows={4} value={keywords} onChange={(e) => setKeywords(e.target.value)} />
              <small style={{ color: kws.length > MAX_KEYWORDS ? "#c0392b" : "#566273" }}>{kws.length} / {MAX_KEYWORDS}</small>
            </label>
            <label><input type="checkbox" checked={pub.adult} onChange={(e) => set({ adult: e.target.checked })} /> {t("成人向けコンテンツを含む")}</label>
            <span />
            <label>{t("読者対象年齢（下限）")}<input type="number" min={0} value={pub.age_min} onChange={(e) => set({ age_min: e.target.value })} /></label>
            <label>{t("読者対象年齢（上限）")}<input type="number" min={0} value={pub.age_max} onChange={(e) => set({ age_max: e.target.value })} /></label>
          </div>
        )}
        {msg && <p style={{ color: "#2e7d32", margin: "6px 0" }}>{msg}</p>}
        {err && pub && <p style={{ color: "#c0392b", margin: "6px 0" }}>{err}</p>}
        <div className="modalActions">
          <button onClick={copyAll} disabled={!pub}>{t("まとめてコピー")}</button>
          <button onClick={onClose}>{t("閉じる")}</button>
          <button className="primary" onClick={save} disabled={!pub || over || kws.length > MAX_KEYWORDS}>{t("保存")}</button>
        </div>
      </div>
    </div>
  );
}
