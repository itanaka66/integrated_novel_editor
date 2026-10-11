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


def new_job(pid: int, provider: str, prompt: str, style: str = '', custom_style: str = '',
            overlay: bool = False, title: str = '', author: str = '') -> dict:
    job = {'id': next(_ids), 'project_id': pid, 'provider': provider, 'prompt': prompt, 'status': 'queued',
           'style': style, 'custom_style': custom_style, 'overlay': overlay, 'title': title, 'author': author, 'filename': None, 'last_message': 'キューに追加しました'}
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
        'url': '',  # blank = COMFYUI_URL
        'checkpoint': '',  # blank = COMFYUI_CHECKPOINT, else the first installed one
        'width': 832, 'height': 1216,  # portrait ~2:3; 832x1216 is an SDXL-native bucket
        'steps': 28, 'cfg': 6.5, 'sampler_name': 'euler', 'scheduler': 'normal',
        'negative': ('text, letters, typography, title, watermark, signature, logo, border, frame, '
                     'low quality, blurry, deformed, extra fingers, cropped'),
    },
    'higgsfield': {'model': '', 'resolution': '2K', 'aspect_ratio': '2:3'},  # blank model = HIGGSFIELD_MODEL
    # Title/author lettering drawn onto the finished image (see overlay_text).
    # Sizes are fractions of the image width, positions of its height. "font"
    # blank = the first installed CJK-capable font found; a path pins one.
    'overlay': {
        'font': '',
        'title_size': 0.045, 'author_size': 0.04, 'max_title_lines': 4, 'max_title_chars': 12,
        'text_color': '#ffffff', 'stroke_color': '#101018', 'stroke_ratio': 0.09,
        'title_y': 0.07, 'author_y': 0.95, 'side_margin': 0.07,
    },
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


# ---- settings screen (edit cover_config.json from the UI) -------------------

COMFY_FIELDS = {'url': str, 'checkpoint': str, 'width': int, 'height': int, 'steps': int, 'cfg': float,
                'sampler_name': str, 'scheduler': str, 'negative': str, 'negative_extra': str}
HIGGS_FIELDS = {'model': str, 'resolution': str, 'aspect_ratio': str}
STYLE_TEXT_FIELDS = ('label', 'prompt_style', 'prompt_suffix')


def _clean(src: dict, fields: dict) -> dict:
    out = {}
    for k, typ in fields.items():
        if k not in (src or {}) or src[k] in (None, ''):
            continue  # blank = inherit / use the default
        try:
            out[k] = typ(src[k]) if typ is not str else str(src[k]).strip()
        except (TypeError, ValueError):
            raise CoverError(f'設定値が不正です: {k}={src[k]!r}')
        if typ is not str and out[k] <= 0:
            raise CoverError(f'設定値は正の数で指定してください: {k}')
    return out


def editable_config() -> dict:
    """The part of the config the settings screen edits. Style entries hold only
    their own overrides (blank = inherits the common value), so saving what was
    read does not copy common values into every style."""
    cfg = load_config()
    return {'default_style': cfg.get('default_style', 'anime'), 'comfyui': cfg['comfyui'], 'higgsfield': cfg['higgsfield'],
            'styles': {k: {'label': v.get('label', k), 'prompt_style': v.get('prompt_style', ''), 'prompt_suffix': v.get('prompt_suffix', ''),
                           'comfyui': v.get('comfyui') or {}, 'higgsfield': v.get('higgsfield') or {}} for k, v in cfg['styles'].items()}}


def save_editable_config(data: dict) -> dict:
    """Validate and write the edited settings into cover_config.json, keeping
    any other keys in the file (e.g. overlay). The running app picks the file up
    on the next generation (it is hot-reloaded)."""
    p = config_path()
    try:
        raw = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except (ValueError, OSError):
        raw = {}
    cur = load_config()
    raw['comfyui'] = {**(raw.get('comfyui') or {}), **_clean(data.get('comfyui') or {}, {k: v for k, v in COMFY_FIELDS.items() if k != 'negative_extra'})}
    raw['higgsfield'] = {**(raw.get('higgsfield') or {}), **_clean(data.get('higgsfield') or {}, HIGGS_FIELDS)}
    styles = {}
    for key in cur['styles']:
        sd = (data.get('styles') or {}).get(key) or {}
        entry = {f: str(sd.get(f, '')).strip() for f in STYLE_TEXT_FIELDS}
        entry['label'] = entry['label'] or cur['styles'][key].get('label', key)
        entry['comfyui'] = _clean(sd.get('comfyui') or {}, COMFY_FIELDS)
        entry['higgsfield'] = _clean(sd.get('higgsfield') or {}, HIGGS_FIELDS)
        styles[key] = entry
    raw['styles'] = styles
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    return editable_config()


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


