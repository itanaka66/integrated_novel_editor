import { ROWS } from "./locales";

export const LANGUAGES = [
  { code: "ja", label: "日本語" },
  { code: "en", label: "English" },
  { code: "zh-CN", label: "简体中文" },
  { code: "zh-TW", label: "繁體中文" },
  { code: "ko", label: "한국어" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "de", label: "Deutsch" },
] as const;

export type LangCode = (typeof LANGUAGES)[number]["code"];
export type Dict = Record<string, string>;

export const LANG_STORAGE_KEY = "ine-lang";

// Japanese is the source language: every UI string is written in Japanese at
// its call site, t("日本語") is the lookup key, and ja needs no dictionary.
// A string with no row just shows in Japanese rather than breaking
// (i18n.test.tsx fails before that can ship, though).
const COLUMN: Record<Exclude<LangCode, "ja">, number> = { en: 1, "zh-CN": 2, "zh-TW": 3, ko: 4, es: 5, fr: 6, de: 7 };

function buildDict(code: LangCode): Dict {
  if (code === "ja") return {};
  const col = COLUMN[code];
  const d: Dict = {};
  for (const row of ROWS) if (row[col]) d[row[0]] = row[col];
  return d;
}

export function isLangCode(v: unknown): v is LangCode {
  return LANGUAGES.some((l) => l.code === v);
}

export function readStoredLanguage(): LangCode {
  try {
    const v = localStorage.getItem(LANG_STORAGE_KEY);
    return isLangCode(v) ? v : "ja";
  } catch {
    return "ja";
  }
}

// The language this page load is rendering in. Read once, at module load,
// and never changed afterwards: plenty of UI text lives in module-level
// constants (sidebar items, tab lists, ...) evaluated exactly once, so
// switching languages in place would leave those stale. Instead the choice
// is only *stored* (at login) and applied by a page reload — see
// applyStoredLanguage().
const loadedLanguage: LangCode = typeof window === "undefined" ? "ja" : readStoredLanguage();
const dict: Dict = buildDict(loadedLanguage);

export function getLanguage(): LangCode {
  return loadedLanguage;
}

if (typeof document !== "undefined") document.documentElement.lang = loadedLanguage;

export function storeLanguage(code: LangCode): void {
  try {
    localStorage.setItem(LANG_STORAGE_KEY, code);
  } catch {
    /* localStorage unavailable; the language just won't persist */
  }
}

// Called right after a successful login: if the user picked a different
// language on the login screen than this page was loaded with, reload so
// every module re-evaluates in it. Returns true if it reloaded.
export function applyStoredLanguage(): boolean {
  if (typeof window !== "undefined" && readStoredLanguage() !== loadedLanguage) {
    window.location.reload();
    return true;
  }
  return false;
}

export function t(ja: string, vars?: Record<string, string | number>): string {
  let s = dict[ja] ?? ja;
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m));
  return s;
}
