import time
import zipfile
from io import BytesIO

import pytest

from app import cover
from app.config import settings

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


@pytest.fixture(autouse=True)
def covers_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "covers_dir", str(tmp_path / "covers"))
    monkeypatch.setattr(settings, "cover_config_path", str(tmp_path / "cover_config.json"))


def wait(client, jid):
    for _ in range(50):
        j = client.get(f"/api/v1/cover-jobs/{jid}").json()
        if j["status"] in ("completed", "error"):
            return j
        time.sleep(0.1)
    return j


def test_comfy_workflow_wires_prompt_and_checkpoint():
    wf = cover.comfy_workflow("a dragon", "sdxl.safetensors", 7, cover.style_settings("anime")["comfyui"])
    assert wf["6"]["inputs"]["text"] == "a dragon"
    assert wf["4"]["inputs"]["ckpt_name"] == "sdxl.safetensors"
    assert wf["3"]["inputs"]["seed"] == 7
    assert wf["5"]["inputs"]["height"] > wf["5"]["inputs"]["width"]


def test_image_ext_detects_formats_and_rejects_junk():
    assert cover.image_ext(PNG) == ".png"
    assert cover.image_ext(b"\xff\xd8\xff") == ".jpg"
    with pytest.raises(cover.CoverError):
        cover.image_ext(b"<html>")


def test_prompt_uses_llm_and_falls_back(client, project, monkeypatch):
    async def ok(prompt, *a, **k):
        return '"a lone knight, cinematic"', "m"
    monkeypatch.setattr(cover, "generate", ok)
    assert client.post(f"/api/v1/projects/{project['id']}/cover/prompt").json()["prompt"] == "a lone knight, cinematic"

    async def boom(prompt, *a, **k):
        raise RuntimeError("ollama down")
    monkeypatch.setattr(cover, "generate", boom)
    assert "no text" in client.post(f"/api/v1/projects/{project['id']}/cover/prompt").json()["prompt"]


def test_generate_select_and_epub_embeds_cover(client, project, monkeypatch):
    async def fake(prompt, ss):
        return PNG
    monkeypatch.setattr(cover, "comfyui_image", fake)
    pid = project["id"]
    client.post(f"/api/v1/projects/{pid}/episodes", json={"number": 1, "title": "t", "content": "本文"})
    j = wait(client, client.post(f"/api/v1/projects/{pid}/cover/generate", json={"provider": "comfyui", "prompt": "x", "overlay": False}).json()["id"])
    assert j["status"] == "completed" and j["filename"].startswith("comfyui-")

    covers = client.get(f"/api/v1/projects/{pid}/covers").json()
    assert [c["filename"] for c in covers] == [j["filename"]] and not covers[0]["selected"]
    assert client.get(f"/api/v1/projects/{pid}/covers/{j['filename']}").content == PNG

    z = zipfile.ZipFile(BytesIO(client.get(f"/api/v1/projects/{pid}/export", params={"format": "epub"}).content))
    assert "OEBPS/cover.png" not in z.namelist()

    assert client.put(f"/api/v1/projects/{pid}/cover", json={"filename": j["filename"]}).json()[0]["selected"]
    z = zipfile.ZipFile(BytesIO(client.get(f"/api/v1/projects/{pid}/export", params={"format": "epub"}).content))
    assert z.read("OEBPS/cover.png") == PNG
    opf = z.read("OEBPS/content.opf").decode()
    assert 'properties="cover-image"' in opf and '<itemref idref="cover-page"' in opf


def test_provider_errors_surface_in_job(client, project, monkeypatch):
    monkeypatch.setattr(settings, "higgsfield_key", "")
    j = wait(client, client.post(f"/api/v1/projects/{project['id']}/cover/generate", json={"provider": "higgsfield", "prompt": "x"}).json()["id"])
    assert j["status"] == "error" and "HIGGSFIELD_KEY" in j["last_message"]


def test_validation_and_path_safety(client, project):
    pid = project["id"]
    assert client.post(f"/api/v1/projects/{pid}/cover/generate", json={"provider": "x", "prompt": "p"}).status_code == 400
    assert client.post(f"/api/v1/projects/{pid}/cover/generate", json={"provider": "comfyui", "prompt": " "}).status_code == 400
    assert client.get(f"/api/v1/projects/{pid}/covers/..%2Fsecret.png").status_code in (400, 404)
    assert client.put(f"/api/v1/projects/{pid}/cover", json={"filename": "../x.png"}).status_code == 404