# ---- title / author lettering ----------------------------------------------

_FONT_CANDIDATES = (
    # Windows
    'C:/Windows/Fonts/meiryob.ttc', 'C:/Windows/Fonts/YuGothB.ttc', 'C:/Windows/Fonts/meiryo.ttc', 'C:/Windows/Fonts/msgothic.ttc',
    # macOS
    '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',
    '/Library/Fonts/Arial Unicode.ttf',
    # Linux (fonts-ipafont-gothic is what the Docker image installs)
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf', '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf',
    '/usr/share/fonts/truetype/takao-gothic/TakaoPGothic.ttf', '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
    '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
)
_CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af\uff00-\uffef]')


def find_font(configured: str = '') -> str | None:
    for p in ([configured] if configured else []) + list(_FONT_CANDIDATES):
        if p and Path(p).exists():
            return p
    return None


_BREAK_AFTER = set('、。・〜～！？!?」』）】 　')
_NO_START = set('、。・！？!?」』）】ー')


def split_title(text: str, max_chars: int = 12, max_lines: int = 4) -> list[str]:
    """Split a CJK title into balanced lines of at most `max_chars` characters
    (up to `max_lines` lines), breaking after punctuation/spaces when one is
    close to the ideal position. A title too long for max_lines x max_chars
    still gets max_lines lines (the caller shrinks the font to fit)."""
    text = ' '.join((text or '').split())
    if len(text) <= max_chars:
        return [text] if text else []
    n = min(max_lines, -(-len(text) // max_chars))
    lines, pos = [], 0
    for k in range(n):
        left = n - k
        if left == 1:
            lines.append(text[pos:].strip())
            break
        ideal = -(-(len(text) - pos) // left)
        best = ideal
        for off in (0, -1, 1, -2, 2):
            p = ideal + off
            if p < 1 or pos + p >= len(text) or text[pos + p] in _NO_START and text[pos + p - 1] not in _BREAK_AFTER:
                continue
            if p > max_chars or len(text) - (pos + p) > (left - 1) * max(max_chars, ideal):
                continue
            if text[pos + p - 1] in _BREAK_AFTER:
                best = p
                break
        lines.append(text[pos:pos + best].strip())
        pos += best
    return [ln for ln in lines if ln]


def _wrap(draw, text: str, font, max_w: float) -> list[str]:
    words = text.split(' ') if ' ' in text.strip() else list(text)
    sep = ' ' if ' ' in text.strip() else ''
    lines, cur = [], ''
    for w in words:
        trial = f'{cur}{sep}{w}' if cur else w
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def overlay_text(data: bytes, title: str, author: str, cfg: dict) -> tuple[bytes, str]:
    """Draw the title near the top (where the prompt asks the model to leave
    calm space) and the author at the bottom. Returns (image bytes, note);
    note is empty on success, or says why the lettering was left off so the
    image is still kept rather than lost."""
    try:
        from io import BytesIO
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return data, 'Pillow が未インストールのため、タイトルと著者名を入れられませんでした。'
    title, author = (title or '').strip(), (author or '').strip()
    if not title and not author:
        return data, ''
    ov = cfg
    font_path = find_font(ov.get('font', ''))
    if not font_path:
        if _CJK.search(title + author):
            return data, ('日本語フォントが見つからないため、タイトルと著者名を入れられませんでした。'
                          'cover_config.json の overlay.font にフォントのパスを指定してください。')
        font_path = None
    try:
        img = Image.open(BytesIO(data))
        fmt = img.format or 'PNG'
        img = img.convert('RGBA')
    except Exception:
        return data, '画像として読み込めないため、タイトルと著者名を入れられませんでした。'
    w, h = img.size
    layer = ImageDraw.Draw(img)

    def font_at(size: int):
        return ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default(size)

    def stroke_for(size: int) -> int:
        return max(1, round(size * float(ov['stroke_ratio'])))

    max_w = w * (1 - 2 * float(ov['side_margin']))

    def draw_block(text: str, size: int, y: float, anchor_bottom: bool, max_lines: int, max_chars: int = 0) -> None:
        if not text:
            return
        fixed = split_title(text, max_chars, max_lines) if max_chars and _CJK.search(text) else None
        while True:
            f = font_at(size)
            if fixed is not None:
                lines = fixed
                fits = all(layer.textlength(ln, font=f) <= max_w for ln in lines)
            else:
                lines = _wrap(layer, text, f, max_w)
                fits = len(lines) <= max_lines
            if fits or size <= 14:
                break
            size = int(size * 0.9)
        sw = stroke_for(size)
        line_h = int(size * 1.25)
        block_h = line_h * len(lines)
        top = y - block_h if anchor_bottom else y
        for i, line in enumerate(lines):
            layer.text((w / 2, top + i * line_h), line, font=f, fill=ov['text_color'], anchor='ma',
                       stroke_width=sw, stroke_fill=ov['stroke_color'])

    draw_block(title, round(w * float(ov['title_size'])), h * float(ov['title_y']), False, int(ov['max_title_lines']), int(ov.get('max_title_chars', 12)))
    draw_block(author, round(w * float(ov['author_size'])), h * float(ov['author_y']), True, 1)

    out = BytesIO()
    if fmt.upper() in ('JPEG', 'JPG'):
        img.convert('RGB').save(out, 'JPEG', quality=95)
    elif fmt.upper() == 'WEBP':
        img.save(out, 'WEBP', quality=95)
    else:
        img.save(out, 'PNG')
    return out.getvalue(), ''


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


async def test_comfyui(url: str = '', checkpoint: str = '') -> dict:
    """Connection test for the settings screen: can ComfyUI be reached, which
    checkpoints does it list, and does the configured one resolve."""
    base = (url or load_config()['comfyui'].get('url') or settings.comfyui_url).rstrip('/')
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f'{base}/object_info/CheckpointLoaderSimple')
            r.raise_for_status()
            installed = list(r.json()['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0])
    except Exception as ex:
        return {'ok': False, 'url': base, 'checkpoints': [], 'message': f'{base} に接続できません: {type(ex).__name__}: {ex}'}
    try:
        used = resolve_checkpoint(checkpoint or load_config()['comfyui'].get('checkpoint') or settings.comfyui_checkpoint, installed)
    except CoverError as ex:
        return {'ok': False, 'url': base, 'checkpoints': installed, 'message': str(ex)}
    return {'ok': True, 'url': base, 'checkpoints': installed, 'message': f'接続できました。チェックポイント {len(installed)} 件（使用: {used}）'}


async def comfyui_image(prompt: str, ss: dict, timeout: float = 600) -> bytes:
    cs = ss['comfyui']
    base = (cs.get('url') or settings.comfyui_url).rstrip('/')
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(f'{base}/object_info/CheckpointLoaderSimple')
        r.raise_for_status()
        installed = r.json()['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
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
        note = ''
        if job.get('overlay'):
            # Keep the untouched image too, so the lettering can be redone later.
            (d / 'raw').mkdir(exist_ok=True)
            (d / 'raw' / name).write_bytes(data)
            data, note = await asyncio.to_thread(overlay_text, data, job.get('title', ''), job.get('author', ''), load_config()['overlay'])
        (d / name).write_bytes(data)
        # What produced this image, kept beside it so it can be reproduced or
        # compared later (the files on disk are the source of truth).
        (d / f'{name}.json').write_text(json.dumps({
            'provider': job['provider'], 'style': ss['style'], 'style_label': ss['label'],
            'custom_style': job.get('custom_style', ''), 'prompt': job['prompt'],
            'title': job.get('title', '') if job.get('overlay') else '', 'author': job.get('author', '') if job.get('overlay') else '',
            'settings': ss['comfyui'] if job['provider'] == 'comfyui' else ss['higgsfield'],
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        job['filename'] = name
        job['status'] = 'completed'
        job['last_message'] = '表紙画像を生成しました。' + (' ' + note if note else '')
        if job.get('overlay') and not note and not (job.get('author') or '').strip():
            job['last_message'] += '（著者名が未設定のため、タイトルのみ入れました。設定の基本設定で著者名を入力できます）'
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
_STATE_FIELDS = ('prompt', 'style', 'custom_style', 'provider', 'overlay')


def load_state(pid: int) -> dict:
    p = covers_dir(pid) / 'prompt.json'
    try:
        raw = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    except ValueError:
        raw = {}
    return {'prompt': raw.get('prompt', ''), 'style': raw.get('style') or list_styles()['default'],
            'custom_style': raw.get('custom_style', ''), 'provider': raw.get('provider') or 'comfyui',
            'overlay': raw.get('overlay', True)}


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


def delete_cover(pid: int, filename: str) -> None:
    """Remove one generated image with its sidecar and the untouched original."""
    d = covers_dir(pid)
    if not SAFE_NAME.match(filename) or not (d / filename).exists():
        raise FileNotFoundError(filename)
    if selected_name(pid) == filename:
        _selected_marker(pid).unlink(missing_ok=True)
    for f in (d / filename, d / f'{filename}.json', d / 'raw' / filename):
        f.unlink(missing_ok=True)


def selected_cover(pid: int) -> tuple[bytes, str] | None:
    """(bytes, extension) of the project's chosen cover, or None."""
    name = selected_name(pid)
    if not name:
        return None
    p = covers_dir(pid) / name
    return p.read_bytes(), p.suffix.lower()

