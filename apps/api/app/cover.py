"""Book-cover illustration: prompt from the novel's content, image from ComfyUI or Higgsfield.

Flow: `build_prompt` asks the Writer model (falling back to a template) for an
English image prompt describing a cover scene; `run_cover_job` renders it with
the chosen backend and stores the PNG/JPEG under `settings.covers_dir/<pid>/`.
One stored image can be marked as the project's cover (`cover.<ext>`), which
the EPUB export embeds.

Jobs are tracked in memory only (same trade-off as translator.py).
"""
import asyncio
import itertools
import logging
import random
import re
import time
from pathlib import Path

import httpx

from .config import settings
from .ollama import generate

logger = logging.getLogger(__name__)

PROVIDERS = ('comfyui', 'higgsfield')
# Portrait ~2:3, the usual trade-paperback / e-book cover ratio. 832x1216 is
# an SDXL-native bucket close to 2:3.
COMFY_WIDTH, COMFY_HEIGHT = 832, 1216
NEGATIVE = ('text, letters, typography, title, watermark, signature, logo, border, frame, '
            'low quality, blurry, deformed, extra fingers, cropped')
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp')
SAFE_NAME = re.compile(r'^[\w.-]+\.(png|jpg|jpeg|webp)$', re.I)

jobs: dict[int, dict] = {}
running: dict[int, asyncio.Task] = {}
_ids = itertools.count(1)


class CoverError(Exception):
    pass


def covers_dir(pid: int) -> Path:
    d = Path(settings.covers_dir) / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_job(pid: int, provider: str, prompt: str) -> dict:
    job = {'id': next(_ids), 'project_id': pid, 'provider': provider, 'prompt': prompt, 'status': 'queued',
           'filename': None, 'last_message': 'キューに追加しました'}
    jobs[job['id']] = job
    return job


# ---- prompt -------------------------------------------------------------

def _digest_context(project, episodes, characters) -> str:
    lines = [f'Title: {project.name}', f'Genre: {project.genre or "unspecified"}',
             f'Synopsis: {(project.description or "").strip() or "unspecified"}']
    if characters:
        lines.append('Main characters: ' + '; '.join(
            f'{c.name} ({(c.role or "").strip()}) {(c.description or "").strip()[:80]}'.strip() for c in characters[:5]))
    picked = episodes[:6] + episodes[-3:] if len(episodes) > 9 else episodes
    for e in picked:
        text = (e.summary or (e.content or '')[:200]).strip().replace('\n', ' ')
        if text:
            lines.append(f'Episode {e.number} "{e.title}": {text[:200]}')
    return '\n'.join(lines)


def fallback_prompt(project) -> str:
    base = (project.description or project.genre or project.name or 'a story').strip()
    return (f'book cover illustration, {project.genre or "fantasy"}, {base[:200]}, cinematic composition, '
            'dramatic lighting, highly detailed, vertical poster, no text')


async def build_prompt(project, episodes, characters) -> str:
    ask = f'''You are an art director for a published novel. Based on the novel info below, write ONE English text-to-image prompt
for its book-cover illustration: a single striking key scene or symbolic image that captures the story's genre, mood and protagonist.
Requirements: vertical 2:3 composition, painterly/cinematic professional book-cover quality, leave calm space in the upper third for a title,
and absolutely NO text, letters, or typography in the image. Output only the prompt (comma-separated phrases, under 120 words).

{_digest_context(project, episodes, characters)}'''
    try:
        t, _ = await generate(ask)
        t = (t or '').strip().strip('"')
        return t or fallback_prompt(project)
    except Exception:
        logger.exception('Cover prompt generation failed; using fallback template')
        return fallback_prompt(project)


# ---- backends ------------------------------------------------------------

def comfy_workflow(prompt: str, checkpoint: str, seed: int) -> dict:
    return {
        '3': {'class_type': 'KSampler', 'inputs': {'seed': seed, 'steps': 28, 'cfg': 6.5, 'sampler_name': 'euler',
                                                   'scheduler': 'normal', 'denoise': 1, 'model': ['4', 0],
                                                   'positive': ['6', 0], 'negative': ['7', 0], 'latent_image': ['5', 0]}},
        '4': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': checkpoint}},
        '5': {'class_type': 'EmptyLatentImage', 'inputs': {'width': COMFY_WIDTH, 'height': COMFY_HEIGHT, 'batch_size': 1}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': ['4', 1]}},
        '7': {'class_type': 'CLIPTextEncode', 'inputs': {'text': NEGATIVE, 'clip': ['4', 1]}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['3', 0], 'vae': ['4', 2]}},
        '9': {'class_type': 'SaveImage', 'inputs': {'filename_prefix': 'ine_cover', 'images': ['8', 0]}},
    }


