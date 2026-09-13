"""CORS middleware whose allowed-origins list can change at runtime.

Starlette's CORSMiddleware freezes `allow_origins` at app-startup time, so
changing CORS_ORIGINS normally requires editing .env and restarting the
container. This subclass overrides the one method that reads that list
(`is_allowed_origin`) to consult `runtime_config.get_cors_origins()` fresh on
every request instead — letting the Settings screen change it live, the same
way it already does for the Qdrant/Ollama URLs.
"""
from starlette.middleware.cors import CORSMiddleware

from . import runtime_config as rc


class DynamicCORSMiddleware(CORSMiddleware):
    def is_allowed_origin(self, origin: str) -> bool:
        return origin in rc.get_cors_origins()
