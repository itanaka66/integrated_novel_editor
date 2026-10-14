import asyncio

from app import importer
from app.models import ImportJob, Project, Episode

NOVEL_EXPORT = """\
【タイトル】
インポート作品

【あらすじ】
あらすじ本文。

【ジャンル】
SF

------------------------- エピソード1開始 -------------------------
【エピソードタイトル】
第1話 「開始」

【本文】
一話の本文。
------------------------- エピソード2開始 -------------------------
【エピソードタイトル】
第2話 「継続」

【本文】
二話の本文。
"""

DRAFT_EPISODES = """\
-------------------------第2話 「継続・改」-------------------------
【本文】
上書きされた二話の本文。

-------------------------第3話 「新話」-------------------------
【本文】
新しい三話の本文。
"""


def _stub_ai(monkeypatch):
    # Importing must not run any AI step (embedding, character states,
    # continuity): fail loudly if anything tries to reach the model.
    from app import ollama

    async def boom(*a, **k):
        raise AssertionError("AI must not be called during import")
    monkeypatch.setattr(ollama, "generate", boom)
    assert not hasattr(importer, "index") and not hasattr(importer, "check_continuity") and not hasattr(importer, "update_character_states")


def test_novel_import_creates_project_and_episodes(db_session_factory, monkeypatch):
    _stub_ai(monkeypatch)
    monkeypatch.setattr(importer, "SessionLocal", db_session_factory)

    db = db_session_factory()
    job = ImportJob(mode="novel", source_filename="novel.txt", status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    asyncio.run(importer.run_import_job(job_id, NOVEL_EXPORT))

    db = db_session_factory()
    job = db.get(ImportJob, job_id)
    assert job.status == "completed"
    assert job.total_episodes == 2
    assert job.created_episodes == 2
    assert job.updated_episodes == 0
    assert job.project_id is not None

    project = db.get(Project, job.project_id)
    assert project.name == "インポート作品"
    assert project.genre == "SF"

    episodes = db.query(Episode).filter(Episode.project_id == project.id).order_by(Episode.number).all()
    assert [e.number for e in episodes] == [1, 2]
    assert episodes[0].title == "開始"
    assert "一話の本文" in episodes[0].content
    db.close()


def test_episodes_import_upserts_into_existing_project(db_session_factory, monkeypatch):
    _stub_ai(monkeypatch)
    monkeypatch.setattr(importer, "SessionLocal", db_session_factory)

    db = db_session_factory()
    project = Project(name="既存作品", description="", genre="")
    db.add(project)
    db.commit()
    db.refresh(project)
    existing = Episode(project_id=project.id, number=2, title="旧タイトル", content="旧本文")
    db.add(existing)
    db.commit()

    job = ImportJob(mode="episodes", project_id=project.id, source_filename="draft.txt", status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    project_id = project.id
    db.close()

    asyncio.run(importer.run_import_job(job_id, DRAFT_EPISODES))

    db = db_session_factory()
    job = db.get(ImportJob, job_id)
    assert job.status == "completed"
    assert job.total_episodes == 2
    assert job.created_episodes == 1  # episode 3 is new
    assert job.updated_episodes == 1  # episode 2 already existed

    episodes = {e.number: e for e in db.query(Episode).filter(Episode.project_id == project_id).all()}
    assert episodes[2].title == "継続・改"
    assert "上書きされた" in episodes[2].content
    assert episodes[3].title == "新話"
    db.close()


def test_episodes_import_snapshots_a_revision_when_overwriting(db_session_factory, monkeypatch):
    _stub_ai(monkeypatch)
    monkeypatch.setattr(importer, "SessionLocal", db_session_factory)

    db = db_session_factory()
    project = Project(name="既存作品2", description="", genre="")
    db.add(project)
    db.commit()
    db.refresh(project)
    existing = Episode(project_id=project.id, number=2, title="旧タイトル", content="旧本文")
    db.add(existing)
    db.commit()
    episode_id = existing.id

    job = ImportJob(mode="episodes", project_id=project.id, source_filename="draft.txt", status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    asyncio.run(importer.run_import_job(job_id, DRAFT_EPISODES))

    from app.models import EpisodeRevision
    db = db_session_factory()
    revisions = db.query(EpisodeRevision).filter(EpisodeRevision.episode_id == episode_id).all()
    assert len(revisions) == 1
    assert revisions[0].content == "旧本文"
    db.close()


def test_import_into_missing_project_errors(db_session_factory, monkeypatch):
    _stub_ai(monkeypatch)
    monkeypatch.setattr(importer, "SessionLocal", db_session_factory)

    db = db_session_factory()
    job = ImportJob(mode="episodes", project_id=999999, source_filename="draft.txt", status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    asyncio.run(importer.run_import_job(job_id, DRAFT_EPISODES))

    db = db_session_factory()
    job = db.get(ImportJob, job_id)
    assert job.status == "error"
    db.close()
