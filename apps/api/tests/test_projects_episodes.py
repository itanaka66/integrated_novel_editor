def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_project_create_and_list(client, project):
    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    assert any(p["id"] == project["id"] for p in r.json())


def test_project_not_found(client):
    r = client.get("/api/v1/projects/999999")
    assert r.status_code == 404


def test_episode_crud_and_save_warnings(client, project):
    # A character must exist, otherwise update_character_states legitimately
    # has nothing to do and returns early without touching Ollama.
    client.post(f"/api/v1/projects/{project['id']}/characters", json={"name": "田中"})

    r = client.post(
        f"/api/v1/projects/{project['id']}/episodes",
        json={"number": 1, "title": "第一話", "summary": "s", "content": "本文"},
    )
    assert r.status_code == 200
    ep = r.json()

    r = client.get(f"/api/v1/projects/{project['id']}/episodes")
    assert len(r.json()) == 1

    # PUT hits RAG indexing and character-state update, both of which fail in
    # the test environment (no Ollama/Qdrant) — they must be reported as
    # warnings, not swallowed or turned into a 500.
    r = client.put(f"/api/v1/episodes/{ep['id']}", json={"title": "改題"})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "改題"
    assert len(body["warnings"]) == 2

    r = client.delete(f"/api/v1/episodes/{ep['id']}")
    assert r.status_code == 204
    r = client.get(f"/api/v1/projects/{project['id']}/episodes")
    assert r.json() == []


def test_episode_put_not_found(client):
    r = client.put("/api/v1/episodes/999999", json={"title": "x"})
    assert r.status_code == 404


def test_bulk_delete_closes_gaps_in_remaining_episode_numbers(client, project):
    ids = {}
    for n in range(1, 6):
        r = client.post(f"/api/v1/projects/{project['id']}/episodes", json={"number": n, "title": f"第{n}話"})
        ids[n] = r.json()["id"]

    # Delete episodes 2 and 4, leaving 1, 3, 5 — expect them renumbered to 1, 2, 3.
    r = client.post(
        f"/api/v1/projects/{project['id']}/episodes/bulk-delete",
        json={"episode_ids": [ids[2], ids[4]]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["deleted_count"] == 2
    assert body["renumbered_count"] == 2  # old #3 -> #2, old #5 -> #3; old #1 stays #1
    remaining = sorted(body["episodes"], key=lambda e: e["number"])
    assert [e["number"] for e in remaining] == [1, 2, 3]
    assert [e["id"] for e in remaining] == [ids[1], ids[3], ids[5]]

    r = client.get(f"/api/v1/projects/{project['id']}/episodes")
    assert sorted(e["number"] for e in r.json()) == [1, 2, 3]


def test_bulk_delete_with_unknown_ids_is_a_no_op_for_those_ids(client, project):
    r = client.post(f"/api/v1/projects/{project['id']}/episodes", json={"number": 1, "title": "第1話"})
    ep_id = r.json()["id"]

    r = client.post(
        f"/api/v1/projects/{project['id']}/episodes/bulk-delete",
        json={"episode_ids": [999999]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["deleted_count"] == 0
    assert [e["id"] for e in body["episodes"]] == [ep_id]