async def comfyui_image(prompt: str, timeout: float = 600) -> bytes:
    base = settings.comfyui_url.rstrip('/')
    async with httpx.AsyncClient(timeout=60) as c:
        checkpoint = settings.comfyui_checkpoint
        if not checkpoint:  # no override: use the first checkpoint ComfyUI has installed
            r = await c.get(f'{base}/object_info/CheckpointLoaderSimple')
            r.raise_for_status()
            names = r.json()['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
            if not names:
                raise CoverError('ComfyUI にチェックポイントモデルがありません。')
            checkpoint = names[0]
        r = await c.post(f'{base}/prompt', json={'prompt': comfy_workflow(prompt, checkpoint, random.randint(0, 2**32 - 1))})
        if r.status_code != 200:
            raise CoverError(f'ComfyUI がワークフローを拒否しました: {r.text[:300]}')
        pid = r.json()['prompt_id']
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            h = (await c.get(f'{base}/history/{pid}')).json().get(pid)
            if h:
                for out in h.get('outputs', {}).values():
                    for img in out.get('images', []):
                        v = await c.get(f'{base}/view', params={'filename': img['filename'], 'subfolder': img.get('subfolder', ''),
                                                                 'type': img.get('type', 'output')})
                        v.raise_for_status()
                        return v.content
                raise CoverError('ComfyUI の出力に画像がありませんでした。')
            await asyncio.sleep(2)
    raise CoverError('ComfyUI の生成がタイムアウトしました。')


async def higgsfield_image(prompt: str) -> bytes:
    if not settings.higgsfield_key:
        raise CoverError('HIGGSFIELD_KEY が設定されていません（"<api-key>:<api-secret>" 形式）。')
    try:
        import higgsfield_client
    except ImportError:
        raise CoverError('higgsfield-client が未インストールです（pip install higgsfield-client）。')
    import os
    os.environ.setdefault('HF_KEY', settings.higgsfield_key)
    try:
        result = await higgsfield_client.subscribe_async(
            settings.higgsfield_model,
            arguments={'prompt': prompt, 'resolution': '2K', 'aspect_ratio': '2:3'})
    except Exception as ex:
        raise CoverError(f'Higgsfield での生成に失敗しました: {ex}')
    try:
        url = result['images'][0]['url']
    except (KeyError, IndexError, TypeError):
        raise CoverError('Higgsfield の結果に画像がありませんでした。')
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as c:
        r = await c.get(url)
        r.raise_for_status()
        return r.content


def image_ext(data: bytes) -> str:
    if data.startswith(b'\x89PNG'):
        return '.png'
    if data.startswith(b'\xff\xd8'):
        return '.jpg'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    raise CoverError('画像データを認識できませんでした。')


async def run_cover_job(job: dict) -> None:
    try:
        job['status'] = 'running'
        job['last_message'] = '画像を生成中…（数分かかることがあります）'
        fn = comfyui_image if job['provider'] == 'comfyui' else higgsfield_image
        data = await fn(job['prompt'])
        name = f"{job['provider']}-{int(time.time())}{image_ext(data)}"
        (covers_dir(job['project_id']) / name).write_bytes(data)
        job['filename'] = name
        job['status'] = 'completed'
        job['last_message'] = '表紙画像を生成しました。'
    except CoverError as ex:
        job['status'] = 'error'
        job['last_message'] = str(ex)
    except Exception as ex:
        logger.exception('Cover job %s failed', job['id'])
        job['status'] = 'error'
        job['last_message'] = f'表紙の生成に失敗しました: {ex}'
    finally:
        running.pop(job['id'], None)


# ---- stored files --------------------------------------------------------

def list_covers(pid: int) -> list[dict]:
    d = covers_dir(pid)
    chosen = selected_name(pid)
    files = sorted((f for f in d.iterdir() if f.suffix.lower() in IMAGE_EXTS and not f.stem == 'cover'),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    return [{'filename': f.name, 'provider': f.name.split('-')[0], 'selected': f.name == chosen} for f in files]


def _selected_marker(pid: int) -> Path:
    return covers_dir(pid) / 'selected.txt'


def selected_name(pid: int) -> str | None:
    m = _selected_marker(pid)
    name = m.read_text(encoding='utf-8').strip() if m.exists() else ''
    return name if name and SAFE_NAME.match(name) and (covers_dir(pid) / name).exists() else None


def select_cover(pid: int, filename: str) -> None:
    if not SAFE_NAME.match(filename) or not (covers_dir(pid) / filename).exists():
        raise FileNotFoundError(filename)
    _selected_marker(pid).write_text(filename, encoding='utf-8')


def selected_cover(pid: int) -> tuple[bytes, str] | None:
    """(bytes, extension) of the project's chosen cover, or None."""
    name = selected_name(pid)
    if not name:
        return None
    p = covers_dir(pid) / name
    return p.read_bytes(), p.suffix.lower()

