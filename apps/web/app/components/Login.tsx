"use client";
import { FormEvent, useEffect, useState } from "react";
import { api, API_ROOT, setAuth } from "../lib/api";

export default function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [oauthProviders, setOauthProviders] = useState<string[]>([]);

  useEffect(() => {
    // /health needs no login (see apps/api/app/auth.py's public paths), so
    // this is safe to call before the user has entered anything — it's
    // just asking which "Sign in with ..." buttons the server actually has
    // client_id/secret configured for (see config.py).
    api("/health").then((h) => setOauthProviders(h.oauth_providers || [])).catch(() => {});
  }, []);

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    setError(""); setBusy(true);
    setAuth(username, password);
    try {
      await api("/projects");
      onLoggedIn();
    } catch (err) {
      // api() throws a specifically-worded Error only for a real 401 —
      // anything else here (a network error, a CORS rejection) is not a
      // credentials problem, and telling the user their password is wrong
      // sends them on a wild goose chase re-typing a password that was
      // never the issue. See docs/requirements.md's CORS_ORIGINS section if
      // this keeps happening after double-checking the password.
      if (err instanceof Error && err.message === "unauthorized") {
        setError("ユーザー名またはパスワードが違います。");
      } else {
        setError("APIに接続できませんでした。サーバーが起動しているか、環境変数 CORS_ORIGINS にこのページのアドレスが含まれているかを確認してください。");
      }
    } finally { setBusy(false); }
  }

  const PROVIDER_LABELS: Record<string, string> = { google: "Googleでログイン", github: "GitHubでログイン" };

  return (
    <div className="center">
      <form className="loginCard" onSubmit={submit}>
        <b>✦ Integrated Novel Editor</b>
        <p>AIと創る、あなただけの物語</p>
        <input placeholder="ユーザー名" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <input placeholder="パスワード" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <div className="loginError">{error}</div>}
        <button type="submit" disabled={busy}>{busy ? "確認中..." : "ログイン"}</button>
        <div className="loginDivider">または</div>
        {["google", "github"].map((p) =>
          oauthProviders.includes(p) ? (
            <a key={p} className="loginOAuth loginOAuthLink" href={`${API_ROOT}/auth/login/${p}`}>{PROVIDER_LABELS[p]}</a>
          ) : (
            <button key={p} type="button" className="loginOAuth" disabled title="サーバー側でこのログイン方法が設定されていません">{PROVIDER_LABELS[p]}</button>
          ),
        )}
      </form>
    </div>
  );
}
