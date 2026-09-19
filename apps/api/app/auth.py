from editor_common.auth import MAX_FAILURES, make_auth_middleware, make_session_verifier  # noqa: F401 (MAX_FAILURES re-exported for tests)
from editor_common.users import authenticate_user

from .config import settings
from .db import SessionLocal
from .models import User

# A module-level indirection (rather than calling SessionLocal directly)
# so tests can point authentication at their isolated in-memory database —
# app.db.get_db is overridden per-request via FastAPI's dependency_overrides,
# but this middleware runs outside that dependency graph.
_session_factory = SessionLocal


def _authenticate(username: str, password: str) -> bool:
    db = _session_factory()
    try:
        return authenticate_user(db, User, username, password) is not None
    finally:
        db.close()


def _current_session_factory():
    # A separate indirection from _authenticate's own inline call, so both
    # read the (possibly test-monkeypatched) module-level _session_factory
    # fresh on every call rather than capturing whatever it was bound to
    # when make_session_verifier() ran at import time.
    return _session_factory()


# Accepts either a signed session cookie (set by editor_common.oauth's
# Google/GitHub login routes — see main.py's register_oauth_routes call) or
# HTTP Basic credentials, in that order — see make_auth_middleware's
# docstring. /auth/... itself must stay reachable without either, since
# that's the login flow.
AuthMiddleware = make_auth_middleware(
    authenticate_basic=_authenticate,
    verify_session=make_session_verifier(settings.session_secret, _current_session_factory, User),
    public_path_prefixes=('/auth',),
)
