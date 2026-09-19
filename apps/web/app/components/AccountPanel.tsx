"use client";
import { useEffect, useState } from "react";
import { api, changeMyPassword, post } from "../lib/api";

type UserRow = { id: number; username: string; email: string | null; is_admin: boolean; is_active: boolean };

export default function AccountPanel({ isAdmin, onCancel }: { isAdmin: boolean; onCancel: () => void }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwMessage, setPwMessage] = useState("");
  const [pwError, setPwError] = useState("");

  const [users, setUsers] = useState<UserRow[]>([]);
  const [newUsername, setNewUsername] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserIsAdmin, setNewUserIsAdmin] = useState(false);
  const [userBusy, setUserBusy] = useState(false);
  const [userError, setUserError] = useState("");

  useEffect(() => {
    if (isAdmin) api("/users").then(setUsers).catch(() => {});
  }, [isAdmin]);

  async function submitPassword() {
    setPwError(""); setPwMessage("");
    if (newPassword !== confirmPassword) { setPwError("新しいパスワードが一致しません。"); return; }
    setPwBusy(true);
    try {
      const detail = await changeMyPassword(currentPassword, newPassword);
      setPwMessage(detail);
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
    } catch (err) {
      setPwError(err instanceof Error ? err.message : "パスワードの変更に失敗しました。");
    } finally { setPwBusy(false); }
  }

  async function submitNewUser() {
    if (!newUsername.trim() || !newUserPassword) return;
    setUserError("");
    setUserBusy(true);
    try {
      const u = await post("/users", { username: newUsername, password: newUserPassword, is_admin: newUserIsAdmin, email: newUserEmail || undefined });
      setUsers((prev) => [...prev, u].sort((a, b) => a.username.localeCompare(b.username)));
      setNewUsername(""); setNewUserPassword(""); setNewUserEmail(""); setNewUserIsAdmin(false);
    } catch (err) {
      setUserError(err instanceof Error ? err.message : "ユーザーの追加に失敗しました。");
    } finally { setUserBusy(false); }
  }

  return (
    <div className="modalOverlay" onClick={onCancel}>
      <div className="modalCard" onClick={(e) => e.stopPropagation()}>
        <h1>アカウント設定</h1>

        <label>現在のパスワード<input type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} autoFocus /></label>
        <label>新しいパスワード<input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} /></label>
        <label>新しいパスワード（確認）<input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} /></label>
        {pwError && <p className="errorNote">{pwError}</p>}
        {pwMessage && !pwError && <p className="dashboardNote">{pwMessage}</p>}
        <div className="modalActions">
          <button onClick={submitPassword} disabled={pwBusy || !currentPassword || !newPassword}>{pwBusy ? "変更中..." : "パスワードを変更"}</button>
        </div>

        {isAdmin && (
          <>
            <h1>ユーザー管理（管理者のみ）</h1>
            <div className="cards">
              {users.map((u) => (
                <div className="card" key={u.id}>
                  <b>{u.username}</b>
                  <span>{u.is_admin ? "管理者" : "一般ユーザー"}{!u.is_active ? "・無効化済み" : ""}</span>
                </div>
              ))}
            </div>
            <label>新規ユーザー名<input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} /></label>
            <label>初期パスワード<input type="password" value={newUserPassword} onChange={(e) => setNewUserPassword(e.target.value)} /></label>
            <label>メールアドレス（任意・パスワード再設定に使用）<input type="email" value={newUserEmail} onChange={(e) => setNewUserEmail(e.target.value)} /></label>
            <label style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <input type="checkbox" checked={newUserIsAdmin} onChange={(e) => setNewUserIsAdmin(e.target.checked)} />
              管理者権限を付与する
            </label>
            {userError && <p className="errorNote">{userError}</p>}
            <div className="modalActions">
              <button onClick={submitNewUser} disabled={userBusy || !newUsername.trim() || !newUserPassword}>{userBusy ? "追加中..." : "ユーザーを追加"}</button>
            </div>
          </>
        )}

        <div className="modalActions">
          <button onClick={onCancel}>閉じる</button>
        </div>
      </div>
    </div>
  );
}
