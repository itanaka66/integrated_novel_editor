import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import CoverPanel from "./CoverPanel";
import { api } from "../lib/api";

vi.mock("../lib/api", () => ({ api: vi.fn(), fetchBlobUrl: vi.fn().mockResolvedValue("blob:x") }));

const STYLES = { default: "anime", styles: [{ key: "anime", label: "アニメ風" }, { key: "gekiga", label: "劇画風" }, { key: "photo", label: "実写風" }, { key: "other", label: "その他" }] };

function route(state: object) {
  vi.mocked(api).mockImplementation(async (path: string, opts?: RequestInit) => {
    if (path === "/cover/styles") return STYLES;
    if (path.endsWith("/cover/state") && opts?.method === "PUT") return { prompt: "", style: "anime", custom_style: "", provider: "comfyui", ...JSON.parse(String(opts.body)) };
    if (path.endsWith("/cover/state")) return state;
    if (path.endsWith("/covers")) return [];
    return {};
  });
}

describe("CoverPanel", () => {
  beforeEach(() => { vi.mocked(api).mockReset(); });
  afterEach(() => { vi.useRealTimers(); });

  it("offers the four looks and restores the saved prompt and look", async () => {
    route({ prompt: "saved prompt", style: "gekiga", custom_style: "", provider: "comfyui" });
    render(<CoverPanel projectId={1} />);
    expect(await screen.findByDisplayValue("saved prompt")).toBeInTheDocument();
    for (const l of ["アニメ風", "劇画風", "実写風", "その他"]) expect(screen.getByLabelText(l)).toBeInTheDocument();
    expect(screen.getByLabelText("劇画風")).toBeChecked();
  });

  it("asks for the user's own look when その他 is chosen", async () => {
    route({ prompt: "", style: "anime", custom_style: "", provider: "comfyui" });
    render(<CoverPanel projectId={1} />);
    await screen.findByLabelText("その他");
    expect(screen.queryByPlaceholderText(/自由に記入/)).toBeNull();
    fireEvent.click(screen.getByLabelText("その他"));
    expect(await screen.findByPlaceholderText(/自由に記入/)).toBeInTheDocument();
  });

  it("saves edits to the prompt automatically", async () => {
    route({ prompt: "", style: "anime", custom_style: "", provider: "comfyui" });
    render(<CoverPanel projectId={1} />);
    const box = await screen.findByPlaceholderText(/英語プロンプト/);
    vi.useFakeTimers();
    fireEvent.change(box, { target: { value: "my edit" } });
    await act(async () => { vi.advanceTimersByTime(800); });
    const put = vi.mocked(api).mock.calls.find(([p, o]) => String(p).endsWith("/cover/state") && (o as RequestInit | undefined)?.method === "PUT");
    expect(put).toBeTruthy();
    expect(JSON.parse(String((put![1] as RequestInit).body)).prompt).toBe("my edit");
  });

  it("sends the chosen look when creating the prompt and when generating", async () => {
    route({ prompt: "p", style: "photo", custom_style: "", provider: "comfyui" });
    render(<CoverPanel projectId={1} />);
    await screen.findByDisplayValue("p");
    fireEvent.click(screen.getByText("作品内容からプロンプトを作成"));
    await waitFor(() => expect(vi.mocked(api).mock.calls.some(([p, o]) => String(p).endsWith("/cover/prompt") && JSON.parse(String((o as RequestInit).body)).style === "photo")).toBe(true));
    fireEvent.click(screen.getByText("表紙を生成"));
    await waitFor(() => expect(vi.mocked(api).mock.calls.some(([p, o]) => String(p).endsWith("/cover/generate") && JSON.parse(String((o as RequestInit).body)).style === "photo")).toBe(true));
  });
});
