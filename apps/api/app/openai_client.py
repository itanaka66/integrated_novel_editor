"""Async OpenAI-compatible LLM client (POST /v1/chat/completions).
Used in place of editor_common.ollama when ANNA_LLM_URL is set.
Exposes the same function signatures so ollama.py can route transparently.
"""
import asyncio
import json
import logging

import httpx

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2


def _headers(api_key: str | None) -> dict:
    h: dict = {}
    if api_key:
        h['Authorization'] = f'Bearer {api_key}'
    return h


def _payload(model: str, prompt: str, stream: bool) -> dict:
    return {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': stream,
    }


async def _post_with_retry(url: str, payload: dict, timeout: float, headers: dict):
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(url, json=payload, headers=headers)
                r.raise_for_status()
                return r
        except (httpx.TransportError, httpx.HTTPStatusError) as ex:
            last_error = ex
            # 4xx are client-side configuration errors; retrying won't help.
            if isinstance(ex, httpx.HTTPStatusError) and ex.response.status_code < 500:
                break
            if attempt == MAX_ATTEMPTS:
                break
            logger.warning(
                'OpenAI request to %s failed (attempt %d/%d): %s; retrying in %ds',
                url, attempt, MAX_ATTEMPTS, ex, RETRY_BACKOFF_SECONDS,
            )
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise last_error


async def generate(prompt, model, url, timeout=240, options=None, api_key=None):
    endpoint = url.rstrip('/') + '/chat/completions'
    r = await _post_with_retry(endpoint, _payload(model, prompt, False), timeout, _headers(api_key))
    data = r.json()
    text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
    return text, model


async def generate_with_usage(prompt, model, url, timeout=240, options=None, api_key=None):
    endpoint = url.rstrip('/') + '/chat/completions'
    r = await _post_with_retry(endpoint, _payload(model, prompt, False), timeout, _headers(api_key))
    data = r.json()
    text = data.get('choices', [{}])[0].get('message', {}).get('content', '')
    u = data.get('usage', {})
    usage = {'input_tokens': u.get('prompt_tokens'), 'output_tokens': u.get('completion_tokens')}
    return text, model, usage


async def stream_generate(prompt, model, url, timeout=240, options=None, api_key=None):
    endpoint = url.rstrip('/') + '/chat/completions'
    async with httpx.AsyncClient(timeout=timeout) as c:
        async with c.stream(
            'POST', endpoint,
            json=_payload(model, prompt, True),
            headers=_headers(api_key),
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith('data: '):
                    continue
                data_str = line[6:]
                if data_str == '[DONE]':
                    break
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                content = chunk.get('choices', [{}])[0].get('delta', {}).get('content')
                if content:
                    yield {'delta': content}
    yield {'done': True, 'model': model, 'usage': {'input_tokens': None, 'output_tokens': None}}
