"""Whole-novel translation into a new project (one episode at a time).

The result is a separate project so the original stays untouched. Jobs are
tracked in memory only (like auto_writer's `running` map, but without a DB
table — a translation is cheap to re-run and this avoids a migration); a
server restart simply drops in-flight jobs.
"""
import asyncio
import contextlib
import itertools
import json
import logging
import re

from sqlalchemy import select

from .db import SessionLocal
from .models import Project, Episode, Character, WorldEntity
# Translation uses its own model (Settings > 接続設定; defaults to the Controller's
# server/model, the A770 in the reference setup), never the Writer's, so it does
# not compete with prose generation.
from .ollama import translator_generate as generate
from .ollama import reviewer_generate as review_generate
from .ollama import alignment_embed, pin_translator, translator_count
from .omission import find_omissions
from .config import settings as env_settings
from .continuity import extract_json
from . import file_sync
from .llm_queue import purpose, set_project

logger = logging.getLogger(__name__)

LANGUAGES = {
    'ja': '日本語', 'en': 'English', 'zh-CN': '简体中文', 'ko': '한국어',
    'es': 'Español', 'fr': 'Français', 'de': 'Deutsch', 'pt-BR': 'Português (BR)',
}
# Language names as given to the model, in English for reliable instruction-following.
_PROMPT_LANG = {
    'ja': 'Japanese', 'en': 'English', 'zh-CN': 'Simplified Chinese', 'ko': 'Korean',
    'es': 'Spanish', 'fr': 'French', 'de': 'German', 'pt-BR': 'Brazilian Portuguese',
}
CHUNK_CHARS = 2500
# A translated field shorter than this fraction of the original is treated as
# cut off and translated again. Deliberately low: Japanese/Chinese/Korean are
# much shorter than European languages for the same content.
SHORT_RATIO = 0.25

jobs: dict[int, dict] = {}
running: dict[int, asyncio.Task] = {}
_ids = itertools.count(1)


def _state_file():
    d = file_sync.storage_root()
    d.mkdir(parents=True, exist_ok=True)
    return d / 'translate_jobs.json'


def _persist() -> None:
    """Write the job table to disk (small) so a server restart can pick the
    unfinished jobs up again instead of losing them."""
    try:
        _state_file().write_text(json.dumps({'jobs': list(jobs.values())[-200:], 'all_jobs': list(all_jobs.values())[-50:]}, ensure_ascii=False), encoding='utf-8')
    except OSError:
        logger.warning('Could not save translate job state', exc_info=True)


def resume_unfinished() -> int:
    """Called at startup: reload saved jobs and restart the ones that were still
    queued/running. Re-running is safe — a translation continues the existing
    translated work and only fills in what is missing (see run_translation)."""
    global _ids, _all_ids
    try:
        saved = json.loads(_state_file().read_text(encoding='utf-8')) if _state_file().exists() else {}
    except (OSError, ValueError):
        return 0
    n = 0
    for j in saved.get('jobs', []):
        jobs[j['id']] = j
    for j in saved.get('all_jobs', []):
        all_jobs[j['id']] = j
    _ids = itertools.count(max(jobs, default=0) + 1)
    _all_ids = itertools.count(max(all_jobs, default=0) + 1)
    for j in list(all_jobs.values()):
        if j['status'] in ('queued', 'running'):
            j['last_message'] = 'サーバー再起動後に続きから再開します…'
            running_all = asyncio.get_event_loop().create_task(run_all(j))
            all_running[j['id']] = running_all
            n += 1
    for j in list(jobs.values()):
        if j['status'] in ('queued', 'running') and not _belongs_to_all_job(j):
            j['status'] = 'queued'
            j['last_message'] = 'サーバー再起動後に続きから再開します…'
            running[j['id']] = asyncio.get_event_loop().create_task(run_translation(j))
            n += 1
        elif j['status'] in ('queued', 'running'):
            j['status'] = 'cancelled'  # its all-languages job restarts the language itself
            j['last_message'] = 'サーバー再起動のため中断しました'
    _persist()
    return n


