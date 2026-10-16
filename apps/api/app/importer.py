"""Background job that turns an uploaded なろう-format text file into
Project/Episode rows, mirrors each episode to disk, indexes it for RAG,
and runs the same AI analysis a normal save does (character-state
extraction), finishing with one whole-project continuity audit.

Modeled directly on auto_writer.run_job: a plain asyncio task tracked in
`running` (so it isn't garbage-collected mid-flight), progress written to
an ImportJob row the client polls, and its own SessionLocal() since it
outlives any single request.
"""
import asyncio
import logging

from sqlalchemy import select

from .db import SessionLocal
from .models import ImportJob, Project, Episode
from . import narou_import as ni
from . import file_sync
from .llm_queue import set_project
from .revisions import snapshot_revision

logger = logging.getLogger(__name__)
running = {}


def _chunks(e):
    s = e.content or ''
    out = []
    start = 0
    i = 0
    while start < len(s):
        out.append({'id': e.id * 100000 + i, 'project_id': e.project_id, 'episode_id': e.id, 'title': e.title, 'source_type': 'episode', 'text': s[start:start + 1400]})
        i += 1
        start += 1200
    return out


async def _import_episode(db, project, parsed_ep) -> bool:
    """Creates or overwrites one episode. Returns True if it was newly created."""
    existing = db.scalar(select(Episode).where(Episode.project_id == project.id, Episode.number == parsed_ep.number))
    created = existing is None
    if existing:
        if parsed_ep.content and parsed_ep.content != existing.content:
            snapshot_revision(db, existing)
        existing.title = parsed_ep.title or existing.title
        existing.summary = parsed_ep.summary or existing.summary
        existing.chapter = parsed_ep.chapter or existing.chapter
        existing.content = parsed_ep.content or existing.content
        e = existing
    else:
        e = Episode(project_id=project.id, number=parsed_ep.number, title=parsed_ep.title, summary=parsed_ep.summary, chapter=parsed_ep.chapter, content=parsed_ep.content)
        db.add(e)
    db.commit()
    db.refresh(e)
    file_sync.write_episode_file(project, e)

    # Deliberately no AI step here (embedding, character-state extraction,
    # continuity audit): importing only stores the text. Run those from the
    # app when wanted.
    return created


async def run_import_job(job_id: int, text: str) -> None:
    db = SessionLocal()
    job = db.get(ImportJob, job_id)
    if not job:
        db.close()
        return
    try:
        job.status = 'running'
        db.commit()

        parsed = ni.parse(text)
        job.total_episodes = len(parsed.episodes)
        db.commit()

        if job.mode == 'novel':
            project = Project(name=parsed.name or '(無題のインポート作品)', description=parsed.description, genre=parsed.genre)
            db.add(project)
            db.commit()
            db.refresh(project)
            job.project_id = project.id
            db.commit()
        else:
            project = db.get(Project, job.project_id)
            if not project:
                job.status = 'error'
                job.last_message = 'インポート先のプロジェクトが見つかりませんでした。'
                db.commit()
                return
        set_project(project.id)

        for parsed_ep in sorted(parsed.episodes, key=lambda x: x.number):
            job.last_message = f'第{parsed_ep.number}話を取り込み中…'
            db.commit()
            created = await _import_episode(db, project, parsed_ep)
            job.processed_episodes += 1
            if created:
                job.created_episodes += 1
            else:
                job.updated_episodes += 1
            db.commit()

        job.status = 'completed'
        job.last_message = f'{len(parsed.episodes)}話を取り込みました（新規{job.created_episodes}話・更新{job.updated_episodes}話）。'
        db.commit()
    except asyncio.CancelledError:
        job.status = 'cancelled'
        job.last_message = 'キャンセルしました（取り込み済みの話は残っています）'
        db.commit()
        raise
    except Exception as ex:
        logger.exception('Import job %s failed', job_id)
        job.status = 'error'
        job.last_message = f'インポートに失敗しました: {ex}'
        db.commit()
    finally:
        db.close()
        running.pop(job_id, None)
