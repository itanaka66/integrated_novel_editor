import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import WritePanel from "./WritePanel";
import { api, post } from "../lib/api";
import { Project } from "../lib/types";

vi.mock("../lib/api", () => ({
  api: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));

const project: Project = { id: 1, name: "テスト作品", description: "", genre: "", rules: "" };

describe("WritePanel — episode management", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
    vi.mocked(post).mockReset();
  });

  it("bulk-deletes selected episodes and applies the renumbered result", async () => {
    vi.mocked(api).mockResolvedValue([
      { id: 1, project_id: 1, number: 1, title: "第1話", summary: "", content: "", updated_at: "" },
      { id: 2, project_id: 1, number: 2, title: "第2話", summary: "", content: "", updated_at: "" },
    ]);
    vi.mocked(post).mockResolvedValue({
      deleted_count: 1,
      renumbered_count: 1,
      episodes: [{ id: 1, project_id: 1, number: 1, title: "第1話", summary: "", content: "", updated_at: "" }],
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<WritePanel project={project} />);

    await screen.findByText("#001 第1話");
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]); // select episode #2

    fireEvent.click(screen.getByText(/件を削除（話数を自動調整）/));

    await waitFor(() => expect(post).toHaveBeenCalledWith("/projects/1/episodes/bulk-delete", { episode_ids: [2] }));
  });

  it("does not bulk-delete when nothing is selected", async () => {
    vi.mocked(api).mockResolvedValue([
      { id: 1, project_id: 1, number: 1, title: "第1話", summary: "", content: "", updated_at: "" },
    ]);
    render(<WritePanel project={project} />);

    await waitFor(() => expect(api).toHaveBeenCalled());
    expect(screen.getByText("選択した件を削除（話数を自動調整）")).toBeDisabled();
  });

  it("shows the quality-check modal with detected issues and jumps to the episode on click", async () => {
    vi.mocked(api).mockResolvedValue([
      { id: 1, project_id: 1, number: 1, title: "第2話 目覚め", summary: "", content: "", updated_at: "" },
      { id: 2, project_id: 1, number: 2, title: "第2話 目覚め", summary: "", content: "", updated_at: "" },
    ]);
    render(<WritePanel project={project} />);

    const checkButton = await screen.findByText(/^⚠ 品質チェック/);
    fireEvent.click(checkButton);

    expect(screen.getByText(/タイトル中の話数（2）が実際の話数（1）と一致していません/)).toBeInTheDocument();
    expect(screen.getByText(/「第2話 目覚め」が第1話・第2話で重複しています/)).toBeInTheDocument();
  });
});