def _belongs_to_all_job(j: dict) -> bool:
    return any(a['status'] in ('queued', 'running') and a['source_project_id'] == j['source_project_id'] for a in all_jobs.values())


all_jobs: dict[int, dict] = {}
all_running: dict[int, asyncio.Task] = {}
_all_ids = itertools.count(1)


def new_all_job(project_id: int, languages: list[str]) -> dict:
    job = {'id': next(_all_ids), 'source_project_id': project_id, 'languages': languages, 'status': 'queued',
           'total_languages': len(languages), 'done_languages': 0, 'failed': [], 'current_language': '', 'project_ids': [],
           'last_message': 'キューに追加しました'}
    all_jobs[job['id']] = job
    _persist()
    return job


async def run_all(job: dict) -> None:
    """Translate into each language in turn (each its own translated work, or the
    existing one topped up). Runs on the server, so it carries on after the user
    logs out; a language that fails does not stop the rest."""
    job['status'] = 'running'
    _persist()
    try:
        for lang in job['languages'][job['done_languages']:]:
            job['current_language'] = LANGUAGES[lang]
            job['last_message'] = f'{LANGUAGES[lang]} に翻訳中…'
            child = new_job(job['source_project_id'], lang)
            await run_translation(child)
            if child['status'] == 'completed':
                if child.get('project_id'):
                    job['project_ids'].append(child['project_id'])
            else:
                job['failed'].append(LANGUAGES[lang])
            job['done_languages'] += 1
            _persist()
        job['status'] = 'completed'
        _persist()
        job['last_message'] = f'{job["total_languages"]}言語の翻訳が終わりました' + (f'（失敗: {"・".join(job["failed"])}）' if job['failed'] else '。')
    except asyncio.CancelledError:
        job['status'] = 'cancelled'
        _persist()
        job['last_message'] = 'キャンセルしました（翻訳済みの分は残っています）'
        raise
    except Exception as ex:
        logger.exception('Translate-all job %s failed', job['id'])
        job['status'] = 'error'
        _persist()
        job['last_message'] = f'全翻訳に失敗しました: {ex}'
    finally:
        all_running.pop(job['id'], None)


def new_job(project_id: int, language: str) -> dict:
    job = {'id': next(_ids), 'source_project_id': project_id, 'project_id': None, 'language': language,
           'status': 'queued', 'total_episodes': 0, 'processed_episodes': 0, 'last_message': 'キューに追加しました'}
    jobs[job['id']] = job
    _persist()
    return job


def split_chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Split on line boundaries into pieces of at most ~limit chars, so a long
    episode fits the model's output budget and paragraph breaks survive."""
    chunks, cur = [], ''
    for line in (text or '').split('\n'):
        while len(line) > limit:  # pathological single line
            if cur:
                chunks.append(cur)
                cur = ''
            chunks.append(line[:limit])
            line = line[limit:]
        if cur and len(cur) + len(line) + 1 > limit:
            chunks.append(cur)
            cur = ''
        cur = f'{cur}\n{line}' if cur else line
    if cur:
        chunks.append(cur)
    return chunks


def is_short(src: str, dst: str) -> bool:
    """True when the translation of `src` is missing or far shorter than it."""
    s, d = len((src or '').strip()), len((dst or '').strip())
    return s > 0 and d < s * SHORT_RATIO


def _prompt(language: str, glossary: str, text: str) -> str:
    return f'''You are a professional literary translator. Translate the following novel text into {_PROMPT_LANG[language]}.
Rules: keep the paragraph/line breaks and dialogue formatting exactly; do not summarize, add, or omit anything; keep the literary tone; render proper nouns consistently{glossary}.
The output must be written entirely in {_PROMPT_LANG[language]}; never return the source text unchanged and never leave source-language sentences untranslated.
Output only the translation, with no preface or notes.

{text}'''


