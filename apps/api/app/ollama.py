from editor_common import ollama as _common_ollama
from .runtime_config import get_effective_config


async def generate(prompt, model=None, url=None, timeout=240):
    cfg = get_effective_config()
    return await _common_ollama.generate(prompt, model or cfg.ollama_model, url or cfg.ollama_url, timeout)


async def controller_generate(prompt):
    cfg = get_effective_config()
    return await generate(prompt, cfg.controller_ollama_model, cfg.controller_ollama_url, 180)


async def embed(texts):
    cfg = get_effective_config()
    return await _common_ollama.embed(texts, cfg.ollama_embed_model, cfg.ollama_url)
