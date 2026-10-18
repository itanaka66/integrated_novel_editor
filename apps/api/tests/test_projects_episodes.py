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


def test_episode_counts_in_one_query(client, project):
    pid = project["id"]
    for n in (1, 2, 3):
        client.post(f"/api/v1/projects/{pid}/episodes", json={"number": n, "title": f"t{n}", "content": ""})
    empty = client.post("/api/v1/projects", json={"name": "empty"}).json()["id"]
    r = client.get("/api/v1/projects/episode-counts")
    assert r.status_code == 200
    counts = r.json()["counts"]
    assert counts[str(pid)] == 3 and str(empty) not in counts


def _mk(client, pid, n, title):
    return client.post(f"/api/v1/projects/{pid}/episodes", json={"number": n, "title": title, "content": f"本文{n}"}).json()


def _mirror_files(pid):
    from app import file_sync
    from app.models import Project
    root = file_sync.storage_root()
    return sorted(p.name for p in root.rglob("*.md")) if root.exists() else []


def test_swap_two_episodes_exchanges_numbers_and_files(client, project):
    pid = project["id"]
    a, b, c = _mk(client, pid, 1, "一"), _mk(client, pid, 2, "二"), _mk(client, pid, 3, "三")
    before = _mirror_files(pid)
    r = client.post(f"/api/v1/projects/{pid}/episodes/swap", json={"episode_a": a["id"], "episode_b": c["id"]})
    assert r.status_code == 200
    eps = r.json()["episodes"]
    assert [(e["number"], e["title"], e["content"]) for e in eps] == [(1, "三", "本文3"), (2, "二", "本文2"), (3, "一", "本文1")]  # text travels with the episode
    after = _mirror_files(pid)
    assert len(after) == len(before) == 3  # no orphaned files from the old numbers
    assert client.post(f"/api/v1/projects/{pid}/episodes/swap", json={"episode_a": a["id"], "episode_b": a["id"]}).status_code == 400
    assert client.post(f"/api/v1/projects/{pid}/episodes/swap", json={"episode_a": a["id"], "episode_b": 99999}).status_code == 404
    other = client.post("/api/v1/projects", json={"name": "other"}).json()["id"]
    foreign = _mk(client, other, 1, "他")
    assert client.post(f"/api/v1/projects/{pid}/episodes/swap", json={"episode_a": a["id"], "episode_b": foreign["id"]}).status_code == 404  # another work's episode


def test_insert_episode_shifts_later_episodes_and_their_references(client, project):
    pid = project["id"]
    _mk(client, pid, 1, "一"); _mk(client, pid, 2, "二"); _mk(client, pid, 3, "三")
    client.post(f"/api/v1/projects/{pid}/plots", json={"title": "長編", "start_episode": 1, "end_episode": 3})
    client.post(f"/api/v1/projects/{pid}/foreshadowings", json={"title": "伏線", "setup_episode": 2, "payoff_episode": 3})
    client.post(f"/api/v1/projects/{pid}/timeline", json={"episode_number": 3, "title": "出来事"})
    r = client.post(f"/api/v1/projects/{pid}/episodes/insert", json={"after_number": 1, "title": "挿入話"})
    assert r.status_code == 200
    body = r.json()
    assert [(e["number"], e["title"]) for e in body["episodes"]] == [(1, "一"), (2, "挿入話"), (3, "二"), (4, "三")]
    new = next(e for e in body["episodes"] if e["title"] == "挿入話")
    assert new["id"] == body["episode_id"] and new["content"] == ""
    plot = client.get(f"/api/v1/projects/{pid}/plots").json()[0]
    assert (plot["start_episode"], plot["end_episode"]) == (1, 4)  # 1 stays, the end moved with episode 3
    fs = client.get(f"/api/v1/projects/{pid}/foreshadowings").json()[0]
    assert (fs["setup_episode"], fs["payoff_episode"]) == (3, 4)
    assert client.get(f"/api/v1/projects/{pid}/timeline").json()[0]["episode_number"] == 4
    assert len(_mirror_files(pid)) == 4
    top = client.post(f"/api/v1/projects/{pid}/episodes/insert", json={"after_number": 0}).json()["episodes"]
    assert [e["number"] for e in top] == [1, 2, 3, 4, 5] and top[0]["title"] == "第1話" and top[1]["title"] == "一"
