from app.config import settings


def test_default_origin_gets_cors_headers(client):
    r = client.get("/api/v1/health", headers={"Origin": settings.cors_origins})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == settings.cors_origins


def test_disallowed_origin_gets_no_cors_headers(client):
    r = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_cors_origins_cannot_be_changed_via_the_settings_api(client):
    # CORS_ORIGINS is env/.env-only (see models.RuntimeConfig's docstring) —
    # a client sending it in a PUT must have no effect at all, not even a
    # silent no-op error; SystemSettingsUpdate simply has no such field, so
    # pydantic drops the extra key.
    new_origin = "http://example.com:3000"

    r = client.put("/api/v1/system-settings", json={"cors_origins": new_origin})
    assert r.status_code == 200
    # The response still reports the real (env-derived) value, unaffected.
    assert r.json()["cors_origins"] == settings.cors_origins

    r = client.get("/api/v1/health", headers={"Origin": new_origin})
    assert "access-control-allow-origin" not in r.headers

    # The env-var origin is still the only one that works.
    r = client.get("/api/v1/health", headers={"Origin": settings.cors_origins})
    assert r.headers.get("access-control-allow-origin") == settings.cors_origins


def test_wildcard_cors_origins_allows_any_origin(client, monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "*")

    r = client.get("/api/v1/health", headers={"Origin": "http://anything.example"})
    # The actual Origin is echoed back, not a literal "*" — required since
    # this app always sends Access-Control-Allow-Credentials: true, and the
    # fetch spec forbids combining a literal wildcard origin with credentials.
    assert r.headers.get("access-control-allow-origin") == "http://anything.example"


def test_trailing_slash_in_configured_origin_is_ignored(client, monkeypatch):
    # A trailing slash typed into CORS_ORIGINS is an easy mistake — the
    # browser's Origin header never has one, so it must not cause every
    # request from that origin to be silently rejected.
    monkeypatch.setattr(settings, "cors_origins", "https://example.com/")

    r = client.get("/api/v1/health", headers={"Origin": "https://example.com"})
    assert r.headers.get("access-control-allow-origin") == "https://example.com"


def test_preflight_request_for_allowed_origin_succeeds(client):
    r = client.options(
        "/api/v1/projects",
        headers={
            "Origin": settings.cors_origins,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == settings.cors_origins
