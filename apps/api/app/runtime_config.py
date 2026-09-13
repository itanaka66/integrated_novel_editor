"""Resolves the connection settings actually in effect right now.

Qdrant and both Ollama endpoints (Writer / Controller) can be overridden
live from the 設定 → 接続設定 screen, stored in the single-row
`runtime_config` table. DATABASE_URL is not — see models.RuntimeConfig's
docstring for why. Every AI/vector call in this app is already stateless
(a fresh client per call), so honoring an override here doesn't need a
restart or any connection-pool surgery — it just changes what the next
call constructs its client with.
"""
from dataclasses import dataclass

from .config import settings as env_settings
from .db import SessionLocal
from .models import RuntimeConfig

SINGLETON_ID = 1


@dataclass
class EffectiveConfig:
    qdrant_url: str
    ollama_url: str
    ollama_model: str
    ollama_embed_model: str
    controller_ollama_url: str
    controller_ollama_model: str
    cors_origins: str


def _pick(override: str | None, fallback: str) -> str:
    return override if override else fallback


def get_effective_config(db=None) -> EffectiveConfig:
    """`db`, when given, must be a session bound to the same engine `get_db`
    hands out to request handlers — pass it whenever you have one (e.g. from
    a FastAPI endpoint) so this reads the same database those handlers do.
    Without it (e.g. from ollama.py/rag.py, which aren't request-scoped),
    this opens and closes its own short-lived session against the app's
    configured engine — fine as long as that's the same engine `get_db`
    uses, which it always is outside of tests (tests override `get_db` to
    an isolated in-memory database that this fallback path can't see).
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    try:
        row = db.get(RuntimeConfig, SINGLETON_ID)
    finally:
        if owns_session:
            db.close()
    return EffectiveConfig(
        qdrant_url=_pick(row.qdrant_url if row else None, env_settings.qdrant_url),
        ollama_url=_pick(row.ollama_url if row else None, env_settings.ollama_url),
        ollama_model=_pick(row.ollama_model if row else None, env_settings.ollama_model),
        ollama_embed_model=_pick(row.ollama_embed_model if row else None, env_settings.ollama_embed_model),
        controller_ollama_url=_pick(row.controller_ollama_url if row else None, env_settings.controller_ollama_url),
        controller_ollama_model=_pick(row.controller_ollama_model if row else None, env_settings.controller_ollama_model),
        cors_origins=_pick(row.cors_origins if row else None, env_settings.cors_origins),
    )


# CORSMiddleware (see app/cors.py) checks the allowed-origins list on every
# request, so it reads this in-memory cache rather than hitting the database
# each time — refreshed at app startup and whenever the Settings screen
# changes the CORS_ORIGINS override (system_settings_put in main.py).
_cors_cache: list[str] | None = None


def refresh_cors_cache(db=None) -> list[str]:
    global _cors_cache
    cfg = get_effective_config(db)
    _cors_cache = [o.strip() for o in cfg.cors_origins.split(',') if o.strip()]
    return _cors_cache


def get_cors_origins() -> list[str]:
    if _cors_cache is None:
        return refresh_cors_cache()
    return _cors_cache


def mask_database_url(url: str) -> str:
    """postgresql+psycopg2://user:secret@host:5432/db -> user:***@host:5432/db"""
    if '@' not in url:
        return url
    scheme_and_creds, rest = url.rsplit('@', 1)
    if '://' not in scheme_and_creds:
        return url
    _, creds = scheme_and_creds.split('://', 1)
    user = creds.split(':', 1)[0] if ':' in creds else creds
    return f'{user}:***@{rest}'
