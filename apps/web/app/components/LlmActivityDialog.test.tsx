import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import LlmActivityDialog from "./LlmActivityDialog";
import { beginActivity, endActivity, getActivities } from "../lib/llmActivity";

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
    expect(screen.getByText("文章を校正しています…")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    act(() => { endActivity(id); });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