_THINK_BLOCK = re.compile(r'<think>.*?</think>', re.S | re.I)
_FENCE = re.compile(r'^```[\w-]*[ \t]*\n(.*?)\n?```[ \t]*$', re.S)
# A first line that only announces the translation ("Here is the translation:").
_PREFACE = re.compile(
    r"^\W*(?:sure|certainly|of course|okay|ok|here(?:'s|\s+is|\s+are)|below\s+is|the\s+following\s+is|translation|translated(?:\s+text)?)\b[^\n]{0,80}[:：]\s*$"
    r'|^\W*(?:以下(?:が|は|に)|こちらが|翻訳(?:結果|文)?(?:は|です)?)[^\n]{0,40}[:：。]?\s*$', re.I)
# A last paragraph that only comments on the translation (kept conservative so
# real story text is never dropped).
_TRAILER = re.compile(
    r"^[(（\[]?\s*(?:note|notes|translator'?s?\s+note|nb)\s*[:：)）\]]"
    r"|^(?:i\s+hope\s+this|let\s+me\s+know\s+if|feel\s+free\s+to)\b"
    r'|^[(（\[]?\s*(?:訳注|翻訳者注|翻訳注)\s*[:：)）\]]', re.I)


def clean_translation(text: str) -> str:
    """Strip what chat models wrap around a translation regardless of which model
    produced it: <think> reasoning, a code fence around the whole answer, an
    announcing first line ("Here is the translation:") and a closing remark
    ("Note: ..." / "I hope this helps"). Only whole leading/trailing lines that
    match strict patterns are removed, never text inside the translation."""
    t = (text or '').strip()
    if '</think>' in t.lower():
        t = _THINK_BLOCK.sub('', t)
        t = re.sub(r'^.*</think>', '', t, flags=re.S | re.I)  # reasoning whose opening tag was cut off
    t = t.replace('<think>', '').strip()
    m = _FENCE.match(t)
    if m:
        t = m.group(1).strip()
    lines = t.split('\n')
    if len(lines) > 1 and _PREFACE.match(lines[0].strip()):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    paras = '\n'.join(lines).rstrip().split('\n\n')
    while len(paras) > 1 and _TRAILER.match(paras[-1].strip()):
        paras.pop()
    return '\n\n'.join(paras).strip()


_KANA = re.compile(r'[\u3040-\u30ff]')
_HAN = re.compile(r'[\u3400-\u9fff]')
_HANGUL = re.compile(r'[\uac00-\ud7af]')
_LATIN_TARGETS = ('en', 'es', 'fr', 'de', 'pt-BR')


def _ratio(rx, text: str) -> float:
    body = re.sub(r'\s', '', text)
    return len(rx.findall(body)) / len(body) if body else 0.0


def bad_translation(src: str, out: str, language: str) -> str:
    """Why `out` is not a usable translation of `src` into `language` ('' = fine):
    empty/far too short (cut off) or still mostly in the source language. Some
    models answer with the Japanese text unchanged or translate only part of it."""
    s, o = len(src.strip()), len(out.strip())
    if s > 40 and o < s * SHORT_RATIO:
        return 'too short'
    if s <= 40:
        return ''
    kana = _ratio(_KANA, out)
    if language in _LATIN_TARGETS and (kana + _ratio(_HAN, out) + _ratio(_HANGUL, out)) > 0.2:
        return 'untranslated'
    if language == 'ko' and (kana > 0.2 or _ratio(_HANGUL, out) < 0.2):
        return 'untranslated'
    if language == 'zh-CN' and kana > 0.1:
        return 'untranslated'
    if language == 'ja' and kana < 0.05:
        return 'untranslated'
    return ''


def _retry_prompt(language: str, glossary: str, text: str) -> str:
    return (f'IMPORTANT: your previous answer was not a complete {_PROMPT_LANG[language]} translation. '
            f'Translate EVERY sentence of the text below into {_PROMPT_LANG[language]} and output nothing in any other language.\n\n'
            + _prompt(language, glossary, text))


REVIEW_MIN_CHARS = 80  # titles and one-liners are not worth a review call


