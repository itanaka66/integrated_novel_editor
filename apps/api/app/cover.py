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
import json
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


def new_job(pid: int, provider: str, prompt: str, style: str = '', custom_style: str = '') -> dict:
    job = {'id': next(_ids), 'project_id': pid, 'provider': provider, 'prompt': prompt, 'status': 'queued',
           'style': style, 'custom_style': custom_style, 'filename': None, 'last_message': 'キューに追加しました'}
    jobs[job['id']] = job
    return job


# ---- settings file (hot-reloaded) ---------------------------------------
#
# Image models and generation settings live in a JSON file
# (settings.cover_config_path), not in code. It is re-read whenever its
# modification time changes, so editing it takes effect on the next request
# without restarting. A missing file is created from DEFAULT_CONFIG so there
# is always something to edit; a broken one is reported on first load, and
# once a good copy has been read, later breakage keeps using that copy.

DEFAULT_CONFIG: dict = {
    'default_style': 'anime',
    'comfyui': {
        'checkpoint': '',  # blank = COMFYUI_CHECKPOINT, else the first installed one
        'width': 832, 'height': 1216,  # portrait ~2:3; 832x1216 is an SDXL-native bucket
        'steps': 28, 'cfg': 6.5, 'sampler_name': 'euler', 'scheduler': 'normal',
        'negative': ('text, letters, typography, title, watermark, signature, logo, border, frame, '
                     'low quality, blurry, deformed, extra fingers, cropped'),
    },
    'higgsfield': {'model': '', 'resolution': '2K', 'aspect_ratio': '2:3'},  # blank model = HIGGSFIELD_MODEL
    # Per-style overrides: any key under "comfyui"/"higgsfield" in a style
    # replaces the base value above for that style ("negative_extra" is added
    # to the negative prompt instead). "prompt_style" steers the generated
    # prompt; "prompt_suffix" is appended to the prompt sent to the image model.
    'styles': {
        'anime': {'label': 'アニメ風',
                  'prompt_style': 'Japanese anime / light-novel cover illustration, clean line art, vibrant cel shading, expressive characters',
                  'prompt_suffix': 'anime style, masterpiece, best quality',
                  'comfyui': {'negative_extra': 'photorealistic, photo, 3d render'}, 'higgsfield': {}},
        'gekiga': {'label': '劇画風',
                   'prompt_style': 'gekiga / dramatic Japanese manga illustration, bold ink lines, heavy hatching and shadow, gritty realistic anatomy',
                   'prompt_suffix': 'gekiga, dramatic ink illustration, high contrast',
                   'comfyui': {'negative_extra': 'cute, chibi, pastel, photorealistic'}, 'higgsfield': {}},
        'photo': {'label': '実写風',
                  'prompt_style': 'photorealistic cinematic photograph, natural lighting, real people and locations, shallow depth of field',
                  'prompt_suffix': 'photorealistic, 35mm film, ultra detailed',
                  'comfyui': {'negative_extra': 'anime, cartoon, illustration, painting'}, 'higgsfield': {}},
        'other': {'label': 'その他', 'prompt_style': '', 'prompt_suffix': '',
                  'comfyui': {}, 'higgsfield': {}},
    },
}

_config_cache: dict = {'path': None, 'mtime': None, 'data': None}


def config_path() -> Path:
    return Path(settings.cover_config_path)


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding='utf-8')
    mtime = p.stat().st_mtime_ns
    c = _config_cache
    if c['path'] == str(p) and c['mtime'] == mtime and c['data'] is not None:
        return c['data']
    try:
        data = _merge(DEFAULT_CONFIG, json.loads(p.read_text(encoding='utf-8')))
    except (ValueError, OSError) as ex:
        if c['data'] is not None and c['path'] == str(p):
            logger.warning('Cover config %s is invalid (%s); keeping the previous version', p, ex)
            return c['data']
        raise CoverError(f'表紙の設定ファイル {p} を読み込めません: {ex}')
    c.update(path=str(p), mtime=mtime, data=data)
    return data


def list_styles() -> dict:
    cfg = load_config()
    return {'default': cfg.get('default_style', 'anime'),
            'styles': [{'key': k, 'label': v.get('label', k)} for k, v in cfg['styles'].items()]}


