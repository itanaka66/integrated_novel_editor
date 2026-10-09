import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// i18n reads the stored language once at module load (see lib/i18n.ts), so
// each case sets localStorage first and imports a fresh copy of the module.
async function loadWith(lang: string | null) {
  vi.resetModules();
  if (lang) localStorage.setItem("ine-lang", lang);
  else localStorage.removeItem("ine-lang");
  return import("./i18n");
}

describe("t()", () => {
  beforeEach(() => localStorage.removeItem("ine-lang"));
  afterEach(() => localStorage.removeItem("ine-lang"));

  it("returns the Japanese source text by default", async () => {
    const { t, getLanguage } = await loadWith(null);
    expect(getLanguage()).toBe("ja");
    expect(t("保存")).toBe("保存");
  });

  it.each([
    ["en", "Save"],
    ["zh-CN", "保存"],
    ["zh-TW", "儲存"],
    ["ko", "저장"],
    ["es", "Guardar"],
    ["fr", "Enregistrer"],
    ["de", "Speichern"],
  ])("translates into %s", async (lang, expected) => {
    const { t, getLanguage } = await loadWith(lang);
    expect(getLanguage()).toBe(lang);
    expect(t("保存")).toBe(expected);
  });

  it("fills in {placeholders}", async () => {
    const { t } = await loadWith("en");
    expect(t("こんにちは、{name}さん", { name: "Aki" })).toBe("Hello, Aki");
  });

  it("falls back to the Japanese text for a string with no translation", async () => {
    const { t } = await loadWith("fr");
    expect(t("まだ翻訳されていない文")).toBe("まだ翻訳されていない文");
  });

  it("ignores an unknown stored language", async () => {
    const { getLanguage } = await loadWith("xx");
    expect(getLanguage()).toBe("ja");
  });

  it("applyStoredLanguage does nothing while the stored language matches the loaded one", async () => {
    const { applyStoredLanguage } = await loadWith("en");
    expect(applyStoredLanguage()).toBe(false);
  });
});
