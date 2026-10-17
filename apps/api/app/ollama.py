import contextlib
import contextvars

from editor_common import ollama as _common_ollama
from .config import settings as env_settings
from .llm_queue import slot
from .runtime_config import get_effective_config

# Sent as Ollama's own "options" object on every Writer /api/generate call
# only (see controller_generate below — the Controller model runs on
# different, more modest hardware and stays on Ollama's own defaults).
# num_ctx/num_predict are sized for this app's long-form novel context
# (full episode history + RAG hits in the prompt, long continuations
# expected back); temperature/top_p/repeat_penalty are fixed defaults
# rather than exposed as settings, since nothing here lets a user tune them
# per-project yet.
WRITER_GENERATION_OPTIONS = {
    'num_ctx': 65536,
    'num_predict': 32768,
    'temperature': 0.7,
    'top_p': 0.9,
    'repeat_penalty': 1.1,
}


async def generate(prompt, model=None, url=None, timeout=240, options=WRITER_GENERATION_OPTIONS, api_key=None, kind='writer'):
    # api_key=None here means "use the Writer's own key" (env_settings.
    # ollama_api_key), not "no key" — controller_generate below passes its
    # own key explicitly to override that, since Controller is typically a
    # separate Ollama instance behind its own auth, if any.
    cfg = get_effective_config()
    key = api_key if api_key is not None else (env_settings.ollama_api_key or None)
    model, url = model or cfg.ollama_model, url or cfg.ollama_url
    async with slot(kind=kind, model=model, url=url):
        return await _common_ollama.generate(prompt, model, url, timeout, options=options, api_key=key)


async def generate_stream(prompt, model=None, url=None):
    """Yields {'delta': str} chunks as Ollama's native stream produces text,
    then a final {'done': True, 'model': str} — used by /episodes/{id}/proofread/stream
    to keep bytes flowing to the client throughout a slow local-LLM generation
    (a buffered single response was observed to sit idle long enough to trip
    an intermediate proxy's idle timeout)."""
    cfg = get_effective_config()
    model, url = model or cfg.ollama_model, url or cfg.ollama_url
    async with slot(kind='writer', model=model, url=url):
        async for event in _common_ollama.stream_generate(
            prompt, model, url,
            options=WRITER_GENERATION_OPTIONS, api_key=env_settings.ollama_api_key or None,
        ):
            if event.get('done'):
                yield {'done': True, 'model': event.get('model')}
            else:
                yield event


_busy: dict[tuple[str, str], int] = {}
_rr = [0]


def translator_endpoints(cfg=None, language: str | None = None) -> list[dict]:
    """The translation LLMs in effect for `language` (any, when None): enabled rows
    whose language boxes include it. When there is none - no list, every row off,
    or no row handling that language - the single translator setting is used,
    which defaults to the Controller (so the Controller translates too)."""
    cfg = cfg or get_effective_config()
    active = [e for e in cfg.translator_pool  # unchecked rows stay listed but are not used
              if e.get('enabled', True) and (language is None or language in e.get('languages', [language]))]
    return active or [{'url': cfg.translator_ollama_url, 'model': cfg.translator_ollama_model}]


def translator_count(language: str | None = None) -> int:
    return len(translator_endpoints(language=language))


def pick_endpoint(endpoints: list[dict]) -> dict:
    """The least busy endpoint (ties go round-robin), so a free translation LLM is
    used before one that is already working."""
    low = min(_busy.get((e['url'], e['model']), 0) for e in endpoints)
    free = [e for e in endpoints if _busy.get((e['url'], e['model']), 0) == low]
    _rr[0] += 1
    return free[_rr[0] % len(free)]


# The translation LLM an episode is pinned to (see pin_translator).
_pinned: contextvars.ContextVar[dict | None] = contextvars.ContextVar('translator_pinned', default=None)


@contextlib.contextmanager
def pin_translator(language: str | None = None):
    """Use ONE translation LLM for everything inside the block. An episode is
    translated start to finish (chapter, title, summary, every chunk, retries and
    fixes) by the same LLM, so its wording and names stay consistent and one
    episode never occupies several LLMs; different episodes still go to different
    LLMs. The LLM is counted as busy for the whole block, so concurrent episodes
    spread out instead of piling onto one."""
    ep = pick_endpoint(translator_endpoints(language=language))
    key = (ep['url'], ep['model'])
    _busy[key] = _busy.get(key, 0) + 1
    token = _pinned.set(ep)
    try:
        yield ep
    finally:
        _pinned.reset(token)
        _busy[key] -= 1


async def translator_generate(prompt, language: str | None = None):
    """Translation. Its own server/model (Settings > 接続設定), which defaults to
    the Controller's; same API key as the Controller (typically the same
    instance) and no options override."""
    pinned = _pinned.get()
    ep = pinned or pick_endpoint(translator_endpoints(language=language))
    model, url = ep['model'], ep['url']
    if model.lower().startswith('qwen3'):
        # Qwen3 "thinks" for ~1000 tokens before answering, which turns a
        # minute into many; its documented /no_think switch skips that.
        prompt = prompt.rstrip() + ' /no_think'
    key = (url, model)
    if not pinned:  # a pinned LLM is already counted busy by pin_translator
        _busy[key] = _busy.get(key, 0) + 1
    try:
        return await generate(
            prompt, model, url, env_settings.translator_timeout_seconds,
            options=None, api_key=env_settings.controller_ollama_api_key or None, kind='translator',
        )
    finally:
        if not pinned:
            _busy[key] -= 1


async def reviewer_generate(prompt):
    """Translation check. Runs on the Controller's server/model (qwen3:14b in the
    reference setup — a stronger judge than the translation model) with the
    long reasoning phase switched off for Qwen3, and the translator's timeout."""
    cfg = get_effective_config()
    model = cfg.controller_ollama_model
    if model.lower().startswith('qwen3'):
        prompt = prompt.rstrip() + ' /no_think'
    return await generate(
        prompt, model, cfg.controller_ollama_url, env_settings.translator_timeout_seconds,
        options=None, api_key=env_settings.controller_ollama_api_key or None, kind='controller',
    )


async def controller_generate(prompt):
    # No options override — the Controller (planning/quality-gate) model
    # runs on its own, smaller GPU; Ollama's own defaults are what that
    # hardware was sized for, unlike the Writer's num_ctx=65536 above.
    # Its own api_key (possibly blank/unset, independently of the Writer's)
    # since it's typically a separate Ollama instance.
    cfg = get_effective_config()
    return await generate(
        prompt, cfg.controller_ollama_model, cfg.controller_ollama_url, 180,
        options=None, api_key=env_settings.controller_ollama_api_key or None, kind='controller',
    )


async def alignment_embed(texts):
    """Multilingual sentence embeddings for the translation omission check (the
    RAG embedding model may be English-only, so this has its own setting)."""
    cfg = get_effective_config()
    model = env_settings.translation_embed_model
    async with slot(kind='embed', model=model, url=cfg.ollama_url):
        return await _common_ollama.embed(texts, model, cfg.ollama_url, api_key=env_settings.ollama_api_key or None)


async def embed(texts):
    cfg = get_effective_config()
    async with slot(kind='embed', model=cfg.ollama_embed_model, url=cfg.ollama_url):
        return await _common_ollama.embed(texts, cfg.ollama_embed_model, cfg.ollama_url, api_key=env_settings.ollama_api_key or None)
