"use client";
import { useEffect, useState } from "react";
import { checkSession, clearAuth, getAuth, logout, setUnauthorizedHandler } from "./lib/api";
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

export default function Studio() {
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    setUnauthorizedHandler(() => { clearAuth(); setAuthed(false); });
    // A stored Basic Auth pair means "probably logged in" without waiting
    // on a network round-trip — but an OAuth2 login (Google/GitHub) leaves
    // no trace in localStorage at all, only an httpOnly session cookie
    // that JavaScript can't read, so its presence has to be asked of the
    // server instead.
    if (getAuth()) {
      setAuthed(true);
    } else {
      checkSession().then(setAuthed);
    }
    return () => setUnauthorizedHandler(null);
  }, []);

  if (authed === null) return <div className="center">確認中...</div>;
  if (!authed) return <Login onLoggedIn={() => setAuthed(true)} />;
  return (
    <>
      <Workspace onLogout={() => { logout().then(() => setAuthed(false)); }} />
      <LlmActivityDialog />
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
        {section === "settings" && <SettingsPanel project={project} onSaved={setProject} />}
      </main>
    </div>
  );
}