def _review_prompt(language: str, glossary: str, src: str, out: str) -> str:
    return f'''You are a meticulous bilingual proofreader. Compare the SOURCE text with its {_PROMPT_LANG[language]} TRANSLATION.
Look for: omitted sentences or clauses, parts left untranslated, mistranslations, content that was added, and character/proper names that are rendered inconsistently{glossary}.
Ignore style preferences. Answer with JSON only, no other text:
{{"ok": true}} when the translation is faithful and complete, otherwise
{{"ok": false, "issues": ["short, concrete description of each problem (max 5, in Japanese)"]}}

SOURCE:
{src}

TRANSLATION:
{out}'''


def _fix_prompt(language: str, glossary: str, src: str, out: str, issues: list[str]) -> str:
    listed = '\n'.join(f'- {i}' for i in issues)
    return (f'A reviewer found these problems in a previous {_PROMPT_LANG[language]} translation of the text below:\n{listed}\n\n'
            f'Previous translation (for reference only):\n{out}\n\n'
            'Write a corrected, COMPLETE translation of the whole text that fixes every problem.\n\n' + _prompt(language, glossary, src))


async def review_chunk(src: str, out: str, language: str, glossary: str) -> list[str]:
    """Problems the checker model finds in `out` ([] = fine, or if the check itself
    failed — a broken checker must never block a translation)."""
    try:
        purpose.set(f'翻訳チェック（{LANGUAGES[language]}）')
        text, _ = await review_generate(_review_prompt(language, glossary, src, out))
    except Exception:
        logger.warning('Translation review call failed', exc_info=True)
        return []
    data = extract_json(clean_translation(text))
    if not isinstance(data, dict) or data.get('ok') is not False:
        return []
    return [str(i).strip() for i in (data.get('issues') or []) if str(i).strip()][:5]


async def _translate_chunk(chunk: str, language: str, glossary: str, stats: dict | None) -> str:
    t, _ = await generate(_prompt(language, glossary, chunk), language=language)
    cleaned = clean_translation(t)
    if bad_translation(chunk, cleaned, language):
        # One more try with a firmer prompt; keep whichever answer is better.
        t2, _ = await generate(_retry_prompt(language, glossary, chunk), language=language)
        again = clean_translation(t2)
        if not bad_translation(chunk, again, language) or len(again) > len(cleaned):
            cleaned = again
    if env_settings.translation_omission_check:
        missing = await find_omissions(chunk, cleaned, alignment_embed)
        if missing:
            # Translate again, naming the sentences that were left out; keep it only
            # when it brings back at least one of them without losing quality.
            purpose.set(f'翻訳（{LANGUAGES[language]}）抜け修正')
            t4, _ = await generate(_fix_prompt(language, glossary, chunk, cleaned, [f'次の文が訳されていません: {m}' for m in missing[:5]]), language=language)
            again = clean_translation(t4)
            if again and not bad_translation(chunk, again, language):
                left = await find_omissions(chunk, again, alignment_embed)
                if len(left) < len(missing):
                    cleaned = again
                    if stats is not None:
                        stats['omissions_fixed'] = stats.get('omissions_fixed', 0) + len(missing) - len(left)
    if env_settings.translation_review and len(chunk.strip()) >= REVIEW_MIN_CHARS:
        issues = await review_chunk(chunk, cleaned, language, glossary)
        if stats is not None:
            stats['reviewed'] = stats.get('reviewed', 0) + 1
        if issues:
            # Translate again with the reviewer's findings, keep it unless it is worse.
            purpose.set(f'翻訳（{LANGUAGES[language]}）修正')
            t3, _ = await generate(_fix_prompt(language, glossary, chunk, cleaned, issues), language=language)
            fixed = clean_translation(t3)
            if fixed and not bad_translation(chunk, fixed, language):
                cleaned = fixed
                if stats is not None:
                    stats['fixed'] = stats.get('fixed', 0) + 1
    return cleaned


async def translate_text(text: str, language: str, glossary: str = '', stats: dict | None = None) -> str:
    """Translate a text chunk by chunk. Which LLM is used is decided by
    ollama.translator_generate (the one an episode is pinned to, else the least busy)."""
    if not (text or '').strip():
        return text or ''
    # One chunk after another: inside an episode they all run on the pinned LLM, and
    # translating them in order keeps names and tone consistent.
    parts = [await _translate_chunk(c, language, glossary, stats) for c in split_chunks(text)]
    return '\n'.join(parts)


