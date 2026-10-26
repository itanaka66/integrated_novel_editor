#!/usr/bin/env python3
"""INE bridge — Anna Executa plugin (JSON-RPC 2.0 over stdio).

Talks to a running Integrated Novel Editor API so Anna can list works,
read story data, draft with the project's context builder, and start
auto-write jobs. Logs go to stderr; stdout is protocol-only.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Callable

MANIFEST: dict[str, Any] = {
    "display_name": "INE Bridge",
    "version": "0.1.0",
    "description": (
        "Connect Anna to a local Integrated Novel Editor (INE) instance. "
        "List works, read the story twin, search episodes, generate prose "
        "with INE's context builder, and manage auto-write jobs."
    ),
    "author": "INE",
    "homepage": "https://github.com/itanaka66/integrated_novel_editor",
    "license": "GPL-3.0",
    "icon": "📖",
    "category": "writing",
    "tags": ["novel", "writing", "ine", "continuity"],
    "credentials": [
        {
            "name": "INE_BASE_URL",
            "display_name": "INE API base URL",
            "description": "Origin of the INE API, without a trailing slash. Default http://localhost:8000",
            "required": False,
            "sensitive": False,
            "default": "http://localhost:8000",
        },
        {
            "name": "INE_USERNAME",
            "display_name": "INE username",
            "description": "HTTP Basic username for the INE API (same as the web login).",
            "required": True,
            "sensitive": False,
        },
        {
            "name": "INE_PASSWORD",
            "display_name": "INE password",
            "description": "HTTP Basic password for the INE API.",
            "required": True,
            "sensitive": True,
        },
    ],
    "runtime": {"type": "uv", "min_version": "0.1.0"},
    "tools": [
        {
            "name": "health",
            "description": "Ping the INE API. Auth is optional for this call.",
            "timeout": 10,
            "parameters": [],
        },
        {
            "name": "list_projects",
            "description": "List INE works (projects): id, name, genre, description.",
            "timeout": 15,
            "parameters": [],
        },
        {
            "name": "get_project",
            "description": "Get one INE work by project_id.",
            "timeout": 15,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "create_project",
            "description": "Create a new INE work.",
            "timeout": 15,
            "parameters": [
                {"name": "name", "type": "string", "description": "Work title", "required": True},
                {"name": "description", "type": "string", "description": "Synopsis", "required": False},
                {"name": "genre", "type": "string", "description": "Genre", "required": False},
                {"name": "rules", "type": "string", "description": "Hard setting rules the AI must obey", "required": False},
                {"name": "language", "type": "string", "description": "ISO-ish language code (default ja)", "required": False},
                {"name": "author", "type": "string", "description": "Author name", "required": False},
                {"name": "episode_goal", "type": "integer", "description": "Target episode count (default 500)", "required": False},
            ],
        },
        {
            "name": "get_story_twin",
            "description": "Story Digital Twin: health score, coverage, continuity, plots. Graphs omitted unless include_graphs=true.",
            "timeout": 30,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {
                    "name": "include_graphs",
                    "type": "boolean",
                    "description": "Include character/world/timeline graphs (large).",
                    "required": False,
                    "default": False,
                },
            ],
        },
        {
            "name": "list_episodes",
            "description": "List episodes of a work (paginated).",
            "timeout": 20,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "limit", "type": "integer", "description": "Page size (default 50, max 200)", "required": False},
                {"name": "offset", "type": "integer", "description": "Offset (default 0)", "required": False},
            ],
        },
        {
            "name": "get_episode",
            "description": "Get one episode including full Markdown content.",
            "timeout": 20,
            "parameters": [
                {"name": "episode_id", "type": "integer", "description": "INE episode id", "required": True},
            ],
        },
        {
            "name": "create_episode",
            "description": "Add an episode to a work.",
            "timeout": 20,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "number", "type": "integer", "description": "Episode number", "required": True},
                {"name": "title", "type": "string", "description": "Episode title", "required": True},
                {"name": "summary", "type": "string", "description": "Short summary", "required": False},
                {"name": "content", "type": "string", "description": "Markdown body", "required": False},
                {"name": "chapter", "type": "string", "description": "Chapter label", "required": False},
            ],
        },
        {
            "name": "save_episode",
            "description": "Update an episode. Saving also snapshots a revision and may update character state.",
            "timeout": 60,
            "parameters": [
                {"name": "episode_id", "type": "integer", "description": "INE episode id", "required": True},
                {"name": "title", "type": "string", "description": "Episode title", "required": False},
                {"name": "summary", "type": "string", "description": "Short summary", "required": False},
                {"name": "content", "type": "string", "description": "Markdown body", "required": False},
                {"name": "chapter", "type": "string", "description": "Chapter label", "required": False},
            ],
        },
        {
            "name": "list_characters",
            "description": "List characters for a work.",
            "timeout": 15,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "create_character",
            "description": "Add a character to a work.",
            "timeout": 15,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "name", "type": "string", "description": "Character name", "required": True},
                {"name": "role", "type": "string", "description": "Role (protagonist, ally, …)", "required": False},
                {"name": "personality", "type": "string", "description": "Personality", "required": False},
                {"name": "speech_style", "type": "string", "description": "Speech style", "required": False},
                {"name": "goal", "type": "string", "description": "Goal", "required": False},
                {"name": "status", "type": "string", "description": "alive / dead / …", "required": False},
                {"name": "description", "type": "string", "description": "Notes", "required": False},
            ],
        },
        {
            "name": "list_world",
            "description": "List world entities (places, tech, glossary, …) for a work.",
            "timeout": 15,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "create_world",
            "description": "Add a world entity.",
            "timeout": 15,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "name", "type": "string", "description": "Entity name", "required": True},
                {"name": "entity_type", "type": "string", "description": "setting / location / technology / glossary / …", "required": False},
                {"name": "description", "type": "string", "description": "Description", "required": False},
                {"name": "rules", "type": "string", "description": "Hard rules", "required": False},
                {"name": "location", "type": "string", "description": "Location", "required": False},
                {"name": "era", "type": "string", "description": "Era", "required": False},
            ],
        },
        {
            "name": "search",
            "description": "Semantic (RAG) search over episode text, with PostgreSQL substring fallback.",
            "timeout": 30,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "query", "type": "string", "description": "Search query", "required": True},
                {"name": "limit", "type": "integer", "description": "Max hits (default 8)", "required": False},
            ],
        },
        {
            "name": "generate",
            "description": "Ask INE's Writer to continue/summarize/proofread using the project's story context.",
            "timeout": 120,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "episode_id", "type": "integer", "description": "Episode to ground the prompt", "required": False},
                {"name": "instruction", "type": "string", "description": "Extra instruction", "required": False},
                {
                    "name": "mode",
                    "type": "string",
                    "description": "continue | summary | plot | proofread (default continue)",
                    "required": False,
                    "default": "continue",
                },
                {"name": "rag_limit", "type": "integer", "description": "RAG snippets to include (default 6)", "required": False},
            ],
        },
        {
            "name": "chat",
            "description": "Send a chat turn on a work. INE persists history and answers from story context.",
            "timeout": 120,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "content", "type": "string", "description": "User message", "required": True},
            ],
        },
        {
            "name": "check_continuity",
            "description": "Run INE's continuity audit (timeline / character / world / foreshadowing).",
            "timeout": 120,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "episode_id", "type": "integer", "description": "Optional episode to focus the audit", "required": False},
            ],
        },
        {
            "name": "list_continuity_issues",
            "description": "List stored open/recent continuity issues for a work.",
            "timeout": 15,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "start_auto_write",
            "description": "Start INE auto-write (Controller plans, Writer drafts). Existing episodes are skipped unless overwrite=true.",
            "timeout": 30,
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "start_episode", "type": "integer", "description": "First episode number (default 1)", "required": False},
                {"name": "end_episode", "type": "integer", "description": "Last episode number (default 500)", "required": False},
                {"name": "premise", "type": "string", "description": "Optional extra premise for planners", "required": False},
                {"name": "overwrite", "type": "boolean", "description": "Overwrite existing episode text", "required": False, "default": False},
                {"name": "writer_model", "type": "string", "description": "Ollama Writer model name", "required": False},
                {"name": "controller_model", "type": "string", "description": "Ollama Controller model name", "required": False},
            ],
        },
        {
            "name": "get_auto_write_job",
            "description": "Poll an auto-write job's status and progress.",
            "timeout": 15,
            "parameters": [
                {"name": "job_id", "type": "integer", "description": "Auto-write job id", "required": True},
            ],
        },
        {
            "name": "stop_auto_write",
            "description": "Request stop of a running auto-write job.",
            "timeout": 15,
            "parameters": [
                {"name": "job_id", "type": "integer", "description": "Auto-write job id", "required": True},
            ],
        },
    ],
}


def _log(message: str) -> None:
    print(f"[ine-bridge] {message}", file=sys.stderr)


def _int(value: Any, name: str, *, required: bool = True, default: int | None = None) -> int | None:
    if value is None or value == "":
        if required:
            raise ValueError(f"{name} is required")
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _omit_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if v is not None}


def resolve_connection(credentials: dict[str, Any] | None) -> tuple[str, str, str]:
    creds = credentials or {}
    base = (
        creds.get("INE_BASE_URL")
        or os.environ.get("INE_BASE_URL")
        or "http://localhost:8000"
    ).rstrip("/")
    user = creds.get("INE_USERNAME") or os.environ.get("INE_USERNAME") or ""
    password = creds.get("INE_PASSWORD") or os.environ.get("INE_PASSWORD") or ""
    return base, user, password


def request_json(
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> tuple[int, Any, str]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        if raw:
            try:
                return exc.code, json.loads(raw), raw
            except json.JSONDecodeError:
                return exc.code, None, raw
        return exc.code, None, str(exc.reason)
    except urllib.error.URLError as exc:
        raise ConnectionError(f"INE API unreachable at {url}: {exc.reason}") from exc
    if not raw:
        return status, None, ""
    try:
        return status, json.loads(raw), raw
    except json.JSONDecodeError:
        return status, None, raw


def ine_call(
    credentials: dict[str, Any] | None,
    method: str,
    path: str,
    *,
    query: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    auth: bool = True,
    timeout: float = 30,
) -> Any:
    base, user, password = resolve_connection(credentials)
    if auth and (not user or not password):
        raise PermissionError(
            "INE_USERNAME and INE_PASSWORD are required. Set them in Anna credentials or the environment."
        )
    qs = ""
    if query:
        from urllib.parse import urlencode

        qs = "?" + urlencode({k: v for k, v in query.items() if v is not None})
    url = f"{base}/api/v1{path}{qs}"
    headers = {"Accept": "application/json"}
    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if auth:
        token = base64.b64encode(f"{user}:{password}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    status, parsed, raw = request_json(method, url, headers=headers, body=body, timeout=timeout)
    if status >= 400:
        detail = parsed if parsed is not None else raw
        raise RuntimeError(f"INE API {method} {path} failed ({status}): {detail}")
    return parsed


def _summarize_twin(data: dict[str, Any], include_graphs: bool) -> dict[str, Any]:
    if include_graphs or not isinstance(data, dict):
        return data
    out = dict(data)
    for key in ("characters", "world", "timeline"):
        graph = out.get(key)
        if isinstance(graph, dict):
            out[key] = {
                "node_count": len(graph.get("nodes") or []),
                "edge_count": len(graph.get("edges") or []),
                "omitted": True,
            }
    return out


def tool_health(_args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    return ine_call(credentials, "GET", "/health", auth=False, timeout=10)


def tool_list_projects(_args, credentials):
    projects = ine_call(credentials, "GET", "/projects")
    return {"projects": projects}


def tool_get_project(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    return ine_call(credentials, "GET", f"/projects/{pid}")


def tool_create_project(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    name = (args.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    body = _omit_none(
        {
            "name": name,
            "description": args.get("description"),
            "genre": args.get("genre"),
            "rules": args.get("rules"),
            "language": args.get("language"),
            "author": args.get("author"),
            "episode_goal": _int(args.get("episode_goal"), "episode_goal", required=False),
        }
    )
    return ine_call(credentials, "POST", "/projects", json_body=body)


def tool_get_story_twin(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    data = ine_call(credentials, "GET", f"/projects/{pid}/story-twin")
    return _summarize_twin(data if isinstance(data, dict) else {}, _bool(args.get("include_graphs")))


def tool_list_episodes(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    limit = _int(args.get("limit"), "limit", required=False, default=50) or 50
    offset = _int(args.get("offset"), "offset", required=False, default=0) or 0
    return ine_call(
        credentials,
        "GET",
        f"/projects/{pid}/episodes",
        query={"limit": max(1, min(limit, 200)), "offset": max(0, offset)},
    )


def tool_get_episode(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    eid = _int(args.get("episode_id"), "episode_id")
    return ine_call(credentials, "GET", f"/episodes/{eid}")


def tool_create_episode(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    number = _int(args.get("number"), "number")
    title = (args.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    body = _omit_none(
        {
            "number": number,
            "title": title,
            "summary": args.get("summary"),
            "content": args.get("content"),
            "chapter": args.get("chapter"),
        }
    )
    return ine_call(credentials, "POST", f"/projects/{pid}/episodes", json_body=body)


def tool_save_episode(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    eid = _int(args.get("episode_id"), "episode_id")
    body = _omit_none(
        {
            "title": args.get("title"),
            "summary": args.get("summary"),
            "content": args.get("content"),
            "chapter": args.get("chapter"),
        }
    )
    if not body:
        raise ValueError("provide at least one of title, summary, content, chapter")
    return ine_call(credentials, "PUT", f"/episodes/{eid}", json_body=body, timeout=60)


def tool_list_characters(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    return ine_call(credentials, "GET", f"/projects/{pid}/characters")


def tool_create_character(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    name = (args.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    body = _omit_none(
        {
            "name": name,
            "role": args.get("role"),
            "personality": args.get("personality"),
            "speech_style": args.get("speech_style"),
            "goal": args.get("goal"),
            "status": args.get("status"),
            "description": args.get("description"),
        }
    )
    return ine_call(credentials, "POST", f"/projects/{pid}/characters", json_body=body)


def tool_list_world(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    return ine_call(credentials, "GET", f"/projects/{pid}/world")


def tool_create_world(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    name = (args.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    body = _omit_none(
        {
            "name": name,
            "entity_type": args.get("entity_type"),
            "description": args.get("description"),
            "rules": args.get("rules"),
            "location": args.get("location"),
            "era": args.get("era"),
        }
    )
    return ine_call(credentials, "POST", f"/projects/{pid}/world", json_body=body)


def tool_search(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    query = (args.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    limit = _int(args.get("limit"), "limit", required=False, default=8) or 8
    return ine_call(
        credentials,
        "POST",
        "/rag/search",
        json_body={"project_id": pid, "query": query, "limit": max(1, min(limit, 40))},
    )


def tool_generate(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    mode = (args.get("mode") or "continue").strip()
    allowed = {"continue", "summary", "plot", "proofread"}
    if mode not in allowed:
        raise ValueError(f"mode must be one of {sorted(allowed)}")
    body = _omit_none(
        {
            "project_id": pid,
            "episode_id": _int(args.get("episode_id"), "episode_id", required=False),
            "instruction": args.get("instruction") or "",
            "mode": mode,
            "rag_limit": _int(args.get("rag_limit"), "rag_limit", required=False, default=6),
        }
    )
    return ine_call(credentials, "POST", "/ai/generate", json_body=body, timeout=120)


def tool_chat(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    content = (args.get("content") or "").strip()
    if not content:
        raise ValueError("content is required")
    return ine_call(
        credentials,
        "POST",
        f"/projects/{pid}/chat",
        json_body={"content": content},
        timeout=120,
    )


def tool_check_continuity(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    body = _omit_none(
        {
            "project_id": pid,
            "episode_id": _int(args.get("episode_id"), "episode_id", required=False),
        }
    )
    return ine_call(credentials, "POST", "/continuity/check", json_body=body, timeout=120)


def tool_list_continuity_issues(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    return ine_call(credentials, "GET", f"/projects/{pid}/continuity/issues")


def tool_start_auto_write(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    body = _omit_none(
        {
            "project_id": pid,
            "start_episode": _int(args.get("start_episode"), "start_episode", required=False, default=1),
            "end_episode": _int(args.get("end_episode"), "end_episode", required=False, default=500),
            "premise": args.get("premise") or "",
            "overwrite": _bool(args.get("overwrite")),
            "writer_model": args.get("writer_model"),
            "controller_model": args.get("controller_model"),
        }
    )
    return ine_call(credentials, "POST", "/auto-write/start", json_body=body)


def tool_get_auto_write_job(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    job_id = _int(args.get("job_id"), "job_id")
    return ine_call(credentials, "GET", f"/auto-write/{job_id}")


def tool_stop_auto_write(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    job_id = _int(args.get("job_id"), "job_id")
    return ine_call(credentials, "POST", f"/auto-write/{job_id}/stop", json_body={})


TOOL_DISPATCH: dict[str, Callable[[dict[str, Any], dict[str, Any] | None], Any]] = {
    "health": tool_health,
    "list_projects": tool_list_projects,
    "get_project": tool_get_project,
    "create_project": tool_create_project,
    "get_story_twin": tool_get_story_twin,
    "list_episodes": tool_list_episodes,
    "get_episode": tool_get_episode,
    "create_episode": tool_create_episode,
    "save_episode": tool_save_episode,
    "list_characters": tool_list_characters,
    "create_character": tool_create_character,
    "list_world": tool_list_world,
    "create_world": tool_create_world,
    "search": tool_search,
    "generate": tool_generate,
    "chat": tool_chat,
    "check_continuity": tool_check_continuity,
    "list_continuity_issues": tool_list_continuity_issues,
    "start_auto_write": tool_start_auto_write,
    "get_auto_write_job": tool_get_auto_write_job,
    "stop_auto_write": tool_stop_auto_write,
}


def handle_describe(_params: dict[str, Any]) -> dict[str, Any]:
    return MANIFEST


def handle_invoke(params: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(params, dict):
        return {"success": False, "error": "params must be an object"}
    tool_name = params.get("tool")
    args = params.get("arguments") or {}
    try:
        if not isinstance(args, dict):
            raise ValueError("`arguments` must be an object")
        credentials = (params.get("context") or {}).get("credentials") or {}
        fn = TOOL_DISPATCH.get(tool_name)
        if fn is None:
            raise ValueError(f"unknown tool: {tool_name!r}")
        payload = fn(args, credentials)
    except Exception as exc:  # noqa: BLE001 — surface as InvokeResult, not a transport crash
        _log(f"{tool_name} failed: {type(exc).__name__}")
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"success": True, "data": payload}


def handle_health(_params: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ready"}


METHOD_DISPATCH = {
    "describe": handle_describe,
    "invoke": handle_invoke,
    "health": handle_health,
}


def send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> None:
    _log(f"{MANIFEST['display_name']} v{MANIFEST['version']} ready")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"parse error: {exc}"}})
            continue
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        handler = METHOD_DISPATCH.get(method)
        if handler is None:
            send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"method not found: {method}"}})
            continue
        try:
            result = handler(params)
            send({"jsonrpc": "2.0", "id": req_id, "result": result})
        except Exception as exc:  # noqa: BLE001
            send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(exc)}})


if __name__ == "__main__":
    main()
