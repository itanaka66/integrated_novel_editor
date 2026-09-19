from editor_common import ollama as _common_ollama
from .runtime_config import get_effective_config


async def generate(prompt, model=None, url=None, timeout=240):
    cfg = get_effective_config()
    return await _common_ollama.generate(prompt, model or cfg.ollama_model, url or cfg.ollama_url, timeout)


async def generate_stream(prompt, model=None, url=None):
    """Yields {'delta': str} chunks as Ollama's native stream produces text,
    then a final {'done': True, 'model': str} — used by /episodes/{id}/proofread/stream
    to keep bytes flowing to the client throughout a slow local-LLM generation
    (a buffered single response was observed to sit idle long enough to trip
    an intermediate proxy's idle timeout)."""
    cfg = get_effective_config()
    async for event in _common_ollama.stream_generate(prompt, model or cfg.ollama_model, url or cfg.ollama_url):
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