def _group_width(language: str | None = None) -> int:
    try:
        return max(1, translator_count(language))
    except Exception:  # settings unreadable: fall back to one at a time
        logger.warning('Could not read the translation LLM list', exc_info=True)
        return 1


async def _translate_episode(e, ne, lang: str, glossary: str, job: dict) -> dict:
    """The translated fields of one episode (only the parts that are missing or too
    short when continuing an earlier translation). Touches no database state, so
    several episodes can run at the same time."""
    purpose.set(f"翻訳（{LANGUAGES[lang]}）第{e.number}話")
    cur = lambda name: getattr(ne, name, '') if ne is not None else ''  # noqa: E731
    out: dict = {}
    with _pin(lang):  # the whole episode on one translation LLM
        return await _translate_episode_fields(e, ne, lang, glossary, job, cur, out)


@contextlib.contextmanager
def _pin(lang: str):
    try:
        cm = pin_translator(lang)
        cm.__enter__()
    except Exception:  # settings unreadable: the unpinned path picks per call
        logger.warning('Could not pin a translation LLM', exc_info=True)
        yield
        return
    try:
        yield
    finally:
        cm.__exit__(None, None, None)


async def _translate_episode_fields(e, ne, lang, glossary, job, cur, out) -> dict:
    if e.chapter and not cur('chapter'):
        out['chapter'] = (await translate_text(e.chapter, lang, glossary)).strip() or e.chapter
    if ne is None or is_short(e.title, cur('title')) or not cur('title'):
        out['title'] = (await translate_text(e.title, lang, glossary, stats=job)).strip() or e.title
    if ne is None or is_short(e.summary, cur('summary')):
        out['summary'] = await translate_text(e.summary, lang, glossary, stats=job)
    if ne is None or is_short(e.content, cur('content')):
        out['content'] = await translate_text(e.content, lang, glossary, stats=job)
    return out


_key_locks: dict[tuple, asyncio.Lock] = {}


def active_job_for(source_project_id: int, language: str) -> dict | None:
    """A queued/running single-language translation of this work into this language."""
    for j in jobs.values():
        if j['source_project_id'] == source_project_id and j['language'] == language and j['status'] in ('queued', 'running'):
            task = running.get(j['id'])
            if task is not None and not task.done():  # a leftover entry with no live task must not block new jobs
                return j
    return None


def _lock_for(job: dict) -> asyncio.Lock:
    """One lock per (event loop, work, language): only one job at a time may
    translate a given work into a given language. Two at once (a second click,
    全翻訳 + a single language, a job resumed after a restart next to a new one)
    would each see the episodes as missing, translate them on different LLMs at
    the same time and create the translated episodes twice."""
    key = (id(asyncio.get_running_loop()), job['source_project_id'], job['language'])
    lock = _key_locks.get(key)
    if lock is None:
        _key_locks[key] = lock = asyncio.Lock()
    return lock


