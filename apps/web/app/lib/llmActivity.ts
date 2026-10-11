import { t } from "./i18n";
// Tracks which backend calls are currently waiting on an LLM, so
// LlmActivityDialog can say *what* the AI is doing instead of the UI just
// sitting there for tens of seconds. Kept as a tiny external store (read via
// useSyncExternalStore) rather than React state, because the calls are made
// from api()/streamSSE() in lib/api.ts, outside any component.

export type LlmActivity = { id: number; label: string; startedAt: number };

type Route = { method: string; re: RegExp; label: (body: unknown) => string };

const AI_MODE_LABELS: Record<string, string> = {
  continue: t("続きを書いています"),
  plot: t("次の展開を考えています"),
  summary: t("要約しています"),
  proofread: t("校正しています"),
  custom: t("AIが指示を処理しています"),
};

// Only endpoints that actually wait on Ollama. Auto-write and cover jobs run
// in the background and have their own progress UI, so they're not listed.
const ROUTES: Route[] = [
  { method: "POST", re: /^\/ai\/generate$/, label: (b) => AI_MODE_LABELS[(b as { mode?: string } | undefined)?.mode ?? ""] ?? t("AIが本文を生成しています") },
  { method: "POST", re: /^\/continuity\/check$/, label: () => t("矛盾・連続性を監査しています") },
  { method: "POST", re: /^\/episodes\/\d+\/character-states$/, label: () => t("登場人物の状態を更新しています") },
  { method: "POST", re: /^\/episodes\/\d+\/proofread(\/stream)?$/, label: () => t("文章を校正しています") },
  { method: "POST", re: /^\/projects\/\d+\/style-guide\/generate$/, label: () => t("スタイルガイドを生成しています") },
  { method: "POST", re: /^\/projects\/\d+\/chat$/, label: () => t("AIが回答を考えています") },
  { method: "POST", re: /^\/projects\/\d+\/cover\/prompt$/, label: () => t("表紙のプロンプトを作成しています") },
  { method: "POST", re: /^\/projects\/\d+\/ai-entities$/, label: () => t("AIが設定案を考えています") },
  { method: "POST", re: /^\/rag\/search(-all)?$/, label: () => t("意味検索の準備（埋め込み生成）をしています") },
];

let activities: LlmActivity[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit() {
  for (const fn of listeners) fn();
}

export function subscribeActivities(fn: () => void): () => void {
  listeners.add(fn);
  return () => { listeners.delete(fn); };
}

// A new array on every change (never mutated in place) — that identity change
// is what useSyncExternalStore uses to know a re-render is needed.
export function getActivities(): LlmActivity[] {
  return activities;
}

// Returns an id to pass to endActivity(), or null when this call isn't an
// LLM one (so callers can use `if (id !== null)` and skip all bookkeeping).
export function beginActivity(method: string, path: string, body?: unknown): number | null {
  const bare = path.split("?")[0];
  const m = method.toUpperCase();
  const route = ROUTES.find((r) => r.method === m && r.re.test(bare));
  if (!route) return null;
  const id = nextId++;
  activities = [...activities, { id, label: route.label(body), startedAt: Date.now() }];
  emit();
  return id;
}

export function endActivity(id: number | null): void {
  if (id === null) return;
  const next = activities.filter((a) => a.id !== id);
  if (next.length === activities.length) return;
  activities = next;
  emit();
}