def style_settings(style: str, custom: str = '') -> dict:
    """Everything one generation needs, resolved from the freshly read config:
    the prompt direction plus ComfyUI / Higgsfield settings for this style."""
    cfg = load_config()
    key = style if style in cfg['styles'] else cfg.get('default_style', 'anime')
    st = cfg['styles'].get(key, {})
    over = dict(st.get('comfyui') or {})
    extra = over.pop('negative_extra', '')
    comfy = _merge(cfg['comfyui'], over)
    comfy['negative'] = ', '.join(x for x in (comfy.get('negative', ''), extra) if x)
    hf = _merge(cfg['higgsfield'], st.get('higgsfield') or {})
    direction = (st.get('prompt_style') or '').strip()
    if key == 'other' and custom.strip():
        direction = custom.strip()
    return {'style': key, 'label': st.get('label', key), 'direction': direction,
            'suffix': (st.get('prompt_suffix') or '').strip(), 'comfyui': comfy, 'higgsfield': hf}


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


def fallback_prompt(project, direction: str = '') -> str:
    base = (project.description or project.genre or project.name or 'a story').strip()
    lead = f'{direction}, ' if direction else ''
    return (f'{lead}book cover illustration, {project.genre or "fantasy"}, {base[:200]}, cinematic composition, '
            'dramatic lighting, highly detailed, vertical poster, no text')


async def build_prompt(project, episodes, characters, style: str = '', custom_style: str = '') -> str:
    direction = style_settings(style, custom_style)['direction']
    style_line = f'\nArt style to use: {direction}.' if direction else ''
    ask = f'''You are an art director for a published novel. Based on the novel info below, write ONE English text-to-image prompt
for its book-cover illustration: a single striking key scene or symbolic image that captures the story's genre, mood and protagonist.
Requirements: vertical 2:3 composition, painterly/cinematic professional book-cover quality, leave calm space in the upper third for a title,
and absolutely NO text, letters, or typography in the image. Output only the prompt (comma-separated phrases, under 120 words).{style_line}

{_digest_context(project, episodes, characters)}'''
    try:
        t, _ = await generate(ask)
        t = (t or '').strip().strip('"')
        return t or fallback_prompt(project, direction)
    except Exception:
        logger.exception('Cover prompt generation failed; using fallback template')
        return fallback_prompt(project, direction)


# ---- backends ------------------------------------------------------------

def comfy_workflow(prompt: str, checkpoint: str, seed: int, cs: dict) -> dict:
    return {
        '3': {'class_type': 'KSampler', 'inputs': {'seed': seed, 'steps': int(cs['steps']), 'cfg': float(cs['cfg']),
                                                   'sampler_name': cs['sampler_name'], 'scheduler': cs['scheduler'],
                                                   'denoise': 1, 'model': ['4', 0], 'positive': ['6', 0],
                                                   'negative': ['7', 0], 'latent_image': ['5', 0]}},
        '4': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': checkpoint}},
        '5': {'class_type': 'EmptyLatentImage', 'inputs': {'width': int(cs['width']), 'height': int(cs['height']), 'batch_size': 1}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': ['4', 1]}},
        '7': {'class_type': 'CLIPTextEncode', 'inputs': {'text': cs['negative'], 'clip': ['4', 1]}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['3', 0], 'vae': ['4', 2]}},
        '9': {'class_type': 'SaveImage', 'inputs': {'filename_prefix': 'ine_cover', 'images': ['8', 0]}},
    }


def resolve_checkpoint(configured: str, installed: list[str]) -> str:
    """Pick the checkpoint name ComfyUI will accept. ComfyUI validates
    `ckpt_name` against the exact file names in models/checkpoints (extension
    included, e.g. "NoobAI-XL.safetensors"), so a name written without the
    extension or with different case is matched against the installed list
    instead of being sent as-is and rejected."""
    if not installed:
        raise CoverError(
            'ComfyUI にチェックポイントモデルが1つもありません（ComfyUI が認識している models/checkpoints が空です）。'
            'モデルファイル（.safetensors / .ckpt）を ComfyUI の models/checkpoints に置き、'
            'ComfyUI を再起動するか画面の「Refresh」を押してから、もう一度お試しください。')
    if not configured:  # no override: use the first checkpoint ComfyUI has installed
        return installed[0]
    if configured in installed:
        return configured
    key = configured.lower()
    for name in installed:
        stem = name.rsplit('.', 1)[0] if '.' in name else name
        if name.lower() == key or stem.lower() == key:
            return name
    raise CoverError(
        f'COMFYUI_CHECKPOINT="{configured}" は ComfyUI のチェックポイント一覧にありません。'
        f'ファイル名は拡張子を含めて指定してください。利用可能: {", ".join(installed)}')


