import base64
import logging
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import settings

logger = logging.getLogger(__name__)

# Paths that must stay reachable without credentials (health checks, API docs).
PUBLIC_PATHS = {"/api/v1/health", "/docs", "/openapi.json", "/redoc"}


def _unauthorized() -> Response:
    return Response(
        status_code=401,
        content='{"detail":"Not authenticated"}',
        media_type="application/json",
        headers={"WWW-Authenticate": "Basic"},
    )


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """Single-user HTTP Basic Auth gate for the whole API.

    This app has no user model; it protects the entire instance with one
    shared admin/password pair configured via ADMIN_USERNAME/ADMIN_PASSWORD.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if not header.startswith("Basic "):
            return _unauthorized()
        try:
            decoded = base64.b64decode(header[6:]).decode("utf-8")
            username, _, password = decoded.partition(":")
        except Exception:
            return _unauthorized()

        user_ok = secrets.compare_digest(username, settings.admin_username)
        pass_ok = secrets.compare_digest(password, settings.admin_password)
        if not (user_ok and pass_ok):
            return _unauthorized()
        return await call_next(request)
