from editor_common import ollama as _common_ollama
from .config import settings as env_settings
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


async def generate(prompt, model=None, url=None, timeout=240, options=WRITER_GENERATION_OPTIONS, api_key=None):
    # api_key=None here means "use the Writer's own key" (env_settings.
    # ollama_api_key), not "no key" — controller_generate below passes its
    # own key explicitly to override that, since Controller is typically a
    # separate Ollama instance behind its own auth, if any.
    cfg = get_effective_config()
    key = api_key if api_key is not None else (env_settings.ollama_api_key or None)
    return await _common_ollama.generate(prompt, model or cfg.ollama_model, url or cfg.ollama_url, timeout, options=options, api_key=key)


async def generate_stream(prompt, model=None, url=None):
    """Yields {'delta': str} chunks as Ollama's native stream produces text,
    then a final {'done': True, 'model': str} — used by /episodes/{id}/proofread/stream
    to keep bytes flowing to the client throughout a slow local-LLM generation
    (a buffered single response was observed to sit idle long enough to trip
    an intermediate proxy's idle timeout)."""
    cfg = get_effective_config()
    async for event in _common_ollama.stream_generate(
        prompt, model or cfg.ollama_model, url or cfg.ollama_url,
        options=WRITER_GENERATION_OPTIONS, api_key=env_settings.ollama_api_key or None,
    ):
        if event.get('done'):
            yield {'done': True, 'model': event.get('model')}
        else:
            yield event


async def controller_generate(prompt):
    # No options override — the Controller (planning/quality-gate) model
    # runs on its own, smaller GPU; Ollama's own defaults are what that
    # hardware was sized for, unlike the Writer's num_ctx=65536 above.
    # Its own api_key (possibly blank/unset, independently of the Writer's)
    # since it's typically a separate Ollama instance.
    cfg = get_effective_config()
    return await generate(
        prompt, cfg.controller_ollama_model, cfg.controller_ollama_url, 180,
        options=None, api_key=env_settings.controller_ollama_api_key or None,
    )


async def embed(texts):
    cfg = get_effective_config()
    return await _common_ollama.embed(texts, cfg.ollama_embed_model, cfg.ollama_url, api_key=env_settings.ollama_api_key or None)
