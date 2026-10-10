import time

from app import translator


def test_split_chunks_respects_limit_and_keeps_text():
    text = "\n".join(["あ" * 40] * 10)
    chunks = translator.split_chunks(text, limit=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "\n".join(chunks) == text
    assert translator.split_chunks("x" * 250, limit=100) == ["x" * 100, "x" * 100, "x" * 50]


def test_translate_creates_new_project(client, project, monkeypatch, db_session_factory):
    async def fake_generate(prompt, *a, **k):
        return "EN:" + prompt.rsplit("\n\n", 1)[-1], "m"
    monkeypatch.setattr(translator, "generate", fake_generate)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "転移", "content": "少年は目覚めた。"})
    r = client.post(f"/api/v1/projects/{pid}/translate", json={"language": "en"})
    assert r.status_code == 200
    jid = r.json()["id"]
    for _ in range(50):
        j = client.get(f"/api/v1/translate-jobs/{jid}").json()
        if j["status"] in ("completed", "error"):
            break
        time.sleep(0.1)
    assert j["status"] == "completed", j
    assert j["project_id"] != pid and j["progress_percent"] == 100.0
    eps = client.get(f"/api/v1/projects/{j['project_id']}/episodes").json()
    assert client.get(f"/api/v1/projects/{j['project_id']}").json()["language"] == "en"
    assert eps[0]["title"] == "EN:転移" and eps[0]["content"] == "EN:少年は目覚めた。"
    assert client.get(f"/api/v1/projects/{pid}/episodes").json()[0]["content"] == "少年は目覚めた。"


def test_translate_rejects_unknown_language(client, project):
    assert client.post(f"/api/v1/projects/{project['id']}/translate", json={"language": "xx"}).status_code == 400


def test_retranslate_only_fills_missing_or_short_parts(client, project, monkeypatch, db_session_factory):
    calls = []

    async def fake_generate(prompt, *a, **k):
        text = prompt.rsplit("\n\n", 1)[-1]
        calls.append(text)
        return "EN:" + text, "m"
    monkeypatch.setattr(translator, "generate", fake_generate)
    monkeypatch.setattr(translator, "SessionLocal", db_session_factory)
    pid = project["id"]
    long_text = "少年は目覚めた。" * 20
    for n in (1, 2, 3):
        client.post(f"/api/v1/projects/{pid}/episodes", json={"number": n, "title": f"題{n}", "content": long_text})

    def run():
        jid = client.post(f"/api/v1/projects/{pid}/translate", json={"language": "en"}).json()["id"]
        for _ in range(80):
            j = client.get(f"/api/v1/translate-jobs/{jid}").json()
            if j["status"] in ("completed", "error"):
                return j
            time.sleep(0.1)
        return j
    first = run()
    assert first["status"] == "completed"
    dst = first["project_id"]
    eps = {e["number"]: e for e in client.get(f"/api/v1/projects/{dst}/episodes").json()}
    # Episode 2 was cut off, episode 3 was deleted from the translation.
    from app.models import Episode
    with db_session_factory() as db:
        db.get(Episode, eps[2]["id"]).content = "EN:少"
        db.delete(db.get(Episode, eps[3]["id"]))
        db.commit()
    calls.clear()
    second = run()
    assert second["status"] == "completed" and second["project_id"] == dst
    assert not any(c == "題1" or c == long_text and False for c in calls)
    assert "題1" not in calls and "題2" not in calls and "題3" in calls
    after = {e["number"]: e for e in client.get(f"/api/v1/projects/{dst}/episodes").json()}
    assert set(after) == {1, 2, 3} and after[2]["content"] == "EN:" + long_text and after[3]["content"] == "EN:" + long_text
