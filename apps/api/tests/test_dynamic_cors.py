from app.config import settings


def test_default_origin_gets_cors_headers(client):
    r = client.get("/api/v1/health", headers={"Origin": settings.cors_origins})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == settings.cors_origins


def test_disallowed_origin_gets_no_cors_headers(client):
    r = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_overriding_cors_origins_takes_effect_without_restart(client):
    new_origin = "http://example.com:3000"

    # Not allowed yet — still on the env-var default.
    r = client.get("/api/v1/health", headers={"Origin": new_origin})
    assert "access-control-allow-origin" not in r.headers

    r = client.put("/api/v1/system-settings", json={"cors_origins": new_origin})
    assert r.status_code == 200

    # Allowed immediately, no app restart between the PUT and this request.
    r = client.get("/api/v1/health", headers={"Origin": new_origin})
    assert r.headers.get("access-control-allow-origin") == new_origin

    # The old default origin is no longer allowed once overridden.
    r = client.get("/api/v1/health", headers={"Origin": settings.cors_origins})
    assert "access-control-allow-origin" not in r.headers


def test_wildcard_cors_origins_allows_any_origin(client):
    r = client.put("/api/v1/system-settings", json={"cors_origins": "*"})
    assert r.status_code == 200

    r = client.get("/api/v1/health", headers={"Origin": "http://anything.example"})
    # The actual Origin is echoed back, not a literal "*" — required since
    # this app always sends Access-Control-Allow-Credentials: true, and the
    # fetch spec forbids combining a literal wildcard origin with credentials.
    assert r.headers.get("access-control-allow-origin") == "http://anything.example"


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
