// One row per UI string: the Japanese source text (also the lookup key)
// followed by its translation into each other language, in this fixed order.
// Keeping a string's seven translations on one line (instead of one
// dictionary file per language) makes a missing or misordered translation
// visible at a glance, and i18n.test.tsx checks every row for completeness
// and matching {placeholders}.
export type Row = readonly [
  ja: string,
  en: string,
  zhCN: string,
  zhTW: string,
  ko: string,
  es: string,
  fr: string,
  de: string,
];
