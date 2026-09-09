import httpx
from .config import settings

async def generate(prompt,model=None,url=None,timeout=240):
 m=model or settings.ollama_model
 base=(url or settings.ollama_url).rstrip('/')
 async with httpx.AsyncClient(timeout=240) as c:
  r=await c.post(settings.ollama_url.rstrip('/')+'/api/generate',json={'model':m,'prompt':prompt,'stream':False}); r.raise_for_status(); return r.json().get('response',''),m

async def controller_generate(prompt):
 return await generate(prompt, settings.controller_ollama_model, settings.controller_ollama_url, 180)

async def embed(texts):
 async with httpx.AsyncClient(timeout=180) as c:
  r=await c.post(settings.ollama_url.rstrip('/')+'/api/embed',json={'model':settings.ollama_embed_model,'input':texts}); r.raise_for_status(); return r.json()['embeddings']
