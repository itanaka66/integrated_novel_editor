import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import LlmActivityDialog from "./LlmActivityDialog";
import { beginActivity, endActivity, getActivities } from "../lib/llmActivity";
import { api } from "../lib/api";

vi.mock("../lib/api", () => ({ api: vi.fn() }));

beforeEach(() => { vi.mocked(api).mockReset(); vi.mocked(api).mockResolvedValue({ entries: [] }); });

afterEach(() => {
  for (const a of getActivities()) endActivity(a.id);
  vi.useRealTimers();
});

describe("LlmActivityDialog", () => {
  it("renders nothing while idle", () => {
    const { container } = render(<LlmActivityDialog />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows what the AI is doing with a progress bar, then disappears when done", () => {
    vi.useFakeTimers();
    render(<LlmActivityDialog />);
    let id: number | null = null;
    act(() => { id = beginActivity("POST", "/episodes/5/proofread/stream"); });
    // Not shown immediately — avoids flashing for very fast calls.
    expect(screen.queryByRole("dialog")).toBeNull();
    act(() => { vi.advanceTimersByTime(1500); });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/文章を校正しています/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    act(() => { endActivity(id); });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("LlmActivityDialog server queue", () => {
  it("lists running and waiting entries from the server, in order", async () => {
    vi.mocked(api).mockResolvedValue({
      entries: [
        { id: 1, position: 1, state: "running", kind_label: "Writer", model: "qwen3:8b", purpose: "自動執筆 EP.5: 本文生成", elapsed_seconds: 42 },
        { id: 2, position: 2, state: "waiting", kind_label: "Writer", model: "qwen3:8b", purpose: "AIチャット", elapsed_seconds: 7 },
      ],
    });
    render(<LlmActivityDialog />);
    expect(await screen.findByText(/1\. 自動執筆 EP\.5: 本文生成/)).toBeInTheDocument();
    expect(screen.getByText(/2\. AIチャット/)).toBeInTheDocument();
    expect(screen.getByText("実行中")).toBeInTheDocument();
    expect(screen.getByText("待機中")).toBeInTheDocument();
    expect(screen.getByText("実行中 1 / 待機 1")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });
});
