"""Find source sentences a translation left out, without asking a chat model.

Both texts are split into sentences and embedded with a multilingual embedding
model (bge-m3 by default); a source sentence whose best match among the
translated sentences (or two neighbours together, for split sentences) is far
less similar than usual was omitted. In a real run, sentences that were
translated scored 0.73-0.95 against their counterpart, while a dropped sentence
scored 0.58 at best. Judging omissions with another chat model turned out
unreliable (it called faithful translations faulty and missed the real gap), and
length-based alignment could not separate short neighbouring sentences, so this
compares meaning instead. Cheap: one embedding call per chunk."""
import logging
import math

logger = logging.getLogger(__name__)

# A source sentence needs a counterpart at least this similar (cosine).
SIMILARITY_FLOOR = 0.66
_END = '.!?…。！？'
_CLOSERS = '"”»\'’」』）)]】'
_MIN_CHARS = 6  # shorter source sentences ("はい。") are too small to judge
_IGNORED = set(_END + _CLOSERS + '「『（([【 \t　')


def split_sentences(text: str) -> list[str]:
    out: list[str] = []
    for line in (text or '').split('\n'):
        cur = ''
        i = 0
        while i < len(line):
            ch = line[i]
            cur += ch
            if ch in _END:
                # swallow trailing end marks and closing quotes: 「…。」 / …?!"
                while True:
                    if i + 1 < len(line) and (line[i + 1] in _END or line[i + 1] in _CLOSERS):
                        i += 1
                    elif i + 2 < len(line) and line[i + 1] == ' ' and line[i + 2] in '»”’':  # French: « … . »
                        i += 2
                        cur += ' '
                    else:
                        break
                    cur += line[i]
                # Latin text: "3.5" or "e.g.x" - only split before whitespace/end
                if ch == '.' and i + 1 < len(line) and not line[i + 1].isspace() and line[i + 1].isalnum():
                    i += 1
                    continue
                if cur.strip():
                    out.append(cur.strip())
                cur = ''
            i += 1
        if cur.strip():
            out.append(cur.strip())
    return out


def size(sentence: str) -> int:
    return sum(1 for ch in sentence if ch not in _IGNORED)


def _cos(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def omitted_sentences(src: list[str], src_vecs: list[list[float]], out_vecs: list[list[float]],
                      pair_vecs: list[list[float]], floor: float = SIMILARITY_FLOOR) -> list[str]:
    """Pure part: the source sentences (long enough to judge) whose best similarity
    to any translated sentence / adjacent pair is below `floor`."""
    candidates = out_vecs + pair_vecs
    missing = []
    for sentence, v in zip(src, src_vecs):
        if size(sentence) < _MIN_CHARS:
            continue
        best = max((_cos(v, c) for c in candidates), default=0.0)
        if best < floor:
            missing.append(sentence)
    return missing


async def find_omissions(src: str, out: str, embed) -> list[str]:
    """Source sentences with no counterpart in `out`. `embed` is an async function
    list[str] -> list[vector]. Returns [] when there is too little text to judge or
    the embedding call fails (a broken checker must never block a translation)."""
    a, b = split_sentences(src), split_sentences(out)
    if len(a) < 2 or sum(size(s) for s in a) < 40:
        return []
    if not b:
        return [s for s in a if size(s) >= _MIN_CHARS]
    pairs = [b[i] + ' ' + b[i + 1] for i in range(len(b) - 1)]
    try:
        vecs = await embed(a + b + pairs)
    except Exception:
        logger.warning('Omission check skipped: embedding failed', exc_info=True)
        return []
    if len(vecs) != len(a) + len(b) + len(pairs):
        return []
    va, vb, vp = vecs[:len(a)], vecs[len(a):len(a) + len(b)], vecs[len(a) + len(b):]
    return omitted_sentences(a, va, vb, vp)
