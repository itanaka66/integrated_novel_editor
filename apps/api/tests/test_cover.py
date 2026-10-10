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
    j = wait(client, client.post(f"/api/v1/projects/{pid}/cover/generate", json={"provider": "comfyui", "prompt": "x"}).json()["id"])
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
    assert s == {"prompt": "my own words", "style": "other", "custom_style": "ukiyo-e", "provider": "higgsfield"}
    assert (cover.covers_dir(pid) / "prompt.json").exists()


def test_generated_image_is_saved_with_its_prompt_and_style(client, project, monkeypatch):
    seen = {}

    async def fake(prompt, ss):
        seen["ss"] = ss
        return PNG
    monkeypatch.setattr(cover, "comfyui_image", fake)
    pid = project["id"]
    j = wait(client, client.post(f"/api/v1/projects/{pid}/cover/generate",
                                 json={"provider": "comfyui", "prompt": "castle", "style": "photo"}).json()["id"])
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
