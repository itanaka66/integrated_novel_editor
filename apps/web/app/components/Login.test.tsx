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

    fireEvent.change(screen.getByPlaceholderText("Username"), { target: { value: "admin" } });
    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "novel" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(onLoggedIn).toHaveBeenCalled());
    expect(setAuth).toHaveBeenCalledWith("admin", "novel");
  });

  it("shows an error and does not log in when the check fails", async () => {
    vi.mocked(api).mockRejectedValue(new Error("unauthorized"));
    const onLoggedIn = vi.fn();
    render(<Login onLoggedIn={onLoggedIn} />);

    fireEvent.change(screen.getByPlaceholderText("Username"), { target: { value: "admin" } });
    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.getByText("Incorrect username or password.")).toBeInTheDocument());
    expect(onLoggedIn).not.toHaveBeenCalled();
  });

  it("shows a connectivity error, not a credentials error, for a network/CORS failure", async () => {
    vi.mocked(api).mockRejectedValue(new TypeError("Failed to fetch"));
    const onLoggedIn = vi.fn();
    render(<Login onLoggedIn={onLoggedIn} />);

    fireEvent.change(screen.getByPlaceholderText("Username"), { target: { value: "admin" } });
    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "novel" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(screen.getByText(/Could not reach the API/)).toBeInTheDocument());
    expect(screen.queryByText("Incorrect username or password.")).not.toBeInTheDocument();
    expect(onLoggedIn).not.toHaveBeenCalled();
  });

  it("disables the OAuth buttons when the server has no provider configured", async () => {
    vi.mocked(api).mockResolvedValue({ oauth_providers: [] });
    render(<Login onLoggedIn={vi.fn()} />);

    await waitFor(() => expect(api).toHaveBeenCalledWith("/health"));
    expect(screen.getByRole("button", { name: "Sign in with Google" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sign in with GitHub" })).toBeDisabled();
  });

  it("turns a configured provider into a real link to its login route", async () => {
    vi.mocked(api).mockResolvedValue({ oauth_providers: ["google"] });
    render(<Login onLoggedIn={vi.fn()} />);

    const googleLink = await screen.findByRole("link", { name: "Sign in with Google" });
    expect(googleLink).toHaveAttribute("href", "http://localhost:8000/auth/login/google");
    // GitHub wasn't in oauth_providers, so it stays a disabled placeholder.
    expect(screen.getByRole("button", { name: "Sign in with GitHub" })).toBeDisabled();
  });

  it("switches to the forgot-password form and reports the server's message", async () => {
    vi.mocked(api).mockResolvedValue({ oauth_providers: [] });
    vi.mocked(forgotPassword).mockResolvedValue("If that email address is registered, a password-reset email has been sent.");
    render(<Login onLoggedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Forgot your password?" }));
    fireEvent.change(screen.getByPlaceholderText("Email address"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Send reset email" }));

    await waitFor(() => expect(forgotPassword).toHaveBeenCalledWith("user@example.com"));
    expect(await screen.findByText(/a password-reset email has been sent/)).toBeInTheDocument();
  });
  it("offers all eight display languages and stores the choice", () => {
    localStorage.removeItem("ine-lang");
    vi.mocked(api).mockResolvedValue({ oauth_providers: [] });
    render(<Login onLoggedIn={vi.fn()} />);
    const select = screen.getByLabelText("Display language") as HTMLSelectElement;
    expect([...select.options].map((o) => o.value)).toEqual(["ja", "en", "zh-CN", "zh-TW", "ko", "es", "fr", "de"]);
    fireEvent.change(select, { target: { value: "ko" } });
    expect(localStorage.getItem("ine-lang")).toBe("ko");
  });

  it("reloads after sign-in when a different language was chosen, instead of continuing", async () => {
    localStorage.removeItem("ine-lang");
    vi.mocked(api).mockResolvedValue([]);
    const reload = vi.fn();
    const original = window.location;
    Object.defineProperty(window, "location", { configurable: true, value: { ...original, reload } });
    const onLoggedIn = vi.fn();
    render(<Login onLoggedIn={onLoggedIn} />);
    fireEvent.change(screen.getByLabelText("Display language"), { target: { value: "de" } });
    fireEvent.change(screen.getByPlaceholderText("Username"), { target: { value: "admin" } });
    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(reload).toHaveBeenCalled());
    expect(onLoggedIn).not.toHaveBeenCalled();
    Object.defineProperty(window, "location", { configurable: true, value: original });
    localStorage.removeItem("ine-lang");
  });
});
