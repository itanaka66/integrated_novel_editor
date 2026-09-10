import asyncio
import logging
import httpx
from .config import settings

logger = logging.getLogger(__name__)

# Retries are for transient network failures (connection refused/reset,
# timeout) only — an HTTP error status from Ollama itself (e.g. 404 unknown
# model) is retried too since it's usually the model still loading, but we
# cap it at a couple of attempts so a genuinely bad request fails fast
# rather than hanging the caller for minutes.
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2

async def _post_with_retry(url, json, timeout):
 last_error = None
 for attempt in range(1, MAX_ATTEMPTS + 1):
  try:
   async with httpx.AsyncClient(timeout=timeout) as c:
    r = await c.post(url, json=json)
    r.raise_for_status()
    return r
  except (httpx.TransportError, httpx.HTTPStatusError) as ex:
   last_error = ex
   if attempt == MAX_ATTEMPTS:
    break
   logger.warning('Ollama request to %s failed (attempt %d/%d): %s; retrying in %ds', url, attempt, MAX_ATTEMPTS, ex, RETRY_BACKOFF_SECONDS)
   await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
 raise last_error

async def generate(prompt,model=None,url=None,timeout=240):
 m=model or settings.ollama_model
 base=(url or settings.ollama_url).rstrip('/')
 r=await _post_with_retry(base+'/api/generate',{'model':m,'prompt':prompt,'stream':False},timeout)
 return r.json().get('response',''),m

async def controller_generate(prompt):
 return await generate(prompt, settings.controller_ollama_model, settings.controller_ollama_url, 180)

async def embed(texts):
 r=await _post_with_retry(settings.ollama_url.rstrip('/')+'/api/embed',{'model':settings.ollama_embed_model,'input':texts},180)
 return r.json()['embeddings']
