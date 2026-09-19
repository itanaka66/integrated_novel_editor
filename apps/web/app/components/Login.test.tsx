import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Login from "./Login";
import { api, forgotPassword, setAuth } from "../lib/api";

vi.mock("../lib/api", () => ({
  api: vi.fn(),
  setAuth: vi.fn(),
  forgotPassword: vi.fn(),
  API_ROOT: "http://localhost:8000",
}));

describe("Login", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
    vi.mocked(setAuth).mockReset();
    vi.mocked(forgotPassword).mockReset();
  });

  it("stores credentials and calls onLoggedIn when the check succeeds", async () => {
    vi.mocked(api).mockResolvedValue([]);
    const onLoggedIn = vi.fn();
    render(<Login onLoggedIn={onLoggedIn} />);

    fireEvent.change(screen.getByPlaceholderText("ユーザー名"), { target: { value: "admin" } });
    fireEvent.change(screen.getByPlaceholderText("パスワード"), { target: { value: "novel" } });
    fireEvent.click(screen.getByRole("button", { name: "ログイン" }));

    await waitFor(() => expect(onLoggedIn).toHaveBeenCalled());
    expect(setAuth).toHaveBeenCalledWith("admin", "novel");
  });

  it("shows an error and does not log in when the check fails", async () => {
    vi.mocked(api).mockRejectedValue(new Error("unauthorized"));
    const onLoggedIn = vi.fn();
    render(<Login onLoggedIn={onLoggedIn} />);

    fireEvent.change(screen.getByPlaceholderText("ユーザー名"), { target: { value: "admin" } });
    fireEvent.change(screen.getByPlaceholderText("パスワード"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "ログイン" }));

    await waitFor(() => expect(screen.getByText("ユーザー名またはパスワードが違います。")).toBeInTheDocument());
    expect(onLoggedIn).not.toHaveBeenCalled();
  });

  it("shows a connectivity error, not a credentials error, for a network/CORS failure", async () => {
    vi.mocked(api).mockRejectedValue(new TypeError("Failed to fetch"));
    const onLoggedIn = vi.fn();
    render(<Login onLoggedIn={onLoggedIn} />);

    fireEvent.change(screen.getByPlaceholderText("ユーザー名"), { target: { value: "admin" } });
    fireEvent.change(screen.getByPlaceholderText("パスワード"), { target: { value: "novel" } });
    fireEvent.click(screen.getByRole("button", { name: "ログイン" }));

    await waitFor(() => expect(screen.getByText(/APIに接続できませんでした/)).toBeInTheDocument());
    expect(screen.queryByText("ユーザー名またはパスワードが違います。")).not.toBeInTheDocument();
    expect(onLoggedIn).not.toHaveBeenCalled();
  });

  it("disables the OAuth buttons when the server has no provider configured", async () => {
    vi.mocked(api).mockResolvedValue({ oauth_providers: [] });
    render(<Login onLoggedIn={vi.fn()} />);

    await waitFor(() => expect(api).toHaveBeenCalledWith("/health"));
    expect(screen.getByRole("button", { name: "Googleでログイン" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "GitHubでログイン" })).toBeDisabled();
  });

  it("turns a configured provider into a real link to its login route", async () => {
    vi.mocked(api).mockResolvedValue({ oauth_providers: ["google"] });
    render(<Login onLoggedIn={vi.fn()} />);

    const googleLink = await screen.findByRole("link", { name: "Googleでログイン" });
    expect(googleLink).toHaveAttribute("href", "http://localhost:8000/auth/login/google");
    // GitHub wasn't in oauth_providers, so it stays a disabled placeholder.
    expect(screen.getByRole("button", { name: "GitHubでログイン" })).toBeDisabled();
  });

  it("switches to the forgot-password form and reports the server's message", async () => {
    vi.mocked(api).mockResolvedValue({ oauth_providers: [] });
    vi.mocked(forgotPassword).mockResolvedValue("登録されているメールアドレス宛てに、パスワード再設定用のメールを送信しました。");
    render(<Login onLoggedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "パスワードをお忘れですか？" }));
    fireEvent.change(screen.getByPlaceholderText("メールアドレス"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "再設定メールを送信" }));

    await waitFor(() => expect(forgotPassword).toHaveBeenCalledWith("user@example.com"));
    expect(await screen.findByText(/再設定用のメールを送信しました/)).toBeInTheDocument();
  });
});
