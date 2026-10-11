import json

from app import ai_entities


def test_ai_entities_adds_new_rows_and_skips_duplicates(client, project, monkeypatch):
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/characters", json={"name": "アキラ"})
    reply = [{"name": "アキラ", "role": "dup"}, {"name": "ミオ", "role": "相棒", "status": "alive"},
             {"name": "ミオ", "role": "重複"}, {"name": "ゴウ", "status": "bogus"}, {"role": "名前なし"}]

    async def fake(prompt, *a, **k):
        assert "アキラ" in prompt  # existing names are passed so the AI avoids them
        return "ここに結果:\n" + json.dumps(reply, ensure_ascii=False), "m"
    monkeypatch.setattr(ai_entities, "generate", fake)
    r = client.post(f"/api/v1/projects/{pid}/ai-entities", json={"kind": "characters"})
    assert r.status_code == 200 and r.json()["created"] == 2
    names = sorted(c["name"] for c in client.get(f"/api/v1/projects/{pid}/characters").json())
    assert names == ["アキラ", "ゴウ", "ミオ"]
    assert client.post(f"/api/v1/projects/{pid}/ai-entities", json={"kind": "nope"}).status_code == 400


def test_ai_entities_glossary_and_timeline(client, project, monkeypatch):
    pid = project["id"]
    seq = iter([[{"name": "魔導炉", "description": "d", "location": "技術"}],
                [{"episode_number": "3", "title": "出発"}, {"episode_number": 3, "title": "出発"}]])

    async def fake(prompt, *a, **k):
        return json.dumps(next(seq), ensure_ascii=False), "m"
    monkeypatch.setattr(ai_entities, "generate", fake)
    assert client.post(f"/api/v1/projects/{pid}/ai-entities", json={"kind": "glossary"}).json()["created"] == 1
    w = client.get(f"/api/v1/projects/{pid}/world").json()
    assert w[0]["entity_type"] == "glossary"
    assert client.post(f"/api/v1/projects/{pid}/ai-entities", json={"kind": "timeline"}).json()["created"] == 1
