"use client";
import { ChangeEvent, useEffect, useRef, useState } from "react";
import { api, post, put, del } from "../lib/api";
import { parseCSV, toCSV, downloadTextFile } from "../lib/csv";
import { t } from "../lib/i18n";

type Field = { key: string; label: string; type?: "text" | "textarea" | "number" | "select"; options?: string[] };
type EntityConfig = {
  title: string;
  hint: string;
  listPath: (pid: number) => string;
  itemPath: (id: number) => string;
  titleField: string;
  fields: Field[];
  defaults: Record<string, unknown>;
  // Optional client-side filter over the fetched list (used to split World
  // entities into 世界観 vs 用語集 without a separate backend endpoint).
  filter?: (item: Record<string, unknown>) => boolean;
};

function emptyForm(cfg: EntityConfig) {
  // Start from cfg.defaults so hidden defaults (e.g. GlossaryPanel's
  // entity_type: "glossary", which isn't an editable field) still get sent
  // on create, not just fields the user can see and edit.
  const f: Record<string, unknown> = { ...cfg.defaults };
  for (const field of cfg.fields) if (!(field.key in f)) f[field.key] = "";
  return f;
}

function Cell({ field, value, onChange, onCommit }: {
  field: Field; value: unknown; onChange: (v: unknown) => void; onCommit?: () => void;
}) {
  if (field.type === "textarea") {
    return <textarea rows={2} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} onBlur={onCommit} />;
  }
  if (field.type === "select") {
    return (
      <select value={String(value ?? "")} onChange={(e) => { onChange(e.target.value); onCommit?.(); }}>
        {(field.options || []).map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  return (
    <input
      type={field.type === "number" ? "number" : "text"}
      value={String(value ?? "")}
      onChange={(e) => onChange(field.type === "number" ? Number(e.target.value) : e.target.value)}
      onBlur={onCommit}
    />
  );
}

export function EntityPanel({ projectId, cfg }: { projectId: number; cfg: EntityConfig }) {
  const [items, setItems] = useState<Record<string, unknown>[]>([]);
  const [busy, setBusy] = useState(false);
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set());
  const [newRows, setNewRows] = useState<Record<string, unknown>[]>([]);
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvResult, setCsvResult] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function load() {
    setBusy(true);
    try {
      const list = await api(cfg.listPath(projectId));
      setItems(cfg.filter ? list.filter(cfg.filter) : list);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => { load(); }, [projectId]);

  function updateField(id: number, key: string, value: unknown) {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, [key]: value } : it)));
  }
  async function commitRow(id: number) {
    const item = items.find((it) => it.id === id);
    if (!item) return;
    setSavingIds((prev) => new Set(prev).add(id));
    try {
      await put(cfg.itemPath(id), item);
    } finally {
      setSavingIds((prev) => { const n = new Set(prev); n.delete(id); return n; });
    }
  }
  async function remove(id: number) {
    if (!confirm(t("削除しますか？"))) return;
    await del(cfg.itemPath(id));
    await load();
  }

  function addRow() { setNewRows((prev) => [...prev, emptyForm(cfg)]); }
  function updateNewField(idx: number, key: string, value: unknown) {
    setNewRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [key]: value } : r)));
  }
  function cancelNewRow(idx: number) { setNewRows((prev) => prev.filter((_, i) => i !== idx)); }
  async function commitNewRow(idx: number) {
    const draft = newRows[idx];
    if (!String(draft[cfg.titleField] ?? "").trim()) return; // nothing to save yet
    await post(cfg.listPath(projectId), draft);
    setNewRows((prev) => prev.filter((_, i) => i !== idx));
    await load();
  }

  function downloadTemplate() {
    downloadTextFile(`${cfg.title}_template.csv`, toCSV([cfg.fields.map((f) => f.key)]));
  }

  async function handleCsvFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setCsvBusy(true); setCsvResult(null);
    try {
      const rows = parseCSV(await file.text());
      if (rows.length < 2) { setCsvResult("データ行が見つかりませんでした。ヘッダー行＋1行以上のデータが必要です。"); return; }
      const [header, ...dataRows] = rows;
      const keys = header.map((h) => h.trim());
      let created = 0, failed = 0;
      for (const row of dataRows) {
        if (row.every((c) => c.trim() === "")) continue;
        const obj: Record<string, unknown> = { ...cfg.defaults };
        keys.forEach((key, i) => {
          const field = cfg.fields.find((f) => f.key === key);
          if (!field) return; // unrecognized column header — ignore it
          const raw = (row[i] ?? "").trim();
          obj[key] = field.type === "number" ? Number(raw) : raw;
        });
        if (!String(obj[cfg.titleField] ?? "").trim()) { failed++; continue; }
        try {
          const createdItem = await post(cfg.listPath(projectId), obj);
          if (createdItem && createdItem.id) created++; else failed++;
        } catch {
          failed++;
        }
      }
      setCsvResult(t("{n}件を作成しました。", { n: created }) + (failed ? t("（{n}件は失敗またはスキップされました）", { n: failed }) : ""));
      await load();
    } finally {
      setCsvBusy(false);
    }
  }

  return (
    <div className="panel">
      <small>STORY KNOWLEDGE</small>
      <h1>{cfg.title}</h1>
      <p>{cfg.hint}</p>
      <div className="entityToolbar">
        <button className="add" onClick={addRow}>{t("＋ 行を追加")}</button>
        <button type="button" onClick={downloadTemplate}>{t("CSVテンプレート")}</button>
        <button type="button" onClick={() => fileInputRef.current?.click()} disabled={csvBusy}>
          {csvBusy ? t("取り込み中...") : t("CSVインポート")}
        </button>
        <input ref={fileInputRef} type="file" accept=".csv" hidden onChange={handleCsvFile} />
      </div>
      {csvResult && <p className="searchSource">{csvResult}</p>}
      <div className="entityTableScroll">
        <table className="entityTable">
          <thead>
            <tr>
              {cfg.fields.map((f) => <th key={f.key}>{f.label}</th>)}
              <th></th>
            </tr>
          </thead>
          <tbody>
            {busy && items.length === 0 && newRows.length === 0 && (
              <tr><td colSpan={cfg.fields.length + 1} className="loading">{t("読み込み中...")}</td></tr>
            )}
            {!busy && items.length === 0 && newRows.length === 0 && (
              <tr><td colSpan={cfg.fields.length + 1} className="loading">{t("まだデータがありません。「＋ 行を追加」またはCSVインポートで登録してください。")}</td></tr>
            )}
            {items.map((item) => {
              const id = item.id as number;
              return (
                <tr key={id}>
                  {cfg.fields.map((f) => (
                    <td key={f.key}>
                      <Cell field={f} value={item[f.key]} onChange={(v) => updateField(id, f.key, v)} onCommit={() => commitRow(id)} />
                    </td>
                  ))}
                  <td className="entityRowActions">
                    {savingIds.has(id) ? <span className="savedNote">{t("保存中...")}</span> : <button onClick={() => remove(id)}>{t("削除")}</button>}
                  </td>
                </tr>
              );
            })}
            {newRows.map((draft, idx) => (
              <tr key={`new-${idx}`} className="entityNewRow">
                {cfg.fields.map((f) => (
                  <td key={f.key}>
                    <Cell field={f} value={draft[f.key]} onChange={(v) => updateNewField(idx, f.key, v)} />
                  </td>
                ))}
                <td className="entityRowActions">
                  <button onClick={() => commitNewRow(idx)}>{t("作成")}</button>
                  <button onClick={() => cancelNewRow(idx)}>{t("取消")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function CharacterPanel({ projectId }: { projectId: number }) {
  return <EntityPanel projectId={projectId} cfg={{
    title: t("キャラクター"), hint: t("作品の正本情報。AI Context Builderが生成時に参照します。"),
    listPath: (pid) => `/projects/${pid}/characters`, itemPath: (id) => `/characters/${id}`,
    titleField: "name",
    fields: [
      { key: "name", label: t("名前") }, { key: "role", label: t("役割") },
      { key: "personality", label: t("性格"), type: "textarea" }, { key: "speech_style", label: t("口調"), type: "textarea" },
      { key: "goal", label: t("目標"), type: "textarea" },
      { key: "status", label: t("状態"), type: "select", options: ["alive", "dead", "missing", "unknown"] },
      { key: "description", label: t("補足"), type: "textarea" },
    ],
    defaults: { status: "alive" },
  }} />;
}

export function WorldPanel({ projectId }: { projectId: number }) {
  return <EntityPanel projectId={projectId} cfg={{
    title: t("世界観"), hint: t("場所・組織・技術・魔法などの世界設定。"),
    listPath: (pid) => `/projects/${pid}/world`, itemPath: (id) => `/world/${id}`,
    titleField: "name",
    filter: (x) => x.entity_type !== "glossary",
    fields: [
      { key: "name", label: t("名称") },
      { key: "entity_type", label: t("種類"), type: "select", options: ["setting", "location", "technology", "magic", "organization", "item"] },
      { key: "description", label: t("説明"), type: "textarea" }, { key: "rules", label: t("ルール"), type: "textarea" },
      { key: "location", label: t("場所") }, { key: "era", label: t("時代") },
    ],
    defaults: { entity_type: "setting" },
  }} />;
}

export function GlossaryPanel({ projectId }: { projectId: number }) {
  return <EntityPanel projectId={projectId} cfg={{
    title: t("用語集"), hint: t("作品固有の用語。世界観データベースに entity_type=\"glossary\" として保存されます。"),
    listPath: (pid) => `/projects/${pid}/world`, itemPath: (id) => `/world/${id}`,
    titleField: "name",
    filter: (x) => x.entity_type === "glossary",
    fields: [{ key: "name", label: t("用語") }, { key: "description", label: t("説明"), type: "textarea" }, { key: "location", label: t("カテゴリ") }],
    defaults: { entity_type: "glossary" },
  }} />;
}

export function PlotPanel({ projectId }: { projectId: number }) {
  return <EntityPanel projectId={projectId} cfg={{
    title: t("プロット"), hint: t("作品全体および各アークの構成。"),
    listPath: (pid) => `/projects/${pid}/plots`, itemPath: (id) => `/plots/${id}`,
    titleField: "title",
    fields: [
      { key: "title", label: t("タイトル") },
      { key: "plot_type", label: t("種類"), type: "select", options: ["main_arc", "arc", "subplot"] },
      { key: "status", label: t("状態"), type: "select", options: ["planned", "active", "completed"] },
      { key: "start_episode", label: t("開始話数"), type: "number" }, { key: "end_episode", label: t("終了話数"), type: "number" },
      { key: "objective", label: t("目的"), type: "textarea" }, { key: "conflict", label: t("対立"), type: "textarea" },
      { key: "resolution", label: t("決着"), type: "textarea" },
    ],
    defaults: { plot_type: "arc", status: "planned" },
  }} />;
}

export function ForeshadowPanel({ projectId }: { projectId: number }) {
  return <EntityPanel projectId={projectId} cfg={{
    title: t("伏線"), hint: t("設置・回収の状態を管理します。"),
    listPath: (pid) => `/projects/${pid}/foreshadowings`, itemPath: (id) => `/foreshadowings/${id}`,
    titleField: "title",
    fields: [
      { key: "title", label: t("タイトル") }, { key: "description", label: t("説明"), type: "textarea" },
      { key: "setup_episode", label: t("設置話数"), type: "number" }, { key: "payoff_episode", label: t("回収話数"), type: "number" },
      { key: "status", label: t("状態"), type: "select", options: ["open", "resolved", "abandoned"] },
    ],
    defaults: { status: "open" },
  }} />;
}

export function TimelinePanel({ projectId }: { projectId: number }) {
  return <EntityPanel projectId={projectId} cfg={{
    title: t("年表"), hint: t("エピソード番号に紐づく出来事の年表。"),
    listPath: (pid) => `/projects/${pid}/timeline`, itemPath: (id) => `/timeline/${id}`,
    titleField: "title",
    fields: [
      { key: "episode_number", label: t("話数"), type: "number" }, { key: "title", label: t("出来事") },
      { key: "world_time", label: t("世界内時間") }, { key: "description", label: t("説明"), type: "textarea" },
    ],
    defaults: { episode_number: 1 },
  }} />;
}
