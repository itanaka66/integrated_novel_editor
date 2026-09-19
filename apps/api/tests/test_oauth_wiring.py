from fastapi.testclient import TestClient

from app import main as main_module
from app.config import settings
from app.main import app as fastapi_app


def test_health_reports_no_oauth_providers_by_default(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["oauth_providers"] == []


def test_build_oauth_providers_requires_both_id_and_secret(monkeypatch):
    # An id with no secret (or vice versa) must not produce a half-configured,
    # broken login button — see config.py's comment on this.
    monkeypatch.setattr(settings, "google_client_id", "id-only")
    monkeypatch.setattr(settings, "google_client_secret", "")
    monkeypatch.setattr(settings, "github_client_id", "")
    monkeypatch.setattr(settings, "github_client_secret", "")
    assert main_module._build_oauth_providers() == {}


def test_build_oauth_providers_builds_configured_providers_with_correct_redirect_uris(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "gid")
    monkeypatch.setattr(settings, "google_client_secret", "gsecret")
    monkeypatch.setattr(settings, "github_client_id", "hid")
    monkeypatch.setattr(settings, "github_client_secret", "hsecret")
    monkeypatch.setattr(settings, "oauth_redirect_base_url", "https://api.example.com")

    providers = main_module._build_oauth_providers()

    assert set(providers.keys()) == {"google", "github"}
    # redirect_uri must exactly match what's registered with each provider
    # (see config.py) — a mismatch here silently breaks the whole flow, so
    # it's worth pinning down exactly what gets built.
    assert providers["google"].redirect_uri == "https://api.example.com/auth/callback/google"
    assert providers["github"].redirect_uri == "https://api.example.com/auth/callback/github"


def test_auth_path_prefix_is_exempt_from_the_login_gate(client):
    # No client_id/secret are set in the test environment, so no provider
    # is registered and /auth/login/google is genuinely a 404 — but it must
    # be a 404 (route not found), not a 401 (blocked by the auth gate
    # before routing even runs), proving public_path_prefixes=('/auth',)
    # is actually taking effect. A fresh, credential-less TestClient (the
    # `client` fixture's own client always sends valid Basic Auth) confirms
    # the distinction against a route that's genuinely protected.
    anon = TestClient(fastapi_app)
    r = anon.get("/auth/login/google")
    assert r.status_code == 404
    r = anon.get("/api/v1/projects")
    assert r.status_code == 401
