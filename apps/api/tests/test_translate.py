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
    assert eps[0]["title"] == "EN:転移" and eps[0]["content"] == "EN:少年は目覚めた。"
    assert client.get(f"/api/v1/projects/{pid}/episodes").json()[0]["content"] == "少年は目覚めた。"


def test_translate_rejects_unknown_language(client, project):
    assert client.post(f"/api/v1/projects/{project['id']}/translate", json={"language": "xx"}).status_code == 400
