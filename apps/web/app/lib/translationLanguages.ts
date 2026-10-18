export type TranslationLanguage = { code: string; english: string; native: string; japanese: string };

// Every language a work can be translated into. The first eight are also what 全翻訳 covers.
export const TRANSLATION_LANGUAGES: TranslationLanguage[] = [
  { code: "ja", english: "Japanese", native: "日本語", japanese: "日本語" },
  { code: "en", english: "English", native: "English", japanese: "英語" },
  { code: "zh-CN", english: "Chinese (Simplified)", native: "简体中文", japanese: "中国語（簡体字）" },
  { code: "ko", english: "Korean", native: "한국어", japanese: "韓国語" },
  { code: "es", english: "Spanish", native: "Español", japanese: "スペイン語" },
  { code: "fr", english: "French", native: "Français", japanese: "フランス語" },
  { code: "de", english: "German", native: "Deutsch", japanese: "ドイツ語" },
  { code: "pt-BR", english: "Portuguese (Brazil)", native: "Português (BR)", japanese: "ポルトガル語（ブラジル）" },
  { code: "it", english: "Italian", native: "Italiano", japanese: "イタリア語" },
  { code: "nl", english: "Dutch", native: "Nederlands", japanese: "オランダ語" },
  { code: "pl", english: "Polish", native: "Polski", japanese: "ポーランド語" },
  { code: "uk", english: "Ukrainian", native: "Українська", japanese: "ウクライナ語" },
  { code: "tr", english: "Turkish", native: "Türkçe", japanese: "トルコ語" },
  { code: "ar", english: "Arabic", native: "العربية", japanese: "アラビア語" },
  { code: "hi", english: "Hindi", native: "हिन्दी", japanese: "ヒンディー語" },
  { code: "vi", english: "Vietnamese", native: "Tiếng Việt", japanese: "ベトナム語" },
  { code: "th", english: "Thai", native: "ไทย", japanese: "タイ語" },
  { code: "id", english: "Indonesian", native: "Bahasa Indonesia", japanese: "インドネシア語" },
  { code: "sv", english: "Swedish", native: "Svenska", japanese: "スウェーデン語" },
  { code: "el", english: "Greek", native: "Ελληνικά", japanese: "ギリシャ語" },
  { code: "fa", english: "Persian", native: "فارسی", japanese: "ペルシア語" },
  { code: "ms", english: "Malay", native: "Bahasa Melayu", japanese: "マレー語" },
];

export const CORE_TRANSLATION_CODES = TRANSLATION_LANGUAGES.slice(0, 8).map((l) => l.code);

// 「英語名 / 現地語名 / 日本語名」 as shown in the language drop-down.
export function languageOptionLabel(l: TranslationLanguage): string {
  return `${l.english} / ${l.native} / ${l.japanese}`;
}
