import zipfile
from io import BytesIO


def setup_episode(client, project):
    client.post(
        f"/api/v1/projects/{project['id']}/episodes",
        json={"number": 1, "title": "転移", "summary": "少年が目覚める", "content": "少年は森で目を覚ました。"},
    )


def test_export_txt(client, project):
    setup_episode(client, project)
    r = client.get(f"/api/v1/projects/{project['id']}/export", params={"format": "txt"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "attachment" in r.headers["content-disposition"]
    assert "第1話 転移" in r.text
    assert "少年は森で目を覚ました。" in r.text


def test_export_markdown(client, project):
    setup_episode(client, project)
    r = client.get(f"/api/v1/projects/{project['id']}/export", params={"format": "md"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert f"# {project['name']}" in r.text
    assert "## 第1話 転移" in r.text


def test_export_epub_is_a_valid_zip_with_expected_entries(client, project):
    setup_episode(client, project)
    r = client.get(f"/api/v1/projects/{project['id']}/export", params={"format": "epub"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/epub+zip"

    z = zipfile.ZipFile(BytesIO(r.content))
    names = z.namelist()
    assert "mimetype" in names
    assert "META-INF/container.xml" in names
    assert "OEBPS/content.opf" in names
    assert "OEBPS/ch1.xhtml" in names
    assert z.read("mimetype") == b"application/epub+zip"
    assert "転移" in z.read("OEBPS/ch1.xhtml").decode("utf-8")


def test_export_rejects_unknown_format(client, project):
    r = client.get(f"/api/v1/projects/{project['id']}/export", params={"format": "pdf"})
    assert r.status_code == 400


def test_export_not_found_project(client):
    r = client.get("/api/v1/projects/999999/export")
    assert r.status_code == 404


def test_export_empty_project_does_not_crash(client, project):
    r = client.get(f"/api/v1/projects/{project['id']}/export", params={"format": "epub"})
    assert r.status_code == 200


def test_digest_picks_climax_into_new_project(client, project):
    pid = project["id"]
    for n in range(1, 7):
        client.post(f"/api/v1/projects/{pid}/episodes", json={"number": n, "title": f"話{n}", "content": "あ" * 100})
    client.post(f"/api/v1/projects/{pid}/plots", json={"title": "第一部", "start_episode": 1, "end_episode": 3})
    r = client.post(f"/api/v1/projects/{pid}/digest", json={"ratio": 0.5})
    assert r.status_code == 200
    body = r.json()
    assert body["project"]["id"] != pid
    assert body["source_numbers"] == [1, 3, 6]
    assert body["chars"] == 300 and body["source_chars"] == 600
    eps = client.get(f"/api/v1/projects/{body['project']['id']}/episodes").json()
    assert [e["number"] for e in eps] == [1, 2, 3]
    assert [e["title"] for e in eps] == ["話1", "話3", "話6"]
    assert len(client.get(f"/api/v1/projects/{pid}/episodes").json()) == 6


def test_digest_rejects_empty_project_and_bad_ratio(client, project):
    pid = project["id"]
    assert client.post(f"/api/v1/projects/{pid}/digest", json={}).status_code == 400
    assert client.post(f"/api/v1/projects/{pid}/digest", json={"ratio": 2}).status_code == 400


def test_export_uses_project_language(client, project):
    pid = project["id"]
    client.put(f"/api/v1/projects/{pid}", json={"language": "en"})
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "Awakening", "content": "The boy woke."})
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 2, "title": "Empty"})
    txt = client.get(f"/api/v1/projects/{pid}/export", params={"format": "txt"}).text
    assert "Episode 1: Awakening" in txt and "(No text)" in txt and "第1話" not in txt
    z = zipfile.ZipFile(BytesIO(client.get(f"/api/v1/projects/{pid}/export", params={"format": "epub"}).content))
    assert "<dc:language>en</dc:language>" in z.read("OEBPS/content.opf").decode()
    assert 'lang="en"' in z.read("OEBPS/ch1.xhtml").decode()
    assert "Contents" in z.read("OEBPS/nav.xhtml").decode()


def test_export_defaults_to_japanese(client, project):
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "転移", "content": "本文"})
    z = zipfile.ZipFile(BytesIO(client.get(f"/api/v1/projects/{pid}/export", params={"format": "epub"}).content))
    assert "<dc:language>ja</dc:language>" in z.read("OEBPS/content.opf").decode()


def test_kdp_package_has_epub_cover_and_info_sheets(client, project, monkeypatch, tmp_path):
    import csv
    import io
    import zipfile
    from app import cover
    from app.config import settings
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path / "covers"))
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "一話", "content": "本文です。"})
    client.put(f"/api/v1/projects/{pid}/publishing", json={"title": "題名", "subtitle": "副題", "author": "筆名", "description": "紹介文",
                                                           "keywords": ["SF", "恐竜"], "category": "SF", "adult": False, "age_min": "12", "age_max": ""})
    d = cover.covers_dir(pid)
    (d / "comfyui-1.png").write_bytes(b"\x89PNG\r\n\x1a\nxx")
    (d / "comfyui-1.png.json").write_text('{"provider": "comfyui"}', encoding="utf-8")
    client.put(f"/api/v1/projects/{pid}/cover", json={"filename": "comfyui-1.png"})
    r = client.get(f"/api/v1/projects/{pid}/export", params={"format": "kdp"})
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert sorted(z.namelist()) == ["book.epub", "cover.png", "kdp_info.csv", "kdp_info.md"]
    rows = list(csv.reader(io.StringIO(z.read("kdp_info.csv").decode("utf-8-sig"))))
    info = {k: v for k, v in rows[1:]}
    assert info["本のタイトル"] == "題名" and info["キーワード（最大7つ）"] == "SF / 恐竜" and info["表紙ファイル"] == "cover.png"
    assert "comfyui" in info["AI生成コンテンツ: 画像（下書き）"]
    md = z.read("kdp_info.md").decode("utf-8")
    assert "題名" in md and "紹介文" in md and "本人" in md