def test_resolve_checkpoint_matches_name_without_extension_or_case():
    installed = ["NoobAI-XL.safetensors", "other.ckpt"]
    assert cover.resolve_checkpoint("NoobAI-XL", installed) == "NoobAI-XL.safetensors"
    assert cover.resolve_checkpoint("noobai-xl.SAFETENSORS", installed) == "NoobAI-XL.safetensors"
    assert cover.resolve_checkpoint("other.ckpt", installed) == "other.ckpt"
    assert cover.resolve_checkpoint("", installed) == "NoobAI-XL.safetensors"


def test_resolve_checkpoint_explains_an_empty_checkpoint_list():
    import pytest

    with pytest.raises(cover.CoverError, match="models/checkpoints"):
        cover.resolve_checkpoint("NoobAI-XL", [])


def test_resolve_checkpoint_lists_what_is_available_when_the_name_is_unknown():
    import pytest

    with pytest.raises(cover.CoverError) as ex:
        cover.resolve_checkpoint("missing", ["a.safetensors", "b.ckpt"])
    assert "a.safetensors" in str(ex.value) and "b.ckpt" in str(ex.value)


def _write_config(over):
    import json
    cfg = cover.load_config()
    p = cover.config_path()
    p.write_text(json.dumps(over, ensure_ascii=False), encoding="utf-8")
    import os
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))  # guarantee a visible mtime change
    return cfg


def test_config_file_is_created_with_the_four_styles():
    cfg = cover.load_config()
    assert cover.config_path().exists()
    assert [s["key"] for s in cover.list_styles()["styles"]] == ["anime", "gekiga", "photo", "other"]
    assert [s["label"] for s in cover.list_styles()["styles"]] == ["アニメ風", "劇画風", "実写風", "その他"]
    assert cfg["comfyui"]["width"] == 832


def test_each_style_resolves_its_own_model_and_settings():
    _write_config({"comfyui": {"checkpoint": "base.safetensors"}, "styles": {
        "anime": {"comfyui": {"checkpoint": "anime-xl.safetensors", "steps": 20}},
        "photo": {"comfyui": {"checkpoint": "real.safetensors", "negative_extra": "anime"}},
    }})
    assert cover.style_settings("anime")["comfyui"]["checkpoint"] == "anime-xl.safetensors"
    assert cover.style_settings("anime")["comfyui"]["steps"] == 20
    assert cover.style_settings("photo")["comfyui"]["checkpoint"] == "real.safetensors"
    assert cover.style_settings("photo")["comfyui"]["negative"].endswith(", anime")
    assert cover.style_settings("gekiga")["comfyui"]["checkpoint"] == "base.safetensors"  # falls back to the base


def test_editing_the_config_file_takes_effect_without_a_restart():
    assert cover.style_settings("anime")["comfyui"]["steps"] == 28
    _write_config({"styles": {"anime": {"comfyui": {"steps": 50}}}})
    assert cover.style_settings("anime")["comfyui"]["steps"] == 50
    assert cover.style_settings("gekiga")["comfyui"]["steps"] == 28  # untouched defaults still merged in


def test_a_broken_config_keeps_the_last_good_copy():
    cover.load_config()
    p = cover.config_path()
    p.write_text("{ not json", encoding="utf-8")
    import os
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert cover.style_settings("anime")["comfyui"]["steps"] == 28


def test_other_style_uses_the_users_own_description():
    ss = cover.style_settings("other", "watercolor, soft pastel")
    assert ss["direction"] == "watercolor, soft pastel"
    assert cover.style_settings("anime", "ignored")["direction"] != "ignored"


def test_unknown_style_falls_back_to_the_default():
    assert cover.style_settings("nope")["style"] == "anime"


def test_prompt_request_passes_the_style_to_the_llm_and_is_saved(client, project, monkeypatch):
    seen = {}

    async def fake_generate(prompt, *a, **k):
        seen["ask"] = prompt
        return "a knight", "m"
    monkeypatch.setattr(cover, "generate", fake_generate)
    pid = project["id"]
    r = client.post(f"/api/v1/projects/{pid}/cover/prompt", json={"style": "gekiga"})
    assert r.json()["prompt"] == "a knight"
    assert "gekiga" in seen["ask"]
    state = client.get(f"/api/v1/projects/{pid}/cover/state").json()
    assert state["prompt"] == "a knight" and state["style"] == "gekiga"


def test_prompt_state_survives_and_user_edits_are_saved(client, project):
    pid = project["id"]
    fresh = client.get(f"/api/v1/projects/{pid}/cover/state").json()
    assert fresh["prompt"] == "" and fresh["style"] == "anime" and fresh["provider"] == "comfyui"
    client.put(f"/api/v1/projects/{pid}/cover/state", json={"prompt": "my own words", "style": "other", "custom_style": "ukiyo-e"})
    client.put(f"/api/v1/projects/{pid}/cover/state", json={"provider": "higgsfield"})  # partial update keeps the rest
    s = client.get(f"/api/v1/projects/{pid}/cover/state").json()
    assert s == {"prompt": "my own words", "style": "other", "custom_style": "ukiyo-e", "provider": "higgsfield", "overlay": True}
    assert (cover.covers_dir(pid) / "prompt.json").exists()


