"""Whole-novel translation into a new project (one episode at a time).

The result is a separate project so the original stays untouched. Jobs are
tracked in memory only (like auto_writer's `running` map, but without a DB
table — a translation is cheap to re-run and this avoids a migration); a
server restart simply drops in-flight jobs.
"""
import asyncio
import itertools
import logging

from sqlalchemy import select

from .db import SessionLocal
from .models import Project, Episode, Character, WorldEntity
from .ollama import generate
from . import file_sync

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


def new_job(project_id: int, language: str) -> dict:
    job = {'id': next(_ids), 'source_project_id': project_id, 'project_id': None, 'language': language,
           'status': 'queued', 'total_episodes': 0, 'processed_episodes': 0, 'last_message': 'キューに追加しました'}
    jobs[job['id']] = job
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
Output only the translation, with no preface or notes.

{text}'''


async def translate_text(text: str, language: str, glossary: str = '') -> str:
    if not (text or '').strip():
        return text or ''
    out = []
    for chunk in split_chunks(text):
        t, _ = await generate(_prompt(language, glossary, chunk))
        out.append(t.strip())
    return '\n'.join(out)


async def run_translation(job: dict) -> None:
    db = SessionLocal()
    try:
        job['status'] = 'running'
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
        dst = db.scalars(select(Project).where(Project.source_project_id == src.id, Project.language == lang)
                         .order_by(Project.id.desc())).first()
        resume = dst is not None
        if not resume:
            job['last_message'] = 'タイトルを翻訳中…'
            name = (await translate_text(src.name, lang, glossary)).strip() or src.name
            desc = await translate_text(src.description, lang, glossary)
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
        for e in eps:
            ne = existing.get(e.number)
            if ne is None:
                job['last_message'] = f'第{e.number}話を翻訳中…'
                ne = Episode(project_id=dst.id, number=e.number, title='', summary='', content='')
                db.add(ne)
            elif not any(is_short(a, b) for a, b in ((e.title, ne.title), (e.summary, ne.summary), (e.content, ne.content))):
                skipped += 1
                job['processed_episodes'] += 1
                continue
            else:
                job['last_message'] = f'第{e.number}話の不足分を翻訳中…'
            # Translate only the parts that are missing or too short.
            if is_short(e.title, ne.title) or not ne.title:
                ne.title = (await translate_text(e.title, lang, glossary)).strip() or e.title
            if is_short(e.summary, ne.summary):
                ne.summary = await translate_text(e.summary, lang, glossary)
            if is_short(e.content, ne.content):
                ne.content = await translate_text(e.content, lang, glossary)
            db.commit()
            db.refresh(ne)
            file_sync.write_episode_file(dst, ne)
            done += 1
            job['processed_episodes'] += 1
        job['status'] = 'completed'
        job['last_message'] = (f'{done}話を翻訳しました（訳が揃っている{skipped}話はそのまま）。' if resume
                               else f'{len(eps)}話の翻訳が完了しました。')
    except Exception as ex:
        logger.exception('Translation job %s failed', job['id'])
        job['status'] = 'error'
        job['last_message'] = f'翻訳に失敗しました: {ex}'
    finally:
        db.close()
        running.pop(job['id'], None)
