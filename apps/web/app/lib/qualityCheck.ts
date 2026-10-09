import { Episode } from "./types";
import { t } from "../lib/i18n";

export type QualityIssue = { episodeId: number | null; episodeNumber: number | null; message: string };

// Matches "第5話" style episode-number call-outs embedded in a title, so a
// stale one left over from before a renumber (or a copy-paste typo) can be
// caught — only Arabic numerals, matching what addEpisode() itself always
// generates ("第${number}話").
const TITLE_NUMBER_RE = /第\s*(\d+)\s*話/;

// Runs of 2+ Latin letters — a lightweight heuristic for English words that
// crept into otherwise-Japanese prose (a known AI-generation artifact).
// Deliberately not fussy about proper nouns/loanwords the author intended;
// this is a review aid, not an auto-fix, so false positives are cheap and
// false negatives (missing a real mix-in) are the worse failure mode.
const ENGLISH_WORD_RE = /[A-Za-z]{2,}/g;

export function computeQualityIssues(episodes: Episode[]): QualityIssue[] {
  const issues: QualityIssue[] = [];
  const titleOccurrences = new Map<string, Episode[]>();

  for (const ep of episodes) {
    const title = ep.title?.trim() ?? "";
    if (!title) {
      issues.push({ episodeId: ep.id, episodeNumber: ep.number, message: t("第{n}話：タイトルが空です", { n: ep.number }) });
    } else {
      const m = title.match(TITLE_NUMBER_RE);
      if (m && Number(m[1]) !== ep.number) {
        issues.push({
          episodeId: ep.id,
          episodeNumber: ep.number,
          message: t("第{n}話「{title}」：タイトル中の話数（{m}）が実際の話数（{n}）と一致していません", { n: ep.number, title, m: m[1] }),
        });
      }
      const list = titleOccurrences.get(title) ?? [];
      list.push(ep);
      titleOccurrences.set(title, list);
    }

    const words = Array.from(new Set(ep.content?.match(ENGLISH_WORD_RE) ?? []));
    if (words.length > 0) {
      const shown = words.slice(0, 8).join("、") + (words.length > 8 ? t(" 他") : "");
      issues.push({ episodeId: ep.id, episodeNumber: ep.number, message: t("第{n}話「{title}」：本文に英単語が混在しています（{shown}）", { n: ep.number, title: title || t("（無題）"), shown }) });
    }
  }

  for (const [title, eps] of titleOccurrences) {
    if (eps.length > 1) {
      const numbers = eps.map((x) => x.number).sort((a, b) => a - b);
      issues.push({
        episodeId: eps[0].id,
        episodeNumber: eps[0].number,
        message: t("タイトル「{title}」が第{nums}話で重複しています", { title, nums: numbers.join(t("話・第")) }),
      });
    }
  }

  return issues;
}
