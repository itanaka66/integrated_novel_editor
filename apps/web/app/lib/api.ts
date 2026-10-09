import { beginActivity, endActivity } from "./llmActivity";
import { t } from "../lib/i18n";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
// editor_common.oauth's login/callback/logout routes (see app/main.py) are
// mounted on the API app directly, not under /api/v1 — this is the same
// origin with that suffix stripped, e.g. "http://localhost:8000".
export const API_ROOT = API.replace(/\/api\/v1\/?$/, "");

// The backend protects every /api/v1/* route (except /health) with either
// HTTP Basic Auth (a username/password pair resent from localStorage on
// every request — see apps/api/app/auth.py) or a signed session cookie set
// by a Google/GitHub OAuth2 login (editor_common.oauth). Every request
// below sends credentials: "include" so that cookie actually reaches the
// API even when it's a different origin from the web app (CORS already
// allows credentialed requests — see DynamicCORSMiddleware).
const AUTH_KEY = "ns-auth";

export function getAuth(): { u: string; pw: string } | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
export function setAuth(u: string, pw: string) {
  try {
    localStorage.setItem(AUTH_KEY, JSON.stringify({ u, pw }));
  } catch {
    /* localStorage unavailable; session just won't persist */
  }
}
export function clearAuth() {
  try {
    localStorage.removeItem(AUTH_KEY);
  } catch {
    /* localStorage unavailable */
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

function jsonBodyOf(opts?: RequestInit): unknown {
  try {
    return typeof opts?.body === "string" ? JSON.parse(opts.body) : undefined;
  } catch {
    return undefined;
  }
}

export async function api(path: string, opts?: RequestInit) {
  const auth = getAuth();
  const headers = new Headers(opts?.headers);
  if (auth) headers.set("Authorization", "Basic " + btoa(`${auth.u}:${auth.pw}`));
  // Registers this call with LlmActivityDialog if it's one that waits on an
  // LLM (see lib/llmActivity.ts); a no-op (null) for everything else.
  const activity = beginActivity(opts?.method || "GET", path, jsonBodyOf(opts));
  try {
    const r = await fetch(API + path, { ...opts, headers, credentials: "include" });
    if (r.status === 401) {
      onUnauthorized?.();
      throw new Error("unauthorized");
    }
    if (r.status === 204) return null;
    return await r.json();
  } finally {
    endActivity(activity);
  }
}

// A lightweight "am I actually logged in" probe — true for either a stored
// Basic Auth pair OR a valid OAuth2 session cookie (there's no way to tell
// the cookie is there and valid without asking the server; unlike Basic
// Auth's localStorage pair, it isn't readable from JavaScript at all,
// httpOnly on purpose). Never throws — any failure (network, CORS, a real
// 401) just means "not logged in".
export async function checkSession(): Promise<boolean> {
  try {
    await api("/projects");
    return true;
  } catch {
    return false;
  }
}

// Who's behind whichever credential actually authenticated this request
// (Basic Auth pair or OAuth2 session cookie), and whether that account has
// admin rights (gates the user-management UI) — see GET /api/v1/me.
export type CurrentUser = { username: string; isAdmin: boolean };
export async function getCurrentUser(): Promise<CurrentUser | null> {
  try {
    const r = await api("/me");
    return { username: r.username as string, isAdmin: !!r.is_admin };
  } catch {
    return null;
  }
}

// Clears the stored Basic Auth pair and asks the server to drop the OAuth2
// session cookie, if any — best-effort; local state is cleared either way,
// since that alone is enough to make studio.tsx show the login screen
// again even if this network call itself fails.
export async function logout(): Promise<void> {
  clearAuth();
  try {
    await fetch(`${API_ROOT}/auth/logout`, { credentials: "include" });
  } catch {
    /* server unreachable; the local sign-out above still stands */
  }
}
// Changes the logged-in user's own password (GET /api/v1/me identifies
// who that is server-side). Unlike api()/post(), this checks r.ok and
// throws with the server's Japanese error message (e.g. wrong current
// password) instead of silently returning it as if the call succeeded.
export async function changeMyPassword(currentPassword: string, newPassword: string): Promise<string> {
  const auth = getAuth();
  const headers = new Headers({ "Content-Type": "application/json" });
  if (auth) headers.set("Authorization", "Basic " + btoa(`${auth.u}:${auth.pw}`));
  const r = await fetch(`${API}/me/password`, {
    method: "PUT",
    headers,
    credentials: "include",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  const body = await r.json().catch(() => ({}));
  if (r.status === 401) {
    onUnauthorized?.();
    throw new Error("unauthorized");
  }
  if (!r.ok) throw new Error(body.detail || t("パスワードの変更に失敗しました。"));
  return body.detail as string;
}

// Both below are called from outside any logged-in session (a forgotten
// password, by definition) — plain fetch() against API_ROOT's /auth/...
// routes (public, see apps/api/app/auth.py's public_path_prefixes),
// never api()'s API (=.../api/v1) base or its Basic Auth header.
export async function forgotPassword(email: string): Promise<string> {
  const r = await fetch(`${API_ROOT}/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || "Something went wrong.");
  return body.detail as string;
}
export async function resetPassword(token: string, newPassword: string): Promise<string> {
  const r = await fetch(`${API_ROOT}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(body.detail || "Something went wrong.");
  return body.detail as string;
}

export async function post(p: string, b: unknown) {
  return api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
}
export async function put(p: string, b: unknown) {
  return api(p, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
}
export async function postFile(p: string, file: File) {
  // No Content-Type header here on purpose — the browser sets the
  // multipart boundary itself; overriding it breaks the upload.
  const form = new FormData();
  form.append("file", file);
  return api(p, { method: "POST", body: form });
}
export async function del(p: string) {
  return api(p, { method: "DELETE" });
}

// Server-Sent Events, consumed manually via fetch()+ReadableStream instead of
// the browser's native EventSource — EventSource can't send an Authorization
// header, and this API requires one on every request. Returns a function
// that aborts the stream (call it on unmount / when switching jobs).
export function streamSSE(path: string, onMessage: (data: unknown) => void, onDone?: () => void, body?: unknown): () => void {
  const controller = new AbortController();
  (async () => {
    const auth = getAuth();
    const headers = new Headers();
    if (auth) headers.set("Authorization", "Basic " + btoa(`${auth.u}:${auth.pw}`));
    const init: RequestInit = { headers, signal: controller.signal, credentials: "include" };
    if (body !== undefined) {
      headers.set("Content-Type", "application/json");
      init.method = "POST";
      init.body = JSON.stringify(body);
    }
    const activity = beginActivity(init.method || "GET", path, body);
    try {
      const r = await fetch(API + path, init);
      if (r.status === 401) {
        onUnauthorized?.();
        return;
      }
      if (!r.body) return;
      const reader = r.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) >= 0) {
          const chunk = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          const line = chunk.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          try {
            onMessage(JSON.parse(line.slice(6)));
          } catch {
            /* malformed chunk; ignore */
          }
        }
      }
    } catch (err) {
      if ((err as { name?: string }).name !== "AbortError") throw err;
    } finally {
      endActivity(activity);
      onDone?.();
    }
  })();
  return () => controller.abort();
}

// Triggers a browser download for an endpoint that returns a file body
// (Content-Disposition: attachment) rather than JSON — export downloads.
export async function downloadFile(path: string, fallbackFilename: string) {
  const auth = getAuth();
  const headers = new Headers();
  if (auth) headers.set("Authorization", "Basic " + btoa(`${auth.u}:${auth.pw}`));
  const r = await fetch(API + path, { headers, credentials: "include" });
  if (r.status === 401) {
    onUnauthorized?.();
    throw new Error("unauthorized");
  }
  if (!r.ok) throw new Error(`Export failed: ${r.status}`);
  const blob = await r.blob();
  const disposition = r.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : fallbackFilename;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Fetches an authenticated binary endpoint (e.g. a cover image) and returns
// an object URL — <img src> can't send the Basic Auth header itself.
export async function fetchBlobUrl(path: string): Promise<string> {
  const auth = getAuth();
  const headers = new Headers();
  if (auth) headers.set("Authorization", "Basic " + btoa(`${auth.u}:${auth.pw}`));
  const r = await fetch(API + path, { headers, credentials: "include" });
  if (r.status === 401) {
    onUnauthorized?.();
    throw new Error("unauthorized");
  }
  if (!r.ok) throw new Error(`Fetch failed: ${r.status}`);
  return URL.createObjectURL(await r.blob());
}
