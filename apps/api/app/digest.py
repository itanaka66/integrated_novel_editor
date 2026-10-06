"""Pick the climax episodes of a project for a 総集編 (digest) edition.

Pure functions only (no DB / LLM) so the selection is deterministic and
cheap: a long series can have hundreds of episodes, and scoring each one
through a local LLM would take far longer than the digest is worth.
Climax-ness is inferred from structure the author already recorded —
where plot arcs end, where foreshadowing pays off — plus the opening and
final episodes, with a small text-intensity term to break ties.
"""
import re

_INTENSITY_RE = re.compile(r'[！？!?]|……')


def _intensity(content: str) -> float:
    """0..1 — density of exclamations/questions/ellipses, capped."""
    if not content:
        return 0.0
    return min(1.0, len(_INTENSITY_RE.findall(content)) / max(1, len(content)) * 40)


def score_episodes(episodes, plots, foreshadowings) -> dict[int, float]:
    numbers = {e.number for e in episodes}
    scores = {e.number: _intensity(e.content) for e in episodes}
    for p in plots:
        if p.end_episode in numbers:
            scores[p.end_episode] += 3.0
    for f in foreshadowings:
        if f.payoff_episode in numbers:
            scores[f.payoff_episode] += 2.0
    if numbers:
        scores[max(numbers)] += 5.0
        scores[min(numbers)] += 2.0
    return scores


def select_climax(episodes, plots, foreshadowings, ratio: float = 0.5):
    """Return the episodes (in story order) that best fit ``ratio`` of the
    total text length, highest climax score first."""
    episodes = sorted(episodes, key=lambda e: e.number)
    total = sum(len(e.content or '') for e in episodes)
    if not episodes:
        return []
    budget = total * ratio
    scores = score_episodes(episodes, plots, foreshadowings)
    chosen, used = [], 0
    for e in sorted(episodes, key=lambda e: (-scores[e.number], e.number)):
        size = len(e.content or '')
        if chosen and used + size > budget:
            continue
        chosen.append(e)
        used += size
    return sorted(chosen, key=lambda e: e.number)
