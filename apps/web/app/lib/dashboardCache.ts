import { Project } from "./types";

// The dashboard cards (work list + episode counts) are cached in this browser
// so the screen draws instantly and refreshes quietly behind it. The numbers are
// not critical, so a slightly old value is fine until the refresh lands.
const KEY = "ine-dashboard-cache-v1";

export type Twin = { metrics: { episodes: number; continuity_open: number }; health: { score: number; label: string } };
export type DashboardCache = { projects: Project[]; counts: Record<string, number>; focus?: { id: number; twin: Twin } };

export function loadDashboardCache(): DashboardCache | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const c = JSON.parse(raw) as DashboardCache;
    return Array.isArray(c?.projects) && c.counts && typeof c.counts === "object" ? c : null;
  } catch { return null; }
}

export function saveDashboardCache(c: DashboardCache): void {
  try { localStorage.setItem(KEY, JSON.stringify(c)); } catch { /* storage full/blocked: just no cache */ }
}

export function clearDashboardCache(): void {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}
