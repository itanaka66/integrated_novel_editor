from editor_common import ollama as _common_ollama
from .runtime_config import get_effective_config

# Sent as Ollama's own "options" object on every /api/generate call (both
# the Writer and the Controller model — see controller_generate below).
# num_ctx/num_predict are sized for this app's long-form novel context
# (full episode history + RAG hits in the prompt, long continuations
# expected back); temperature/top_p/repeat_penalty are fixed defaults
# rather than exposed as settings, since nothing here lets a user tune them
# per-project yet.
GENERATION_OPTIONS = {
    'num_ctx': 65536,
    'num_predict': 32768,
    'temperature': 0.7,
    'top_p': 0.9,
    'repeat_penalty': 1.1,
}


async def generate(prompt, model=None, url=None, timeout=240):
    cfg = get_effective_config()
    return await _common_ollama.generate(prompt, model or cfg.ollama_model, url or cfg.ollama_url, timeout, options=GENERATION_OPTIONS)


async def generate_stream(prompt, model=None, url=None):
    """Yields {'delta': str} chunks as Ollama's native stream produces text,
    then a final {'done': True, 'model': str} — used by /episodes/{id}/proofread/stream
    to keep bytes flowing to the client throughout a slow local-LLM generation
    (a buffered single response was observed to sit idle long enough to trip
    an intermediate proxy's idle timeout)."""
    cfg = get_effective_config()
    async for event in _common_ollama.stream_generate(prompt, model or cfg.ollama_model, url or cfg.ollama_url, options=GENERATION_OPTIONS):
        if event.get('done'):
            yield {'done': True, 'model': event.get('model')}
        else:
            yield event


async def controller_generate(prompt):
    cfg = get_effective_config()
    return await generate(prompt, cfg.controller_ollama_model, cfg.controller_ollama_url, 180)


async def embed(texts):
    cfg = get_effective_config()
    return await _common_ollama.embed(texts, cfg.ollama_embed_model, cfg.ollama_url)
