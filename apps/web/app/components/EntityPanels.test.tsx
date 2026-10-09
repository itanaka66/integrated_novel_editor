import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CharacterPanel } from "./EntityPanels";
import { api, post, put, del } from "../lib/api";

vi.mock("../lib/api", () => ({
  api: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}));

describe("CharacterPanel (generic EntityPanel)", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
    vi.mocked(post).mockReset();
    vi.mocked(put).mockReset();
    vi.mocked(del).mockReset();
  });

  it("loads and renders the character list as a table row", async () => {
    vi.mocked(api).mockResolvedValue([{ id: 1, name: "田中", role: "主人公", personality: "慎重" }]);
    render(<CharacterPanel projectId={1} />);

    await waitFor(() => expect(screen.getByDisplayValue("田中")).toBeInTheDocument());
    expect(api).toHaveBeenCalledWith("/projects/1/characters");
  });

  it("editing a cell does not save by itself; the 更新 button saves the whole row via PUT", async () => {
    vi.mocked(api).mockResolvedValue([{ id: 1, name: "田中", role: "主人公", personality: "慎重", status: "alive" }]);
    vi.mocked(put).mockResolvedValue({});
    render(<CharacterPanel projectId={1} />);

    const nameInput = await screen.findByDisplayValue("田中");
    const update = screen.getByRole("button", { name: "更新" });
    expect(update).toBeDisabled(); // nothing edited yet

    fireEvent.change(nameInput, { target: { value: "田中太郎" } });
    fireEvent.blur(nameInput);
    expect(put).not.toHaveBeenCalled();
    expect(update).toBeEnabled();

    fireEvent.click(update);
    await waitFor(() => expect(put).toHaveBeenCalledWith("/characters/1", expect.objectContaining({ name: "田中太郎" })));
    await waitFor(() => expect(screen.getByRole("button", { name: "更新" })).toBeDisabled()); // clean again
  });

  it("adding a new row and filling the title field creates it, seeding cfg.defaults", async () => {
    vi.mocked(api).mockResolvedValueOnce([]).mockResolvedValueOnce([{ id: 2, name: "リナ", status: "alive" }]);
    vi.mocked(post).mockResolvedValue({ id: 2 });
    render(<CharacterPanel projectId={1} />);

    await waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByText("＋ 行を追加"));
    const nameInput = screen.getAllByRole("textbox")[0];
    fireEvent.change(nameInput, { target: { value: "リナ" } });
    fireEvent.click(screen.getByText("作成"));

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [path, body] = vi.mocked(post).mock.calls[0] as [string, Record<string, unknown>];
    expect(path).toBe("/projects/1/characters");
    expect(body.name).toBe("リナ");
    // "status" isn't a value the new-row form leaves blank — it's seeded
    // from cfg.defaults, exactly the mechanism that silently dropped
    // GlossaryPanel's hidden entity_type default before this was fixed.
    expect(body.status).toBe("alive");
  });

  it("does not create a new row until the title field has a value", async () => {
    vi.mocked(api).mockResolvedValue([]);
    render(<CharacterPanel projectId={1} />);

    await waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByText("＋ 行を追加"));
    fireEvent.click(screen.getByText("作成"));

    expect(post).not.toHaveBeenCalled();
  });

  it("deletes a character after confirmation", async () => {
    vi.mocked(api).mockResolvedValueOnce([{ id: 1, name: "田中" }]).mockResolvedValueOnce([]);
    vi.mocked(del).mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<CharacterPanel projectId={1} />);

    await screen.findByDisplayValue("田中");
    fireEvent.click(screen.getByText("削除"));

    await waitFor(() => expect(del).toHaveBeenCalledWith("/characters/1"));
  });

  it("does not delete when the confirmation is declined", async () => {
    vi.mocked(api).mockResolvedValue([{ id: 1, name: "田中" }]);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<CharacterPanel projectId={1} />);

    await screen.findByDisplayValue("田中");
    fireEvent.click(screen.getByText("削除"));

    expect(del).not.toHaveBeenCalled();
  });

  it("imports rows from a CSV file, ignoring unrecognized columns", async () => {
    vi.mocked(api).mockResolvedValueOnce([]).mockResolvedValueOnce([{ id: 3, name: "花子" }]);
    vi.mocked(post).mockResolvedValue({ id: 3 });
    const { container } = render(<CharacterPanel projectId={1} />);

    await waitFor(() => expect(api).toHaveBeenCalledTimes(1));
    const csv = "name,role,unknown_column\n花子,仲間,ignored-value\n";
    const file = new File([csv], "characters.csv", { type: "text/csv" });
    // jsdom's File doesn't implement .text() in this environment/version.
    Object.defineProperty(file, "text", { value: () => Promise.resolve(csv) });
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    await fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(post).toHaveBeenCalled());
    const [path, body] = vi.mocked(post).mock.calls[0] as [string, Record<string, unknown>];
    expect(path).toBe("/projects/1/characters");
    expect(body.name).toBe("花子");
    expect(body.role).toBe("仲間");
    expect(body).not.toHaveProperty("unknown_column");
    await waitFor(() => expect(screen.getByText(/1件を作成しました/)).toBeInTheDocument());
  });
});
