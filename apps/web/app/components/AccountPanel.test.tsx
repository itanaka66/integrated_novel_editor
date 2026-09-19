import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AccountPanel from "./AccountPanel";
import { api, changeMyPassword, post } from "../lib/api";

vi.mock("../lib/api", () => ({
  api: vi.fn(),
  changeMyPassword: vi.fn(),
  post: vi.fn(),
}));

describe("AccountPanel", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
    vi.mocked(changeMyPassword).mockReset();
    vi.mocked(post).mockReset();
  });

  it("changes the password and shows the server's confirmation message", async () => {
    vi.mocked(changeMyPassword).mockResolvedValue("パスワードを変更しました");
    render(<AccountPanel isAdmin={false} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("現在のパスワード"), { target: { value: "old-pass" } });
    fireEvent.change(screen.getByLabelText("新しいパスワード"), { target: { value: "new-pass" } });
    fireEvent.change(screen.getByLabelText("新しいパスワード（確認）"), { target: { value: "new-pass" } });
    fireEvent.click(screen.getByRole("button", { name: "パスワードを変更" }));

    await waitFor(() => expect(changeMyPassword).toHaveBeenCalledWith("old-pass", "new-pass"));
    expect(await screen.findByText("パスワードを変更しました")).toBeInTheDocument();
  });

  it("rejects a mismatched confirmation without calling the API", async () => {
    render(<AccountPanel isAdmin={false} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("現在のパスワード"), { target: { value: "old-pass" } });
    fireEvent.change(screen.getByLabelText("新しいパスワード"), { target: { value: "new-pass" } });
    fireEvent.change(screen.getByLabelText("新しいパスワード（確認）"), { target: { value: "different" } });
    fireEvent.click(screen.getByRole("button", { name: "パスワードを変更" }));

    expect(await screen.findByText("新しいパスワードが一致しません。")).toBeInTheDocument();
    expect(changeMyPassword).not.toHaveBeenCalled();
  });

  it("does not show user management for a non-admin", () => {
    render(<AccountPanel isAdmin={false} onCancel={vi.fn()} />);
    expect(screen.queryByText("ユーザー管理（管理者のみ）")).not.toBeInTheDocument();
    expect(api).not.toHaveBeenCalled();
  });

  it("loads and lists users, and can add a new one, for an admin", async () => {
    vi.mocked(api).mockResolvedValue([{ id: 1, username: "admin", email: null, is_admin: true, is_active: true }]);
    vi.mocked(post).mockResolvedValue({ id: 2, username: "newmember", email: null, is_admin: false, is_active: true });
    render(<AccountPanel isAdmin={true} onCancel={vi.fn()} />);

    await waitFor(() => expect(api).toHaveBeenCalledWith("/users"));
    expect(await screen.findByText("admin")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("新規ユーザー名"), { target: { value: "newmember" } });
    fireEvent.change(screen.getByLabelText("初期パスワード"), { target: { value: "init-pass" } });
    fireEvent.click(screen.getByRole("button", { name: "ユーザーを追加" }));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/users", { username: "newmember", password: "init-pass", is_admin: false, email: undefined }));
    expect(await screen.findByText("newmember")).toBeInTheDocument();
  });
});
