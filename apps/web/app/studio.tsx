"use client";
import { useEffect, useState } from "react";
import { clearAuth, logout, setUnauthorizedHandler } from "./lib/api";
import { useResizableWidth } from "./lib/useResizable";
import { Project } from "./lib/types";
import Login from "./components/Login";
import Sidebar, { Section } from "./components/Sidebar";
import Dashboard from "./components/Dashboard";
import ProjectHome from "./components/ProjectHome";
import WritePanel from "./components/WritePanel";
import { CharacterPanel, WorldPanel, GlossaryPanel, PlotPanel, ForeshadowPanel, TimelinePanel } from "./components/EntityPanels";
import AnalyticsPanel from "./components/AnalyticsPanel";
import SearchPanel from "./components/SearchPanel";
import ChatPanel from "./components/ChatPanel";
import AutoWritePanel from "./components/AutoWritePanel";
import SettingsPanel from "./components/SettingsPanel";
import LlmActivityDialog from "./components/LlmActivityDialog";
import PageLoadingOverlay from "./components/PageLoadingOverlay";
import { useIdleLogout } from "./lib/useIdleLogout";
import { useOfflineLogout } from "./lib/useOfflineLogout";
import { getLanguage, t } from "./lib/i18n";

export default function Studio() {
  const [authed, setAuthed] = useState<boolean>(false);
  const [idleNotice, setIdleNotice] = useState(false);
  const [offlineNotice, setOfflineNotice] = useState(false);

  // layout.tsx server-renders <html lang="ja">; hydration restores that over
  // whatever lib/i18n set at module load, so set it again once mounted.
  useEffect(() => { document.documentElement.lang = getLanguage(); }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => { clearAuth(); setAuthed(false); });
    // Always start signed out. Clear stored credentials and request OAuth session invalidation.
    void logout();
    return () => setUnauthorizedHandler(null);
  }, []);

  // 10 minutes without any input signs the user out (see lib/useIdleLogout).
  useIdleLogout(authed === true, () => {
    setIdleNotice(true);
    logout().then(() => setAuthed(false));
  });

  // Network loss signs the user out immediately (see lib/useOfflineLogout).
  useOfflineLogout(authed === true, () => {
    setOfflineNotice(true);
    logout().then(() => setAuthed(false));
  });

  if (authed === null) return <div className="center" suppressHydrationWarning>{t("確認中...")}</div>;
  if (!authed) return <Login notice={offlineNotice ? t("ネットワーク接続が切断されたため、自動的にサインアウトしました。") : idleNotice ? t("10分間操作がなかったため、自動的にサインアウトしました。") : undefined} onLoggedIn={() => { setIdleNotice(false); setOfflineNotice(false); setAuthed(true); }} />;
  return (
    <>
      <Workspace onLogout={() => { logout().then(() => setAuthed(false)); }} />
      <LlmActivityDialog />
      <PageLoadingOverlay />
    </>
  );
}

function Workspace({ onLogout }: { onLogout: () => void }) {
  const [project, setProject] = useState<Project | null>(null);
  const [section, setSection] = useState<Section>("home");
  const sidebar = useResizableWidth("ine-sidebar-width", 190, 150, 400, "right");

  if (!project) return <Dashboard onOpen={(p) => { setProject(p); setSection("home"); }} onLogout={onLogout} />;

  return (
    <div className="appShell" style={{ "--sidebar-w": `${sidebar.width}px` } as React.CSSProperties}>
      <Sidebar project={project} section={section} onSection={setSection} onDashboard={() => setProject(null)} onLogout={onLogout} />
      <div className="resizeHandle" onMouseDown={sidebar.startDrag} />
      <main className="appMain">
        {section === "home" && <ProjectHome project={project} onSection={setSection} onOpenProject={(p) => { setProject(p); setSection("home"); }} />}
        {section === "write" && <WritePanel project={project} />}
        {section === "plot" && <PlotPanel projectId={project.id} />}
        {section === "characters" && <CharacterPanel projectId={project.id} />}
        {section === "world" && <WorldPanel projectId={project.id} />}
        {section === "timeline" && <TimelinePanel projectId={project.id} />}
        {section === "glossary" && <GlossaryPanel projectId={project.id} />}
        {section === "foreshadow" && <ForeshadowPanel projectId={project.id} />}
        {section === "analytics" && <AnalyticsPanel projectId={project.id} />}
        {section === "search" && <SearchPanel projectId={project.id} />}
        {section === "chat" && <ChatPanel projectId={project.id} />}
        {section === "autowrite" && <AutoWritePanel projectId={project.id} />}
        {section === "settings" && <SettingsPanel project={project} onSaved={setProject} onDeleted={() => setProject(null)} />}
      </main>
    </div>
  );
}