async def comfyui_image(prompt: str, ss: dict, timeout: float = 600) -> bytes:
    base = settings.comfyui_url.rstrip('/')
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(f'{base}/object_info/CheckpointLoaderSimple')
        r.raise_for_status()
        installed = r.json()['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
        cs = ss['comfyui']
        checkpoint = resolve_checkpoint(cs.get('checkpoint') or settings.comfyui_checkpoint, list(installed))
        if ss['suffix']:
            prompt = f"{prompt}, {ss['suffix']}"
        r = await c.post(f'{base}/prompt', json={'prompt': comfy_workflow(prompt, checkpoint, random.randint(0, 2**32 - 1), cs)})
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


async def higgsfield_image(prompt: str, ss: dict) -> bytes:
    if not settings.higgsfield_key:
        raise CoverError('HIGGSFIELD_KEY が設定されていません（"<api-key>:<api-secret>" 形式）。')
    try:
        import higgsfield_client
    except ImportError:
        raise CoverError('higgsfield-client が未インストールです（pip install higgsfield-client）。')
    import os
    os.environ.setdefault('HF_KEY', settings.higgsfield_key)
    hf = ss['higgsfield']
    if ss['suffix']:
        prompt = f"{prompt}, {ss['suffix']}"
    try:
        result = await higgsfield_client.subscribe_async(
            hf.get('model') or settings.higgsfield_model,
            arguments={'prompt': prompt, 'resolution': hf.get('resolution', '2K'), 'aspect_ratio': hf.get('aspect_ratio', '2:3')})
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
        ss = style_settings(job.get('style', ''), job.get('custom_style', ''))
        data = await fn(job['prompt'], ss)
        name = f"{job['provider']}-{int(time.time())}{image_ext(data)}"
        d = covers_dir(job['project_id'])
        (d / name).write_bytes(data)
        # What produced this image, kept beside it so it can be reproduced or
        # compared later (the files on disk are the source of truth).
        (d / f'{name}.json').write_text(json.dumps({
            'provider': job['provider'], 'style': ss['style'], 'style_label': ss['label'],
            'custom_style': job.get('custom_style', ''), 'prompt': job['prompt'],
            'settings': ss['comfyui'] if job['provider'] == 'comfyui' else ss['higgsfield'],
        }, ensure_ascii=False, indent=2), encoding='utf-8')
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

def _meta(pid: int, name: str) -> dict:
    p = covers_dir(pid) / f'{name}.json'
    try:
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except ValueError:
        return {}


def list_covers(pid: int) -> list[dict]:
    d = covers_dir(pid)
    chosen = selected_name(pid)
    files = sorted((f for f in d.iterdir() if f.suffix.lower() in IMAGE_EXTS and not f.stem == 'cover'),
                   key=lambda f: f.stat().st_mtime, reverse=True)
    out = []
    for f in files:
        m = _meta(pid, f.name)
        out.append({'filename': f.name, 'provider': f.name.split('-')[0], 'selected': f.name == chosen,
                    'style': m.get('style_label') or m.get('style') or '', 'prompt': m.get('prompt') or ''})
    return out


# The prompt and style the user is working on, written on every change so it
# survives leaving the screen, a reload, or a restart.
_STATE_FIELDS = ('prompt', 'style', 'custom_style', 'provider')


def load_state(pid: int) -> dict:
    p = covers_dir(pid) / 'prompt.json'
    try:
        raw = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except ValueError:
        raw = {}
    return {'prompt': raw.get('prompt', ''), 'style': raw.get('style') or list_styles()['default'],
            'custom_style': raw.get('custom_style', ''), 'provider': raw.get('provider') or 'comfyui'}


def save_state(pid: int, **fields) -> dict:
    state = load_state(pid)
    state.update({k: v for k, v in fields.items() if k in _STATE_FIELDS and v is not None})
    (covers_dir(pid) / 'prompt.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    return state


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