def test_generated_image_is_saved_with_its_prompt_and_style(client, project, monkeypatch):
    seen = {}

    async def fake(prompt, ss):
        seen["ss"] = ss
        return PNG
    monkeypatch.setattr(cover, "comfyui_image", fake)
    pid = project["id"]
    j = wait(client, client.post(f"/api/v1/projects/{pid}/cover/generate",
                                 json={"provider": "comfyui", "prompt": "castle", "style": "photo", "overlay": False}).json()["id"])
    assert j["status"] == "completed"
    assert seen["ss"]["style"] == "photo"
    img = client.get(f"/api/v1/projects/{pid}/covers").json()[0]
    assert img["style"] == "実写風" and img["prompt"] == "castle"
    assert (cover.covers_dir(pid) / j["filename"]).exists()
    assert (cover.covers_dir(pid) / f"{j['filename']}.json").exists()
    assert client.get(f"/api/v1/projects/{pid}/covers/{j['filename']}").content == PNG


def test_styles_endpoint(client):
    r = client.get("/api/v1/cover/styles").json()
    assert r["default"] == "anime" and len(r["styles"]) == 4


def test_digest_is_remembered_and_reflects_later_edits(client, project):
    pid = project["id"]
    assert client.get(f"/api/v1/projects/{pid}/digest").json() is None
    for n in range(1, 5):
        client.post(f"/api/v1/projects/{pid}/episodes", json={"number": n, "title": f"t{n}", "content": "本文" * 10})
    made = client.post(f"/api/v1/projects/{pid}/digest", json={"ratio": 0.5}).json()
    again = client.get(f"/api/v1/projects/{pid}/digest").json()
    assert again["project"]["id"] == made["project"]["id"]
    assert again["episode_count"] == made["episode_count"] and again["source_numbers"] == made["source_numbers"]
    # The user edits the digest's text; the remembered digest shows the new size.
    eps = client.get(f"/api/v1/projects/{made['project']['id']}/episodes").json()
    client.put(f"/api/v1/episodes/{eps[0]['id']}", json={"content": "x" * 500})
    assert client.get(f"/api/v1/projects/{pid}/digest").json()["chars"] > made["chars"]


def test_overlay_text_draws_title_and_author(tmp_path):
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (400, 600), (20, 20, 20)).save(buf, 'PNG')
    out, note = cover.overlay_text(buf.getvalue(), 'Test Title', 'Author', cover.DEFAULT_CONFIG['overlay'])
    assert note == ''
    img = Image.open(BytesIO(out)).convert('RGB')
    assert img.size == (400, 600)
    assert any(px != (20, 20, 20) for px in img.crop((0, 0, 400, 120)).getdata())
    assert any(px != (20, 20, 20) for px in img.crop((0, 500, 400, 600)).getdata())


def test_overlay_text_without_cjk_font_keeps_image(monkeypatch):
    from io import BytesIO
    from PIL import Image
    monkeypatch.setattr(cover, 'find_font', lambda configured='': None)
    buf = BytesIO()
    Image.new('RGB', (200, 300), (0, 0, 0)).save(buf, 'PNG')
    out, note = cover.overlay_text(buf.getvalue(), '日本語タイトル', '著者', cover.DEFAULT_CONFIG['overlay'])
    assert out == buf.getvalue() and 'フォント' in note


def test_cover_config_can_be_edited_and_is_used(client):
    cfg = client.get("/api/v1/cover/config").json()
    assert set(cfg["styles"]) == {"anime", "gekiga", "photo", "other"}
    cfg["comfyui"]["steps"] = 40
    cfg["styles"]["gekiga"]["comfyui"] = {"checkpoint": "dark-xl", "width": 640}
    cfg["styles"]["gekiga"]["higgsfield"] = {"model": "hf-x"}
    cfg["styles"]["gekiga"]["prompt_suffix"] = "ink!"
    r = client.put("/api/v1/cover/config", json=cfg)
    assert r.status_code == 200
    ss = cover.style_settings("gekiga")
    assert ss["comfyui"]["steps"] == 40 and ss["comfyui"]["checkpoint"] == "dark-xl" and ss["comfyui"]["width"] == 640
    assert ss["higgsfield"]["model"] == "hf-x" and ss["suffix"] == "ink!"
    assert cover.style_settings("anime")["comfyui"]["checkpoint"] == ""
    bad = client.put("/api/v1/cover/config", json={"comfyui": {"steps": "abc"}})
    assert bad.status_code == 400


