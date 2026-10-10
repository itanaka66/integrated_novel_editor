"use client";
import { useState } from "react";
import { post } from "../lib/api";
import { Project } from "../lib/types";
import { t } from "../lib/i18n";

export default function NewProjectForm({ onCreated, onCancel }: { onCreated: (p: Project) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [genre, setGenre] = useState("");
  const [description, setDescription] = useState("");
  const [rules, setRules] = useState("");
  const [episodeGoal, setEpisodeGoal] = useState(500);
  const [author, setAuthor] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    setError("");
    try {
      const p = await post("/projects", { name, genre, description, rules, episode_goal: episodeGoal, author });
      onCreated(p);
    } catch {
      setError(t("作品の作成に失敗しました。APIに接続できているか確認してください。"));
    } finally { setBusy(false); }
  }

  return (
    <div className="modalOverlay" onClick={onCancel}>
      <div className="modalCard" onClick={(e) => e.stopPropagation()}>
        <h1>{t("新規作品作成")}</h1>
        <label>{t("作品名 *")}<input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("例）恐竜文明開拓記")} autoFocus /></label>
        <label>{t("著者名")}<input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder={t("表紙画像に入れる名前")} /></label>
        <label>{t("ジャンル")}<input value={genre} onChange={(e) => setGenre(e.target.value)} placeholder={t("SF・ファンタジー")} /></label>
        <label>{t("あらすじ")}<textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder={t("作品のあらすじを入力してください。")} /></label>
        <label>{t("詳細設定（任意）")}<textarea value={rules} onChange={(e) => setRules(e.target.value)} placeholder={t("文体・想定読者・外せない設定ルールなど")} /></label>
        <label>{t("総話数目標")}<input type="number" value={episodeGoal} min={1} onChange={(e) => setEpisodeGoal(Number(e.target.value))} /></label>
        {error && <p className="errorNote">{error}</p>}
        <div className="modalActions">
          <button onClick={onCancel}>{t("キャンセル")}</button>
          <button onClick={create} disabled={busy || !name.trim()}>{busy ? t("作成中...") : t("作成する")}</button>
        </div>
      </div>
    </div>
  );
}
