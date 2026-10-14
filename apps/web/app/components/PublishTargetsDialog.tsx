"use client";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { PUBLISH_TARGETS, PublishTarget, safeUrl } from "../lib/publishTargets";
import { t } from "../lib/i18n";

const JSON_HEADERS = { "Content-Type": "application/json" };
const TEXT_FIELDS: [keyof PublishTarget, string][] = [
  ["method", t("投稿方式")], ["languages", t("対応言語（8言語）")], ["languageSetting", t("言語指定方法")], ["translation", t("翻訳配信")], ["caution", t("注意事項")],
];
const URL_FIELDS: [keyof PublishTarget, string][] = [["postUrl", t("登録・投稿ページ")], ["officialUrl", t("公式サイト")], ["helpUrl", t("公式ヘルプ")]];
const BLANK: PublishTarget = { name: "", officialUrl: "", postUrl: "", helpUrl: "", method: "", languages: "", languageSetting: "", translation: "", caution: "" };

// The saved list (or the built-in one if never edited) used by the work home.
export function usePublishTargets(): [PublishTarget[], (v: PublishTarget[]) => void] {
  const [targets, setTargets] = useState<PublishTarget[]>(PUBLISH_TARGETS);
  useEffect(() => {
    let live = true;
    api("/publish-targets").then((r) => { if (live && Array.isArray(r?.targets)) setTargets(r.targets); }).catch(() => {});
    return () => { live = false; };
  }, []);
  return [targets, setTargets];
}

// Popup with the details of each posting destination, editable. Links open in a
// new tab; nothing is posted or logged into from here.
export default function PublishTargetsDialog({ targets, onChange, onClose }: { targets: PublishTarget[]; onChange: (v: PublishTarget[]) => void; onClose: () => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<PublishTarget[]>(targets);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  const setField = (i: number, k: keyof PublishTarget, v: string) => setDraft((d) => d.map((x, j) => (j === i ? { ...x, [k]: v } : x)));

  async function save(list: PublishTarget[] | null) {
    setErr(""); setMsg("");
    try {
      const r = await api("/publish-targets", { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ targets: list }) });
      if (r && "targets" in r) {
        const next = r.targets ?? PUBLISH_TARGETS;
        onChange(next); setDraft(next); setEditing(false); setMsg(t("保存しました"));
      } else setErr(r?.detail || t("保存できませんでした"));
    } catch (e) { setErr(e instanceof Error ? e.message : t("保存できませんでした")); }
  }

  const shown = editing ? draft : targets;
  return (
    <div className="modalOverlay" onClick={onClose}>
      <div className="modalCard" style={{ width: "min(900px, 96vw)", maxHeight: "90vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: 0 }}>{t("投稿先の詳細")}</h3>
        <p style={{ fontSize: 12, color: "#566273", margin: "4px 0 10px" }}>{t("各サービスの対応言語や注意事項のメモです。内容は変わることがあるため、最新情報は各公式ページで確認してください。")}</p>
        {shown.map((x, i) => (
          <div key={i} className="resultCard" style={{ marginBottom: 10 }}>
            {editing ? (
              <div className="entityForm">
                <label style={{ gridColumn: "1/-1" }}>{t("投稿先名")}<input value={x.name} onChange={(e) => setField(i, "name", e.target.value)} /></label>
                {URL_FIELDS.map(([k, label]) => <label key={k}>{label} URL<input value={x[k]} placeholder="https://" onChange={(e) => setField(i, k, e.target.value)} /></label>)}
                {TEXT_FIELDS.map(([k, label]) => <label key={k} style={{ gridColumn: "1/-1" }}>{label}<textarea rows={2} value={x[k]} onChange={(e) => setField(i, k, e.target.value)} /></label>)}
                <div style={{ gridColumn: "1/-1" }}><button type="button" onClick={() => setDraft((d) => d.filter((_, j) => j !== i))} style={{ color: "#c0392b" }}>{t("この投稿先を削除")}</button></div>
              </div>
            ) : (
              <>
                <b>{x.name}</b>
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap", margin: "4px 0 8px" }}>
                  {URL_FIELDS.map(([k, label]) => safeUrl(x[k]) && <a key={k} href={safeUrl(x[k])} target="_blank" rel="noopener noreferrer">{label}</a>)}
                </div>
                <table className="entityTable" style={{ width: "100%" }}>
                  <tbody>
                    {TEXT_FIELDS.map(([k, label]) => <tr key={k}><th style={{ width: 150, textAlign: "left" }}>{label}</th><td>{x[k]}</td></tr>)}
                  </tbody>
                </table>
              </>
            )}
          </div>
        ))}
        {editing && <button type="button" onClick={() => setDraft((d) => [...d, { ...BLANK }])}>{t("＋ 投稿先を追加")}</button>}
        {msg && <p style={{ color: "#2e7d32", margin: "6px 0" }}>{msg}</p>}
        {err && <p style={{ color: "#c0392b", margin: "6px 0" }}>{err}</p>}
        <div className="modalActions">
          {!editing && <button onClick={() => { setDraft(targets); setEditing(true); setMsg(""); }}>{t("編集")}</button>}
          {editing && <button onClick={() => { if (window.confirm(t("初期の一覧に戻しますか？"))) save(null); }}>{t("初期値に戻す")}</button>}
          {editing && <button onClick={() => { setEditing(false); setErr(""); }}>{t("取消")}</button>}
          <button onClick={onClose}>{t("閉じる")}</button>
          {editing && <button className="saveButton" onClick={() => save(draft)}>{t("保存")}</button>}
        </div>
      </div>
    </div>
  );
}
