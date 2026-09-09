const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// The backend protects every /api/v1/* route (except /health) with a single
// shared HTTP Basic Auth admin/password pair — see apps/api/app/auth.py.
// There's no session/token, so "logging in" here just means resending these
// credentials from localStorage on every request.
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

export async function api(path: string, opts?: RequestInit) {
  const auth = getAuth();
  const headers = new Headers(opts?.headers);
  if (auth) headers.set("Authorization", "Basic " + btoa(`${auth.u}:${auth.pw}`));
  const r = await fetch(API + path, { ...opts, headers });
  if (r.status === 401) {
    onUnauthorized?.();
    throw new Error("unauthorized");
  }
  if (r.status === 204) return null;
  return r.json();
}
export async function post(p: string, b: unknown) {
  return api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
}
export async function put(p: string, b: unknown) {
  return api(p, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
}
export async function del(p: string) {
  return api(p, { method: "DELETE" });
}
