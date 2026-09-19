import { describe, it, expect } from "vitest";
import { computeQualityIssues } from "./qualityCheck";
import { Episode } from "./types";

function ep(overrides: Partial<Episode>): Episode {
  return { id: 1, project_id: 1, number: 1, title: "第1話", summary: "", content: "", updated_at: "", ...overrides };
}

describe("computeQualityIssues", () => {
  it("flags an empty title", () => {
    const issues = computeQualityIssues([ep({ id: 1, number: 3, title: "" })]);
    expect(issues.some((i) => i.message.includes("タイトルが空です"))).toBe(true);
  });

  it("flags a 第N話 title whose number doesn't match the actual episode number", () => {
    // Classic case this exists for: episode was renumbered (e.g. after a
    // bulk delete closed a gap) but its title text was never updated.
    const issues = computeQualityIssues([ep({ id: 1, number: 4, title: "第5話 目覚め" })]);
    expect(issues.some((i) => i.message.includes("話数（5）が実際の話数（4）と一致していません"))).toBe(true);
  });

  it("does not flag a title whose embedded number matches", () => {
    const issues = computeQualityIssues([ep({ id: 1, number: 5, title: "第5話 目覚め" })]);
    expect(issues.some((i) => i.message.includes("一致していません"))).toBe(false);
  });

  it("flags duplicate titles across episodes", () => {
    const issues = computeQualityIssues([
      ep({ id: 1, number: 1, title: "森の中" }),
      ep({ id: 2, number: 2, title: "町にて" }),
      ep({ id: 3, number: 3, title: "森の中" }),
    ]);
    expect(issues.some((i) => i.message.includes("「森の中」が第1話・第3話で重複しています"))).toBe(true);
  });

  it("flags English words mixed into otherwise-Japanese content", () => {
    const issues = computeQualityIssues([ep({ id: 1, number: 1, content: "彼はthe forestを歩いた。" })]);
    const hit = issues.find((i) => i.message.includes("英単語が混在"));
    expect(hit).toBeDefined();
    expect(hit!.message).toContain("the");
    expect(hit!.message).toContain("forest");
  });

  it("does not flag content with no Latin letters", () => {
    const issues = computeQualityIssues([ep({ id: 1, number: 1, content: "彼は森を歩いた。" })]);
    expect(issues.some((i) => i.message.includes("英単語"))).toBe(false);
  });

  it("returns no issues for a clean episode list", () => {
    const issues = computeQualityIssues([
      ep({ id: 1, number: 1, title: "第1話 出発", content: "静かな朝だった。" }),
      ep({ id: 2, number: 2, title: "第2話 到着", content: "町に着いた。" }),
    ]);
    expect(issues).toEqual([]);
  });
});
