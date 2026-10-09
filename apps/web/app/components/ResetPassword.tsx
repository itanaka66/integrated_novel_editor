"use client";
import { FormEvent, useEffect, useState } from "react";
import { resetPassword } from "../lib/api";

export default function ResetPassword() {
  const [token, setToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    // Read once on mount, from the plain URL query string — no
    // next/navigation useSearchParams here, since that would force this
    // page out of static prerendering for a value read exactly once.
    setToken(new URLSearchParams(window.location.search).get("token") || "");
  }, []);

  async function submit(ev: FormEvent) {
    ev.preventDefault();
    setError("");
    if (newPassword !== confirm) {
      setError("The new passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      const detail = await resetPassword(token, newPassword);
      setMessage(detail);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally { setBusy(false); }
  }

  if (!token) {
    return (
      <div className="center">
        <div className="loginCard">
          <b>✦ Integrated Novel Editor</b>
          <p>This link is invalid. Please start again from the link in the password-reset email.</p>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="center">
        <div className="loginCard">
          <b>✦ Reset password</b>
          <p>{message}</p>
          <a className="loginOAuth loginOAuthLink" href="/">Go to sign in</a>
        </div>
      </div>
    );
  }

  return (
    <div className="center">
      <form className="loginCard" onSubmit={submit}>
        <b>✦ Reset password</b>
        <input placeholder="New password" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoFocus />
        <input placeholder="Confirm new password" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        {error && <div className="loginError">{error}</div>}
        <button type="submit" disabled={busy}>{busy ? "Sending..." : "Reset password"}</button>
      </form>
    </div>
  );
}
