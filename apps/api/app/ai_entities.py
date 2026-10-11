"""Ask the AI for a batch of new story-knowledge rows (characters, world,
glossary, plots, foreshadowing, timeline) and add them to a project.

Rows whose key matches something already there (or repeated in the same batch)
are dropped, so pressing the button again adds fresh ideas, not copies."""
import json
import re
import unicodedata

from sqlalchemy import select

from .models import Character, WorldEntity, Plot, Foreshadowing, TimelineEvent
from .ollama import generate
from .translator import _PROMPT_LANG

# kind -> model, key fields, field spec (name -> hint), constant defaults, row filter
KINDS: dict[str, dict] = {
    'characters': {
        'label': 'キャラクター', 'model': Character, 'keys': ('name',),
        'fields': {'name': '名前', 'role': '役割（主人公・ライバル等）', 'personality': '性格', 'speech_style': '口調',
                   'goal': '目標', 'status': 'alive / dead / missing / unknown のいずれか', 'description': '補足'},
        'choices': {'status': ['alive', 'dead', 'missing', 'unknown']}, 'defaults': {'status': 'alive'},
    },
    'world': {
        'label': '世界観', 'model': WorldEntity, 'keys': ('name',),
        'fields': {'name': '名称', 'entity_type': 'setting / location / technology / magic / organization / item のいずれか',
                   'description': '説明', 'rules': 'ルール', 'location': '場所', 'era': '時代'},
        'choices': {'entity_type': ['setting', 'location', 'technology', 'magic', 'organization', 'item']}, 'defaults': {'entity_type': 'setting'},
        'where': lambda m: m.entity_type != 'glossary',
    },
    'glossary': {
        'label': '用語集', 'model': WorldEntity, 'keys': ('name',),
        'fields': {'name': '用語', 'description': '説明', 'location': 'カテゴリ'},
        'choices': {}, 'defaults': {'entity_type': 'glossary'}, 'where': lambda m: m.entity_type == 'glossary',
    },
    'plots': {
        'label': 'プロット', 'model': Plot, 'keys': ('title',),
        'fields': {'title': 'タイトル', 'plot_type': 'main_arc / arc / subplot のいずれか', 'status': 'planned / active / completed のいずれか',
                   'start_episode': '開始話数（整数）', 'end_episode': '終了話数（整数）', 'objective': '目的', 'conflict': '対立', 'resolution': '決着'},
        'choices': {'plot_type': ['main_arc', 'arc', 'subplot'], 'status': ['planned', 'active', 'completed']}, 'defaults': {'plot_type': 'arc', 'status': 'planned'},
        'ints': ('start_episode', 'end_episode'),
    },
    'foreshadowings': {
        'label': '伏線', 'model': Foreshadowing, 'keys': ('title',),
        'fields': {'title': 'タイトル', 'description': '説明', 'setup_episode': '設置話数（整数）', 'payoff_episode': '回収話数（整数）', 'status': 'open / resolved / abandoned のいずれか'},
        'choices': {'status': ['open', 'resolved', 'abandoned']}, 'defaults': {'status': 'open'}, 'ints': ('setup_episode', 'payoff_episode'),
    },
    'timeline': {
        'label': '年表', 'model': TimelineEvent, 'keys': ('episode_number', 'title'),
        'fields': {'episode_number': '話数（整数）', 'title': '出来事', 'world_time': '世界内時間', 'description': '説明'},
        'choices': {}, 'defaults': {'episode_number': 1}, 'ints': ('episode_number',),
    },
}


def norm(v) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(v or ''))).lower()


def row_key(spec: dict, row) -> tuple:
    get = row.get if isinstance(row, dict) else (lambda k: getattr(row, k, None))
    return tuple(norm(get(k)) for k in spec['keys'])


def parse_rows(text: str) -> list[dict]:
    m = re.search(r'\[.*\]', text or '', re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def clean_row(spec: dict, raw: dict) -> dict | None:
    row = dict(spec['defaults'])
    for k in spec['fields']:
        if k not in raw or raw[k] is None:
            continue
        v = raw[k]
        if k in spec.get('ints', ()):
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
        else:
            v = str(v).strip()
            if k in spec['choices'] and v not in spec['choices'][k]:
                continue
        row[k] = v
    return row if all(row.get(k) not in (None, '') for k in spec['keys']) else None


async def add_ai_rows(db, project, kind: str, count: int = 10) -> list:
    spec = KINDS[kind]
    model = spec['model']
    existing = [r for r in db.scalars(select(model).where(model.project_id == project.id)).all()
                if spec.get('where', lambda m: True)(r)]
    seen = {row_key(spec, r) for r in existing}
    names = [str(getattr(r, spec['keys'][-1])) for r in existing][:120]
    chars = [c.name for c in db.scalars(select(Character).where(Character.project_id == project.id)).all()][:40]
    lang = _PROMPT_LANG.get(project.language or 'ja', 'Japanese')
    fields = '\n'.join(f'- {k}: {hint}' for k, hint in spec['fields'].items())
    prompt = f'''あなたは長編小説の設定編集者です。次の作品に追加する「{spec['label']}」の新しい案を{count}件、考えてください。
作品名: {project.name}
ジャンル: {project.genre}
あらすじ: {project.description}
ルール・方針: {project.rules}
既存の登場人物: {', '.join(chars) or '（なし）'}
既存の{spec['label']}（これらと重複しないこと）: {', '.join(names) or '（なし）'}

出力はJSON配列のみ（前置き・説明・コードブロック不要）。各要素は次のキーを持つオブジェクトにしてください。値は{lang}で書いてください。
{fields}'''
    text, _ = await generate(prompt)
    created = []
    for raw in parse_rows(text):
        row = clean_row(spec, raw)
        if row is None:
            continue
        key = row_key(spec, row)
        if key in seen:
            continue
        seen.add(key)
        obj = model(project_id=project.id, **row)
        db.add(obj)
        created.append(obj)
        if len(created) >= count:
            break
    db.commit()
    for o in created:
        db.refresh(o)
    return created
