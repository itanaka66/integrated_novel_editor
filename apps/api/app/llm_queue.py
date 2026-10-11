"""A visible queue in front of every Ollama call.

Ollama itself already makes concurrent requests for the *same loaded model*
wait for each other (its default is one request at a time per model), but
that queue is invisible from here: callers just sit inside an HTTP request.
This module puts the waiting on our side instead — a semaphore per
(Ollama server, model) — so it can be listed: which calls are running now,
which are waiting behind them, and what each one is for.

Limit per (server, model) is OLLAMA_MAX_CONCURRENCY (default 1, matching
Ollama's own default; raise it if you've set OLLAMA_NUM_PARALLEL higher,
0 disables queueing but keeps the listing). Different models, or different
servers, never wait on each other — e.g. a Writer generation doesn't block
the embedding model, and Writer/Controller on separate GPUs run in parallel.
"""
import asyncio
import contextvars
import itertools
import re
import time
import weakref
from contextlib import asynccontextmanager
from dataclasses import dataclass

from .config import settings

# What the current request/job is *for* (e.g. "文章を校正しています"); set by
# PurposeMiddleware for HTTP calls and by auto_writer for job steps.
purpose: contextvars.ContextVar[str | None] = contextvars.ContextVar('llm_purpose', default=None)

# Which novel the current request/job works on, so the queue can say "which
# novel is doing what". Set from the URL by PurposeMiddleware, from the request
# body by endpoints that carry a project_id, and by background jobs. An episode
# id is enough when that is all the URL has (resolved to its project on listing).
project_id_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar('llm_project_id', default=None)
episode_id_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar('llm_episode_id', default=None)


def set_project(pid: int | None) -> None:
    project_id_ctx.set(pid)


_KIND_LABELS = {'writer': 'Writer', 'controller': 'Controller', 'embed': '埋め込み'}

# Mirrors apps/web/app/lib/llmActivity.ts's table, for the manual endpoints.
_PATH_PURPOSES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'^/api/v1/ai/generate$'), 'AIによる本文生成'),
    (re.compile(r'^/api/v1/continuity/check$'), '矛盾・連続性の監査'),
    (re.compile(r'^/api/v1/episodes/\d+/character-states$'), '登場人物の状態更新'),
    (re.compile(r'^/api/v1/episodes/\d+/proofread(/stream)?$'), '文章校正'),
    (re.compile(r'^/api/v1/projects/\d+/style-guide/generate$'), 'スタイルガイド生成'),
    (re.compile(r'^/api/v1/projects/\d+/chat$'), 'AIチャット'),
    (re.compile(r'^/api/v1/projects/\d+/cover/prompt$'), '表紙プロンプト作成'),
    (re.compile(r'^/api/v1/projects/\d+/ai-entities$'), '設定のAI追加'),
    (re.compile(r'^/api/v1/rag/search(-all)?$'), '意味検索'),
]


_PROJECT_PATH = re.compile(r'^/api/v1/projects/(\d+)(/|$)')
_EPISODE_PATH = re.compile(r'^/api/v1/episodes/(\d+)(/|$)')


@dataclass
class Entry:
    id: int
    kind: str
    model: str
    url: str
    purpose: str | None
    state: str  # 'waiting' | 'running'
    enqueued_at: float
    started_at: float | None = None
    project_id: int | None = None
    episode_id: int | None = None


_ids = itertools.count(1)
_entries: dict[int, Entry] = {}
# Semaphores belong to one event loop; keyed weakly by loop so a finished
# loop (tests call asyncio.run repeatedly) can't leave a stale one behind.
_semaphores: 'weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, dict]' = weakref.WeakKeyDictionary()


def _semaphore(url: str, model: str) -> asyncio.Semaphore | None:
    limit = settings.ollama_max_concurrency
    if limit <= 0:
        return None
    per_loop = _semaphores.setdefault(asyncio.get_running_loop(), {})
    key = (url, model, limit)
    if key not in per_loop:
        per_loop[key] = asyncio.Semaphore(limit)
    return per_loop[key]


@asynccontextmanager
async def slot(*, kind: str, model: str, url: str):
    """Hold a place in the queue for one Ollama call. Waits (visibly) until
    fewer than the limit are running for this (server, model)."""
    entry = Entry(next(_ids), kind, model, url, purpose.get(), 'waiting', time.time(),
                  project_id=project_id_ctx.get(), episode_id=episode_id_ctx.get())
    _entries[entry.id] = entry
    sem = _semaphore(url, model)
    try:
        if sem is not None:
            await sem.acquire()
        entry.state = 'running'
        entry.started_at = time.time()
        try:
            yield entry
        finally:
            if sem is not None:
                sem.release()
    finally:
        _entries.pop(entry.id, None)


def _project_names(entries: list[Entry]) -> dict[int, str]:
    """Names of the novels the listed calls belong to (one small query)."""
    ids = {e.project_id for e in entries if e.project_id}
    eps = {e.episode_id for e in entries if e.episode_id and not e.project_id}
    if not ids and not eps:
        return {}
    from sqlalchemy import select
    from .db import SessionLocal
    from .models import Episode, Project
    db = SessionLocal()
    try:
        ep_project = {r.id: r.project_id for r in db.execute(select(Episode.id, Episode.project_id).where(Episode.id.in_(eps)))} if eps else {}
        for e in entries:
            if not e.project_id and e.episode_id:
                e.project_id = ep_project.get(e.episode_id)
        ids = {e.project_id for e in entries if e.project_id}
        return {r.id: r.name for r in db.execute(select(Project.id, Project.name).where(Project.id.in_(ids)))} if ids else {}
    except Exception:
        return {}
    finally:
        db.close()


def snapshot() -> list[dict]:
    now = time.time()
    names = _project_names(list(_entries.values()))
    running = sorted((e for e in _entries.values() if e.state == 'running'), key=lambda e: e.started_at or 0)
    waiting = sorted((e for e in _entries.values() if e.state == 'waiting'), key=lambda e: e.enqueued_at)
    out = []
    for position, e in enumerate(running + waiting, start=1):
        out.append({
            'id': e.id,
            'position': position,
            'state': e.state,
            'kind': e.kind,
            'kind_label': _KIND_LABELS.get(e.kind, e.kind),
            'model': e.model,
            'purpose': e.purpose,
            'project_id': e.project_id,
            'project_name': names.get(e.project_id) if e.project_id else None,
            'elapsed_seconds': int(now - (e.started_at if e.state == 'running' and e.started_at else e.enqueued_at)),
        })
    return out


class PurposeMiddleware:
    """Pure-ASGI (not BaseHTTPMiddleware) so the contextvar is set in the
    very task that goes on to run the endpoint, and visible to slot()."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            m = _PROJECT_PATH.match(scope['path'])
            if m:
                project_id_ctx.set(int(m.group(1)))
            elif (m := _EPISODE_PATH.match(scope['path'])):
                episode_id_ctx.set(int(m.group(1)))
        if scope['type'] == 'http' and scope.get('method') == 'POST':
            for pattern, label in _PATH_PURPOSES:
                if pattern.match(scope['path']):
                    purpose.set(label)
                    break
        await self.app(scope, receive, send)
