import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { LANGUAGES } from "./i18n";
import { ROWS } from "./locales";

// Every UI string is written in Japanese at its t("...") call site, and that
// Japanese text is also the lookup key — so the source files themselves are
// the list of keys that need a translation row.
function sourceKeys(): Set<string> {
  const root = join(__dirname, "..");
  const files = [
    ...readdirSync(join(root, "components")).filter((f) => f.endsWith(".tsx") && !f.includes(".test.")).map((f) => join(root, "components", f)),
    ...readdirSync(join(root, "lib")).filter((f) => f.endsWith(".ts") && f !== "i18n.ts").map((f) => join(root, "lib", f)),
    join(root, "studio.tsx"),
  ];
  const keys = new Set<string>();
  const re = /\bt\(\s*"((?:[^"\\]|\\.)*)"/g;
  for (const f of files) {
    const src = readFileSync(f, "utf8");
    for (const m of src.matchAll(re)) keys.add(m[1].replace(/\\"/g, '"'));
  }
  return keys;
}

const placeholders = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort().join(",");
const hasJapanese = (s: string) => /[぀-ヿ一-鿿]/.test(s);

describe("i18n translation table", () => {
  it("has eight languages, Japanese first", () => {
    expect(LANGUAGES.map((l) => l.code)).toEqual(["ja", "en", "zh-CN", "zh-TW", "ko", "es", "fr", "de"]);
  });

  it("has a row for every string used in the UI", () => {
    const have = new Set(ROWS.map((r) => r[0]));
    const missing = [...sourceKeys()].filter((k) => hasJapanese(k) && !have.has(k));
    expect(missing).toEqual([]);
  });

  it("has no unused or duplicate rows", () => {
    const used = sourceKeys();
    const keys = ROWS.map((r) => r[0]);
    expect(keys.filter((k, i) => keys.indexOf(k) !== i)).toEqual([]);
    expect(keys.filter((k) => !used.has(k))).toEqual([]);
  });

  it("translates every row into all seven other languages, keeping {placeholders}", () => {
    const problems: string[] = [];
    for (const row of ROWS) {
      expect(row).toHaveLength(8);
      for (let i = 1; i < row.length; i++) {
        if (!row[i].trim() && row[i] !== row[0]) problems.push(`empty [${LANGUAGES[i].code}] ${row[0]}`);
        if (placeholders(row[i]) !== placeholders(row[0])) problems.push(`placeholders [${LANGUAGES[i].code}] ${row[0]}`);
      }
    }
    expect(problems).toEqual([]);
  });
});
