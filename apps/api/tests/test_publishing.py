def test_publishing_roundtrip_and_validation(client, project):
    pid = project["id"]
    cur = client.get(f"/api/v1/projects/{pid}/publishing").json()
    assert cur["title"] == project["name"] and cur["keywords"] == [] and cur["adult"] is False
    body = {"title": "新タイトル", "subtitle": "副題", "author": "ペンネーム", "description": "紹介文", "keywords": [" SF ", "", "恐竜"],
            "category": "SF", "adult": True, "age_min": "15", "age_max": ""}
    r = client.put(f"/api/v1/projects/{pid}/publishing", json=body)
    assert r.status_code == 200 and r.json()["keywords"] == ["SF", "恐竜"]
    got = client.get(f"/api/v1/projects/{pid}/publishing").json()
    assert got["title"] == "新タイトル" and got["author"] == "ペンネーム" and got["subtitle"] == "副題" and got["adult"] is True and got["age_min"] == "15"
    assert client.get(f"/api/v1/projects/{pid}").json()["name"] == "新タイトル"
    assert client.put(f"/api/v1/projects/{pid}/publishing", json={**body, "keywords": list("abcdefgh")}).status_code == 400
    assert client.put(f"/api/v1/projects/{pid}/publishing", json={**body, "title": " "}).status_code == 400
    assert client.put(f"/api/v1/projects/{pid}/publishing", json={**body, "description": "あ" * 4001}).status_code == 400


def test_publish_targets_edit_and_reset(client):
    assert client.get("/api/v1/publish-targets").json() == {"targets": None}
    ok = {"targets": [{"name": "Site", "postUrl": "https://example.com/post", "caution": " 注意 "}]}
    r = client.put("/api/v1/publish-targets", json=ok)
    assert r.status_code == 200
    got = client.get("/api/v1/publish-targets").json()["targets"]
    assert got[0]["name"] == "Site" and got[0]["caution"] == "注意" and got[0]["helpUrl"] == ""
    assert client.put("/api/v1/publish-targets", json={"targets": [{"name": "x", "postUrl": "javascript:alert(1)"}]}).status_code == 400
    assert client.put("/api/v1/publish-targets", json={"targets": [{"name": " "}]}).status_code == 400
    assert client.put("/api/v1/publish-targets", json={"targets": None}).json() == {"targets": None}
    assert client.get("/api/v1/publish-targets").json() == {"targets": None}
