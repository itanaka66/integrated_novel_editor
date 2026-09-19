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
      setError("新しいパスワードが一致しません。");
      return;
    }
    setBusy(true);
    try {
      const detail = await resetPassword(token, newPassword);
      setMessage(detail);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "エラーが発生しました。");
    } finally { setBusy(false); }
  }

  if (!token) {
    return (
      <div className="center">
        <div className="loginCard">
          <b>✦ Integrated Novel Editor</b>
          <p>無効なリンクです。パスワード再設定メールのリンクからやり直してください。</p>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="center">
        <div className="loginCard">
          <b>✦ パスワード再設定</b>
          <p>{message}</p>
          <a className="loginOAuth loginOAuthLink" href="/">ログイン画面へ</a>
        </div>
      </div>
    );
  }

  return (
    <div className="center">
      <form className="loginCard" onSubmit={submit}>
        <b>✦ パスワード再設定</b>
        <input placeholder="新しいパスワード" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} autoFocus />
        <input placeholder="新しいパスワード（確認）" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        {error && <div className="loginError">{error}</div>}
        <button type="submit" disabled={busy}>{busy ? "送信中..." : "パスワードを再設定"}</button>
      </form>
    </div>
  );
}