async def run_translation(job: dict) -> None:
    db = SessionLocal()
    lock = _lock_for(job)
    held = False
    try:
        if lock.locked():
            job['last_message'] = '同じ作品・同じ言語の別の翻訳が終わるのを待っています…'
            _persist()
        await lock.acquire()
        held = True
        # Whatever the job that held the lock translated is now in the database, so
        # the resume logic below only does what is still missing or too short.
        job['status'] = 'running'
        _persist()
        set_project(job['source_project_id'])
        purpose.set(f"翻訳（{LANGUAGES[job['language']]}）")
        src = db.get(Project, job['source_project_id'])
        lang = job['language']
        eps = db.scalars(select(Episode).where(Episode.project_id == src.id).order_by(Episode.number)).all()
        chars = db.scalars(select(Character).where(Character.project_id == src.id)).all()
        worlds = db.scalars(select(WorldEntity).where(WorldEntity.project_id == src.id)).all()
        job['total_episodes'] = len(eps)
        glossary = ''
        if chars:
            glossary = '. Character names: ' + ', '.join(c.name for c in chars)

        # An earlier translation of this work into the same language is continued
        # rather than duplicated: only what is missing or far too short is
        # translated again.
        dst = db.scalars(select(Project).where(Project.source_project_id == src.id, Project.language == lang,
                                Project.language != src.language)
                         .order_by(Project.id.desc())).first()
        resume = dst is not None
        if not resume:
            job['last_message'] = 'タイトルを翻訳中…'
            name = (await translate_text(src.name, lang, glossary, stats=job)).strip() or src.name
            desc = await translate_text(src.description, lang, glossary, stats=job)
            dst = Project(name=f'{name} [{LANGUAGES[lang]}]', description=desc, genre=src.genre, rules=src.rules,
                          episode_goal=src.episode_goal, style_guide='', language=lang, source_project_id=src.id)
            db.add(dst)
            db.flush()
        have_c = {c.name for c in db.scalars(select(Character).where(Character.project_id == dst.id)).all()}
        for c in chars:
            if c.name not in have_c:
                db.add(Character(project_id=dst.id, name=c.name, role=c.role, personality=c.personality, speech_style=c.speech_style,
                                 goal=c.goal, status=c.status, description=c.description))
        have_w = {w.name for w in db.scalars(select(WorldEntity).where(WorldEntity.project_id == dst.id)).all()}
        for w in worlds:
            if w.name not in have_w:
                db.add(WorldEntity(project_id=dst.id, name=w.name, entity_type=w.entity_type, description=w.description,
                                   rules=w.rules, location=w.location, era=w.era))
        db.commit()
        db.refresh(dst)
        job['project_id'] = dst.id

        existing = {x.number: x for x in db.scalars(select(Episode).where(Episode.project_id == dst.id)).all()}
        done = skipped = 0
        work = []
        for e in eps:
            ne = existing.get(e.number)
            if ne is not None and not any(is_short(a, b) for a, b in ((e.title, ne.title), (e.summary, ne.summary), (e.content, ne.content))):
                skipped += 1
                job['processed_episodes'] += 1
                _persist()
                continue
            work.append((e, ne))
        # As many episodes at once as there are translation LLMs (1 = one by one).
        width = _group_width(lang)
        for i in range(0, len(work), width):
            group = work[i:i + width]
            nums = '・'.join(str(e.number) for e, _ in group)
            job['last_message'] = f'第{nums}話を翻訳中…'
            _persist()
            results = await asyncio.gather(*(_translate_episode(e, ne, lang, glossary, job) for e, ne in group))
            for (e, ne), fields in zip(group, results):
                if ne is None:
                    ne = Episode(project_id=dst.id, number=e.number, title='', summary='', content='')
                    db.add(ne)
                for k, v in fields.items():
                    setattr(ne, k, v)
                db.commit()
                db.refresh(ne)
                file_sync.write_episode_file(dst, ne)
                done += 1
                job['processed_episodes'] += 1
                _persist()
        job['status'] = 'completed'
        _persist()
        job['last_message'] = (f'{done}話を翻訳しました（訳が揃っている{skipped}話はそのまま）。' if resume
                               else f'{len(eps)}話の翻訳が完了しました。')
        if job.get('omissions_fixed'):
            job['last_message'] += f"（抜けていた{job['omissions_fixed']}文を補いました）"
        if job.get('reviewed'):
            job['last_message'] += f"（AIチェック{job['reviewed']}回、うち{job.get('fixed', 0)}箇所を修正）"
    except asyncio.CancelledError:
        job['status'] = 'cancelled'
        _persist()
        job['last_message'] = 'キャンセルしました（翻訳済みの分は残っています。もう一度実行すると続きから翻訳します）'
        raise
    except Exception as ex:
        logger.exception('Translation job %s failed', job['id'])
        job['status'] = 'error'
        _persist()
        job['last_message'] = f'翻訳に失敗しました: {ex}'
    finally:
        if held:
            lock.release()
        db.close()
        running.pop(job['id'], None)
