"use client";
import { Project } from "../lib/types";
import { t } from "../lib/i18n";

export type Section =
  | "home" | "write" | "plot" | "characters" | "world" | "timeline"
  | "glossary" | "foreshadow" | "analytics" | "search" | "chat" | "autowrite" | "settings";

const NAV: { key: Section; label: string }[] = [
  { key: "home", label: t("🏠 作品ホーム") },
  { key: "write", label: t("✎ 執筆") },
  { key: "plot", label: t("◆ プロット") },
  { key: "characters", label: t("♟ キャラクター") },
  { key: "world", label: t("◈ 世界観") },
  { key: "timeline", label: t("⏱ 年表") },
  { key: "glossary", label: t("📖 用語集") },
  { key: "foreshadow", label: t("◎ 伏線") },
  { key: "analytics", label: t("📊 分析") },
  { key: "search", label: t("🔍 検索") },
  { key: "chat", label: t("💬 AIチャット") },
  { key: "autowrite", label: t("🚀 自動執筆") },
  { key: "settings", label: t("⚙ 設定") },
];

export default function Sidebar({ project, section, onSection, onDashboard, onLogout }: {
  project: Project; section: Section; onSection: (s: Section) => void; onDashboard: () => void; onLogout: () => void;
}) {
  return (
    <aside className="appSidebar">
      <div className="appSidebarBrand" title="Integrated Novel Editor">✦ INE</div>
      <button className="appSidebarDashboard" onClick={onDashboard}>{t("← ダッシュボードへ")}</button>
      <div className="appSidebarProject"><small>PROJECT</small><b>{project.name}</b></div>
      <div className="appSidebarNav">
        {NAV.map((n) => (
          <button key={n.key} className={section === n.key ? "nav active" : "nav"} onClick={() => onSection(n.key)}>{n.label}</button>
        ))}
      </div>
      <button className="appSidebarLogout" onClick={onLogout}>{t("⏻ ログアウト")}</button>
    </aside>
  );
}
