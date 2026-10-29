"use client";
import { useEffect, useState } from "react";
import { api, del, downloadFile } from "../lib/api";
import { t } from "../lib/i18n";
import { Project } from "../lib/types";

// Danger zone: delete this work. A work with children (translations / digests
// made from it) can only be deleted once all of them are gone. A JSON backup of
// everything in the work is downloaded automatically right before deleting.
export default function DeleteProjectPanel({ project, onDeleted }: { project: Project; onDeleted: () => void }) {
  const [children, setChildren] = useState<Project[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    let alive = true;
    api("/projects").then((r) => { if (alive && Array.isArray(r)) setChildren(r.filter((p: Project) => p.source_project_id === project.id)); }).catch(() => { if (alive) setErr(t("読み込めませんでした")); });
    return () => { alive = false; };
  }, [project.id]);

  async function remove() {
    setBusy(true); setErr(""); setConfirming(false);
    try {
      // The backup must succeed first: if it cannot be saved, nothing is deleted.
      await downloadFile(`/projects/${project.id}/export?format=json`, `${project.name}.json`);
      const r = await del(`/projects/${project.id}`);
      if (r?.detail) { setErr(r.detail); return; }
      onDeleted();
    } catch (e) { setErr(e instanceof Error ? e.message : t("削除できませんでした")); }
    finally { setBusy(false); }
  }

  const blocked = !children || children.length > 0;
  return (
    <div style={{ marginTop: 14 }}>
      <b style={{ color: "#c0392b" }}>{t("作品の削除")}</b>
      <p style={{ fontSize: 13 }}>{t("この作品のエピソード・設定・表紙画像などをすべて削除します。削除の直前に、全データをJSONファイルとして自動ダウンロードします。")}</p>
      {children && children.length > 0 && (
        <div className="resultCard">
          <b>{t("先に子作品（翻訳・総集編）をすべて削除してください")}</b>
          <ul>{children.map((c) => <li key={c.id}>{c.name}</li>)}</ul>
        </div>
      )}
      {confirming ? (
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 13 }}>{t("本当に削除しますか？この操作は取り消せません。")}</span>
          <button onClick={remove} disabled={busy} style={{ color: "#fff", background: "#c0392b", border: "none", padding: "8px 14px", borderRadius: 6 }}>
            {busy ? t("削除中...") : t("削除を確定する")}
          </button>
          <button onClick={() => setConfirming(false)} disabled={busy} style={{ padding: "8px 14px", borderRadius: 6 }}>{t("キャンセル")}</button>
        </div>
      ) : (
        <button onClick={() => setConfirming(true)} disabled={blocked} style={{ color: "#fff", background: blocked ? "#b0b8c4" : "#c0392b", border: "none", padding: "8px 14px", borderRadius: 6 }}>
          {t("この作品を削除")}
        </button>
      )}
      {err && <p style={{ color: "#c0392b" }}>{err}</p>}
    </div>
  );
}
