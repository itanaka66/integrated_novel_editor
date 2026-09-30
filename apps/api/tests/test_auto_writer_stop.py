import asyncio
import json

from app.models import AutoWriteJob
from app import auto_writer


class _FakePlan:
    def __init__(self, content):
        self.content = content


class _FakePlanner:
    async def ensure_series(self, db, project_id, premise=''):
        return _FakePlan(json.dumps({'title': 't', 'arcs': []}))

    async def ensure_arc(self, db, project_id, arc_number, premise=''):
        return _FakePlan(json.dumps({'arc_number': arc_number}))

    async def ensure_mini(self, db, project_id, arc_number, mini_number, premise=''):
        return _FakePlan(json.dumps({'mini_arc_number': mini_number}))

    async def ensure_episode(self, db, project_id, n, premise=''):
        return _FakePlan(json.dumps({'title': f'EP{n}', 'summary': ''}))


async def _fake_controller_generate(prompt):
    return json.dumps({'status': 'PASS', 'issues': [], 'constraints': []}), 'controller-model'


async def _fake_build(db, project_id, existing, limit):
    return {}


async def _fake_noop(*a, **kw):
    return None


async def _fake_index(chunks):
    return None


def _patch_common(monkeypatch):
    monkeypatch.setattr(auto_writer, 'PlannerService', _FakePlanner)
    monkeypatch.setattr(auto_writer, 'controller_generate', _fake_controller_generate)
    monkeypatch.setattr(auto_writer, 'build', _fake_build)
    monkeypatch.setattr(auto_writer, 'update_character_states', _fake_noop)
    monkeypatch.setattr(auto_writer, 'check_continuity', _fake_noop)
    monkeypatch.setattr(auto_writer, 'index', _fake_index)


def _make_job(db_session_factory, project_id, start_episode, end_episode):
    db = db_session_factory()
    job = AutoWriteJob(project_id=project_id, start_episode=start_episode, end_episode=end_episode, writer_model='stub-writer')
    db.add(job); db.commit(); db.refresh(job)
    job_id = job.id
    db.close()
    return job_id


def test_stop_during_last_episodes_writer_call_ends_as_stopped_not_completed(client, project, db_session_factory, monkeypatch):
    # Regression test: a stop request arriving while the *last* episode in
    # range is still being written used to be lost entirely — run_job only
    # checked for it once per episode, at the top of the loop, so nothing
    # ever looked again before the loop's normal exit set status to
    # 'completed'. See _check_stopped's docstring in auto_writer.py.
    _patch_common(monkeypatch)
    job_id = _make_job(db_session_factory, project['id'], 1, 2)

    async def fake_generate(prompt, model=None, url=None, timeout=240, options=None):
        if 'EP.2' in prompt:
            # Simulate a concurrent POST /auto-write/{id}/stop request
            # arriving mid-episode, on its own DB session.
            stop_db = db_session_factory()
            j = stop_db.get(AutoWriteJob, job_id)
            j.status = 'stopping'; stop_db.commit(); stop_db.close()
        return '本文', model or 'writer-model'

    monkeypatch.setattr(auto_writer, 'generate', fake_generate)
    monkeypatch.setattr(auto_writer, 'SessionLocal', db_session_factory)

    asyncio.run(auto_writer.run_job(job_id))

    check_db = db_session_factory()
    final = check_db.get(AutoWriteJob, job_id)
    assert final.status == 'stopped'
    check_db.close()


def test_stop_during_an_earlier_episode_takes_effect_before_the_next_one_starts(client, project, db_session_factory, monkeypatch):
    _patch_common(monkeypatch)
    job_id = _make_job(db_session_factory, project['id'], 1, 3)

    async def fake_generate(prompt, model=None, url=None, timeout=240, options=None):
        if 'EP.1' in prompt:
            stop_db = db_session_factory()
            j = stop_db.get(AutoWriteJob, job_id)
            j.status = 'stopping'; stop_db.commit(); stop_db.close()
        return '本文', model or 'writer-model'

    monkeypatch.setattr(auto_writer, 'generate', fake_generate)
    monkeypatch.setattr(auto_writer, 'SessionLocal', db_session_factory)

    asyncio.run(auto_writer.run_job(job_id))

    check_db = db_session_factory()
    final = check_db.get(AutoWriteJob, job_id)
    assert final.status == 'stopped'
    assert final.current_episode == 1
    # The stop was caught at the Controller-final-gate checkpoint, right
    # after EP.1's Writer call returned but before EP.1 itself got saved —
    # so nothing (not even EP.1) should have been written, and EP.2/EP.3
    # must never have started at all.
    from app.models import Episode
    episodes = check_db.query(Episode).filter(Episode.project_id == project['id']).all()
    assert episodes == []
    check_db.close()
