"use client";
import { FormEvent, useEffect, useState } from "react";
import { api, API_ROOT, forgotPassword, setAuth } from "../lib/api";
import { applyStoredLanguage, isLangCode, LANGUAGES, readStoredLanguage, storeLanguage } from "../lib/i18n";

export default function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [oauthProviders, setOauthProviders] = useState<string[]>([]);
  const [showForgot, setShowForgot] = useState(false);
  // The only place the UI language can be changed: stored here, applied by a
  // reload right after a successful sign-in (see applyStoredLanguage). This
  // screen itself is deliberately English-only — the language isn't chosen yet.
  const [lang, setLang] = useState(readStoredLanguage());
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotMessage, setForgotMessage] = useState("");
  const [forgotBusy, setForgotBusy] = useState(false);

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
      if (!applyStoredLanguage()) onLoggedIn();
    } catch (err) {
      // api() throws a specifically-worded Error only for a real 401 —
      // anything else here (a network error, a CORS rejection) is not a
      // credentials problem, and telling the user their password is wrong
      // sends them on a wild goose chase re-typing a password that was
      // never the issue. See docs/requirements.md's CORS_ORIGINS section if
      // this keeps happening after double-checking the password.
      if (err instanceof Error && err.message === "unauthorized") {
        setError("Incorrect username or password.");
      } else {
        setError("Could not reach the API. Check that the server is running and that the CORS_ORIGINS environment variable includes this page's address.");
      }
    } finally { setBusy(false); }
  }

  const PROVIDER_LABELS: Record<string, string> = { google: "Sign in with Google", github: "Sign in with GitHub" };

  async function submitForgot(ev: FormEvent) {
    ev.preventDefault();
    setForgotBusy(true);
    try {
      const detail = await forgotPassword(forgotEmail);
      setForgotMessage(detail);
    } catch (err) {
      setForgotMessage(err instanceof Error ? err.message : "Something went wrong.");
    } finally { setForgotBusy(false); }
  }

  if (showForgot) {
    return (
      <div className="center">
        <form className="loginCard" onSubmit={submitForgot}>
          <b>✦ Reset password</b>
          <p>We will email a password-reset link to your registered address.</p>
          <input placeholder="Email address" type="email" value={forgotEmail} onChange={(e) => setForgotEmail(e.target.value)} autoFocus />
          {forgotMessage && <div className="loginError">{forgotMessage}</div>}
          <button type="submit" disabled={forgotBusy}>{forgotBusy ? "Sending..." : "Send reset email"}</button>
          <button type="button" className="loginOAuth loginOAuthLink" onClick={() => { setShowForgot(false); setForgotMessage(""); }}>Back to sign in</button>
        </form>
      </div>
    );
  }

  return (
    <div className="center">
      <form className="loginCard" onSubmit={submit}>
        <b>✦ Integrated Novel Editor</b>
        <p>Write your story with AI</p>
        <label className="loginLang">
          Display language
          <select value={lang} onChange={(e) => { const v = e.target.value; if (isLangCode(v)) { setLang(v); storeLanguage(v); } }} aria-label="Display language">
            {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
        </label>
        <input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <div className="loginError">{error}</div>}
        <button type="submit" disabled={busy}>{busy ? "Checking..." : "Sign in"}</button>
        <button type="button" className="loginOAuth loginOAuthLink" onClick={() => setShowForgot(true)}>Forgot your password?</button>
        <div className="loginDivider">or</div>
        {["google", "github"].map((p) =>
          oauthProviders.includes(p) ? (
            <a key={p} className="loginOAuth loginOAuthLink" href={`${API_ROOT}/auth/login/${p}`}>{PROVIDER_LABELS[p]}</a>
          ) : (
            <button key={p} type="button" className="loginOAuth" disabled title="This sign-in method is not configured on the server">{PROVIDER_LABELS[p]}</button>
          ),
        )}
      </form>
    </div>
  );
}
