from editor_common.users import create_user

from app.config import settings
from app.models import User


def test_change_own_password_requires_correct_current_password(client):
    r = client.put(
        "/api/v1/me/password",
        json={"current_password": "wrong", "new_password": "new-pass-123"},
    )
    assert r.status_code == 400


def test_change_own_password_then_login_with_new_password(client):
    r = client.put(
        "/api/v1/me/password",
        json={"current_password": settings.admin_password, "new_password": "new-pass-123"},
    )
    assert r.status_code == 200

    r = client.get("/api/v1/projects")  # old password, still attached to the client
    assert r.status_code == 401

    client.auth = (settings.admin_username, "new-pass-123")
    r = client.get("/api/v1/projects")
    assert r.status_code == 200


def test_forgot_password_always_returns_generic_message(client):
    # Unknown email: no user, no email — must not reveal that via the response.
    r = client.post("/auth/forgot-password", json={"email": "nobody@example.com"})
    assert r.status_code == 200
    generic = r.json()["detail"]

    r2 = client.post("/auth/forgot-password", json={"email": "admin@example.com"})
    assert r2.status_code == 200
    assert r2.json()["detail"] == generic


def test_forgot_password_sends_email_and_reset_link_works(client, db_session_factory, monkeypatch):
    db = db_session_factory()
    db.query(User).filter(User.username == settings.admin_username).update({"email": "admin@example.com"})
    db.commit()
    db.close()

    sent = {}

    def fake_send_email(to, subject, body):
        sent["to"] = to
        sent["subject"] = subject
        sent["body"] = body

    monkeypatch.setattr("app.main.mailer.send_email", fake_send_email)

    r = client.post("/auth/forgot-password", json={"email": "admin@example.com"})
    assert r.status_code == 200
    assert sent["to"] == "admin@example.com"
    assert "reset-password?token=" in sent["body"]

    token = sent["body"].split("token=")[1].split("\n")[0].strip()
    r = client.post("/auth/reset-password", json={"token": token, "new_password": "reset-pass-123"})
    assert r.status_code == 200

    client.auth = (settings.admin_username, "reset-pass-123")
    r = client.get("/api/v1/projects")
    assert r.status_code == 200


def test_reset_password_rejects_invalid_token(client):
    r = client.post("/auth/reset-password", json={"token": "not-a-real-token", "new_password": "x1234567"})
    assert r.status_code == 400


def test_non_admin_cannot_manage_users(client, db_session_factory):
    db = db_session_factory()
    create_user(db, User, "member", "member-pass-123", is_admin=False)
    db.close()

    client.auth = ("member", "member-pass-123")
    r = client.get("/api/v1/users")
    assert r.status_code == 403
    r = client.post("/api/v1/users", json={"username": "someone", "password": "someone-pass-123"})
    assert r.status_code == 403


def test_admin_can_list_and_add_users(client):
    r = client.get("/api/v1/users")
    assert r.status_code == 200
    assert any(u["username"] == settings.admin_username for u in r.json())

    r = client.post("/api/v1/users", json={"username": "newmember", "password": "newmember-pass-123", "is_admin": False})
    assert r.status_code == 200
    assert r.json()["username"] == "newmember"

    # New account actually works.
    client.auth = ("newmember", "newmember-pass-123")
    r = client.get("/api/v1/projects")
    assert r.status_code == 200


def test_admin_cannot_create_duplicate_username(client):
    r = client.post("/api/v1/users", json={"username": settings.admin_username, "password": "whatever-pass-123"})
    assert r.status_code == 409


def test_admin_can_set_email_when_adding_user_and_it_enables_password_reset(client, monkeypatch):
    sent = {}
    monkeypatch.setattr("app.main.mailer.send_email", lambda to, subject, body: sent.update(to=to, body=body))

    r = client.post(
        "/api/v1/users",
        json={"username": "withmail", "password": "withmail-pass-123", "email": "WithMail@Example.com"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "withmail@example.com"

    r = client.post("/auth/forgot-password", json={"email": "withmail@example.com"})
    assert r.status_code == 200
    assert sent.get("to") == "withmail@example.com"


def test_admin_cannot_add_user_with_email_already_taken(client, db_session_factory):
    db = db_session_factory()
    db.query(User).filter(User.username == settings.admin_username).update({"email": "taken@example.com"})
    db.commit()
    db.close()

    r = client.post(
        "/api/v1/users",
        json={"username": "dupemail", "password": "dupemail-pass-123", "email": "taken@example.com"},
    )
    assert r.status_code == 409
