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


def wait(client, jid):
    for _ in range(50):
        j = client.get(f"/api/v1/cover-jobs/{jid}").json()
        if j["status"] in ("completed", "error"):
            return j
        time.sleep(0.1)
    return j


def test_comfy_workflow_wires_prompt_and_checkpoint():
    wf = cover.comfy_workflow("a dragon", "sdxl.safetensors", 7)
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
    async def fake(prompt):
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
