def test_json_backup_contains_project_data(client, project):
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "t", "content": "本文"})
    r = client.get(f"/api/v1/projects/{pid}/export", params={"format": "json"})
    assert r.status_code == 200 and r.json()["tables"]["episodes"][0]["title"] == "t" and r.json()["project"]["id"] == pid


def test_delete_flow(client, project, db_session_factory):
    from app.models import Project, Episode
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "t", "content": "本文"})
    child_id = client.post("/api/v1/projects", json={"name": "child"}).json()["id"]
    with db_session_factory() as db:
        db.get(Project, child_id).source_project_id = pid
        db.commit()
    blocked = client.delete(f"/api/v1/projects/{pid}")
    assert blocked.status_code == 409 and "child" in blocked.json()["detail"]
    assert client.delete(f"/api/v1/projects/{child_id}").status_code == 204
    assert client.delete(f"/api/v1/projects/{pid}").status_code == 204
    assert client.get(f"/api/v1/projects/{pid}").status_code == 404
    with db_session_factory() as db:
        assert db.query(Episode).filter_by(project_id=pid).count() == 0
    assert client.delete(f"/api/v1/projects/{pid}").status_code == 404