def test_comfyui_url_setting_and_connection_test(client, monkeypatch):
    seen = {}

    class FakeResp:
        def __init__(self, data): self._d = data
        def raise_for_status(self): pass
        def json(self): return self._d

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url, **k):
            seen["url"] = url
            if "bad" in url:
                raise OSError("refused")
            return FakeResp({"CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [["NoobAI-XL.safetensors"]]}}}})
    monkeypatch.setattr(cover.httpx, "AsyncClient", FakeClient)
    ok = client.post("/api/v1/cover/test-comfyui", json={"url": "http://good:8188/", "checkpoint": "noobai-xl"}).json()
    assert ok["ok"] and ok["checkpoints"] == ["NoobAI-XL.safetensors"] and seen["url"] == "http://good:8188/object_info/CheckpointLoaderSimple"
    assert not client.post("/api/v1/cover/test-comfyui", json={"url": "http://bad:1"}).json()["ok"]
    assert not client.post("/api/v1/cover/test-comfyui", json={"url": "http://good", "checkpoint": "nope"}).json()["ok"]
    cfg = client.get("/api/v1/cover/config").json()
    cfg["comfyui"]["url"] = "http://saved:8188"
    client.put("/api/v1/cover/config", json=cfg)
    client.post("/api/v1/cover/test-comfyui", json={})
    assert seen["url"].startswith("http://saved:8188/")


def test_author_falls_back_to_login_name_when_unset(client, project, monkeypatch):
    async def fake(prompt, ss):
        return PNG
    monkeypatch.setattr(cover, "comfyui_image", fake)
    pid = project["id"]
    j = wait(client, client.post(f"/api/v1/projects/{pid}/cover/generate", json={"provider": "comfyui", "prompt": "x"}).json()["id"])
    assert j["status"] == "completed"
    assert client.get(f"/api/v1/projects/{pid}/covers").json()[0].get("author", "x") != ""
    assert cover.DEFAULT_CONFIG["overlay"]["title_size"] <= 0.05


def test_delete_cover_removes_files_and_selection(client, project, monkeypatch):
    async def fake(prompt, ss):
        return PNG
    monkeypatch.setattr(cover, "comfyui_image", fake)
    pid = project["id"]
    j = wait(client, client.post(f"/api/v1/projects/{pid}/cover/generate", json={"provider": "comfyui", "prompt": "x"}).json()["id"])
    fn = j["filename"]
    client.put(f"/api/v1/projects/{pid}/cover", json={"filename": fn})
    assert client.delete(f"/api/v1/projects/{pid}/covers/{fn}").json() == []
    d = cover.covers_dir(pid)
    assert not (d / fn).exists() and not (d / f"{fn}.json").exists() and not (d / "raw" / fn).exists()
    assert cover.selected_name(pid) is None
    assert client.delete(f"/api/v1/projects/{pid}/covers/{fn}").status_code == 404
    assert client.delete(f"/api/v1/projects/{pid}/covers/..%2Fx.png").status_code in (400, 404)


def test_split_title_limits_line_length_and_count():
    assert cover.split_title("短い題") == ["短い題"]
    lines = cover.split_title("恐竜文明開拓記 〜大地に咲く炎の記録〜", 12, 4)
    assert 2 <= len(lines) <= 4 and all(len(x) <= 12 for x in lines) and "".join(lines).replace(" ", "") == "恐竜文明開拓記〜大地に咲く炎の記録〜"
    long = "あ" * 30
    assert len(cover.split_title(long, 12, 4)) == 3
    assert all(len(x) <= 12 for x in cover.split_title("い" * 48, 12, 4))
    assert len(cover.split_title("う" * 80, 12, 4)) == 4
    assert not any(x[:1] in "、。！？」" for x in cover.split_title("あいうえおかきくけこさ、しすせそたちつてとなにぬねの", 12, 4))


def test_overlay_long_cjk_title_stays_inside_image():
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (832, 1216), (20, 20, 20)).save(buf, "PNG")
    out, note = cover.overlay_text(buf.getvalue(), "転生したら最強の恐竜使いだった件について〜異世界文明開拓記〜", "著者", cover.DEFAULT_CONFIG["overlay"])
    img = Image.open(BytesIO(out)).convert("RGB")
    edge = [img.getpixel((x, y)) for y in range(0, 400, 5) for x in (0, 1, 2, 829, 830, 831)]
    assert all(p == (20, 20, 20) for p in edge)  # nothing drawn at the left/right edges
