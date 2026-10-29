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
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Callable

MANIFEST: dict[str, Any] = {
    "display_name": "INE Bridge",
    "version": "0.2.1",
    "description": (
        "Connect Anna to a local Integrated Novel Editor (INE) instance. "
        "List works, read the story twin, search episodes, manage plots and "
        "foreshadowings, reflect entities to novel, generate prose and chat "
        "using Anna's own LLM, generate cover prompts, and manage auto-write jobs."
    ),
    "credentials": [
        {
            "name": "INE_BASE_URL",
            "display_name": "INE API base URL",
            "description": "Origin of the INE API, without a trailing slash. Default https://neomedia.dynv6.net:6556",
            "required": False,
            "sensitive": False,
            "default": "https://neomedia.dynv6.net:6556",
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
            "parameters": [],
        },
        {
            "name": "list_projects",
            "description": "List INE works (projects): id, name, genre, description.",
            "parameters": [],
        },
        {
            "name": "get_project",
            "description": "Get one INE work by project_id.",
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "create_project",
            "description": "Create a new INE work.",
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
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "limit", "type": "integer", "description": "Page size (default 50, max 200)", "required": False},
                {"name": "offset", "type": "integer", "description": "Offset (default 0)", "required": False},
            ],
        },
        {
            "name": "get_episode",
            "description": "Get one episode including full Markdown content.",
            "parameters": [
                {"name": "episode_id", "type": "integer", "description": "INE episode id", "required": True},
            ],
        },
        {
            "name": "create_episode",
            "description": "Add an episode to a work.",
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
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "create_character",
            "description": "Add a character to a work.",
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
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "create_world",
            "description": "Add a world entity.",
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
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "query", "type": "string", "description": "Search query", "required": True},
                {"name": "limit", "type": "integer", "description": "Max hits (default 8)", "required": False},
            ],
        },
        {
            "name": "generate",
            "description": "Ask INE's Writer to continue/summarize/proofread using the project's story context.",
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
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "content", "type": "string", "description": "User message", "required": True},
            ],
        },
        {
            "name": "check_continuity",
            "description": "Run INE's continuity audit (timeline / character / world / foreshadowing).",
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "episode_id", "type": "integer", "description": "Optional episode to focus the audit", "required": False},
            ],
        },
        {
            "name": "list_continuity_issues",
            "description": "List stored open/recent continuity issues for a work.",
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "start_auto_write",
            "description": (
                "Create an auto-write job (queued state). "
                "Anna drives the actual writing via auto_write_step — call it after creating the job."
            ),
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "start_episode", "type": "integer", "description": "First episode number (default 1)", "required": False},
                {"name": "end_episode", "type": "integer", "description": "Last episode number (default 500)", "required": False},
                {"name": "premise", "type": "string", "description": "Optional extra premise for planners", "required": False},
                {"name": "overwrite", "type": "boolean", "description": "Overwrite existing episode text", "required": False, "default": False},
            ],
        },
        {
            "name": "auto_write_step",
            "description": (
                "Execute one or more LLM steps for an auto-write job using Anna's LLM via sampling. "
                "Each step is one planning or writing operation (Series plan, Arc plan, Mini Arc plan, "
                "Episode plan, or episode writing). "
                "Call repeatedly — up to ~270+ times for a full 500-episode novel — until done=true. "
                "A full novel requires roughly: 1 series + 5 arcs + 50 mini arcs + N episode plans + N×2 writes. "
                "Requires sampling context (must be called from an Anna session with sampling enabled)."
            ),
            "parameters": [
                {"name": "job_id", "type": "integer", "description": "Auto-write job id from start_auto_write", "required": True},
                {"name": "steps", "type": "integer", "description": "Max LLM steps per call (1-6, default 5). Each step = 1 LLM call.", "required": False, "default": 5},
            ],
        },
        {
            "name": "get_auto_write_job",
            "description": "Poll an auto-write job's status and progress.",
            "parameters": [
                {"name": "job_id", "type": "integer", "description": "Auto-write job id", "required": True},
            ],
        },
        {
            "name": "stop_auto_write",
            "description": "Request stop of a running auto-write job.",
            "parameters": [
                {"name": "job_id", "type": "integer", "description": "Auto-write job id", "required": True},
            ],
        },
        {
            "name": "list_auto_write_jobs",
            "description": "List all auto-write jobs for a work (including completed and stopped ones).",
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "list_plots",
            "description": "List plot arcs for a work (planned, active, resolved, …).",
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "create_plot",
            "description": "Add a plot arc to a work.",
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "title", "type": "string", "description": "Plot title", "required": True},
                {"name": "plot_type", "type": "string", "description": "arc / sub / twist / … (default arc)", "required": False},
                {"name": "status", "type": "string", "description": "planned / active / resolved (default planned)", "required": False},
                {"name": "start_episode", "type": "integer", "description": "Episode number where the arc begins", "required": False},
                {"name": "end_episode", "type": "integer", "description": "Episode number where the arc ends", "required": False},
                {"name": "objective", "type": "string", "description": "What needs to happen", "required": False},
                {"name": "conflict", "type": "string", "description": "The central conflict", "required": False},
                {"name": "resolution", "type": "string", "description": "How it resolves", "required": False},
            ],
        },
        {
            "name": "list_foreshadowings",
            "description": "List foreshadowing items for a work (open, fulfilled, …).",
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "create_foreshadowing",
            "description": "Add a foreshadowing item to a work.",
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "title", "type": "string", "description": "Foreshadowing title / label", "required": True},
                {"name": "description", "type": "string", "description": "What is foreshadowed", "required": False},
                {"name": "setup_episode", "type": "integer", "description": "Episode where it is set up", "required": False},
                {"name": "payoff_episode", "type": "integer", "description": "Episode where it pays off", "required": False},
                {"name": "status", "type": "string", "description": "open / fulfilled (default open)", "required": False},
            ],
        },
        {
            "name": "reflect_to_novel",
            "description": (
                "Re-sync entity data back into the novel. "
                "For characters: re-runs character-state extraction on the 3 most recent episodes. "
                "For plots / foreshadowings: re-runs the continuity checker. "
                "Use after manually editing characters, plots, or foreshadowings to keep the Story Twin consistent."
            ),
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {
                    "name": "kind",
                    "type": "string",
                    "description": "characters | plots | foreshadowings | all (default all)",
                    "required": False,
                    "default": "all",
                },
            ],
        },
        {
            "name": "list_covers",
            "description": "List cover images generated for a work. Each item includes filename, url, style, and created_at.",
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
            ],
        },
        {
            "name": "generate_cover_prompt",
            "description": (
                "Generate an English text-to-image prompt for a novel cover illustration "
                "using Anna's LLM, drawing on the project's synopsis, genre, recent episodes "
                "and characters. Returns a ready-to-use prompt string. "
                "Requires sampling context (must be called from an Anna session with sampling enabled)."
            ),
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {"name": "style", "type": "string", "description": "Art style hint: anime, realistic, watercolor, …", "required": False},
            ],
        },
        {
            "name": "add_ai_entities",
            "description": (
                "Generate and add story-knowledge rows (characters, world, glossary, plots, "
                "foreshadowings, timeline) to a project using Anna's LLM via reverse RPC sampling. "
                "Reads existing rows to avoid duplicates, then asks Anna to generate `count` new items "
                "and POSTs each one back to the INE API. "
                "Requires sampling context (must be called from an Anna session with sampling enabled)."
            ),
            "parameters": [
                {"name": "project_id", "type": "integer", "description": "INE project id", "required": True},
                {
                    "name": "kind",
                    "type": "string",
                    "description": "characters | world | glossary | plots | foreshadowings | timeline",
                    "required": True,
                },
                {"name": "count", "type": "integer", "description": "Number of rows to generate (default 10)", "required": False, "default": 10},
            ],
        },
        {
            "name": "proofread_episode",
            "description": (
                "Proofread an episode using the project's style guide and Anna's LLM via reverse RPC sampling. "
                "Returns a list of suggested corrections (original → suggested, with reason). "
                "With apply=true, saves all corrections back to the episode automatically. "
                "Requires a style guide to be set on the project first (use 「スタイルガイド生成」). "
                "Requires sampling context (must be called from an Anna session with sampling enabled)."
            ),
            "parameters": [
                {"name": "episode_id", "type": "integer", "description": "INE episode id", "required": True},
                {
                    "name": "apply",
                    "type": "boolean",
                    "description": "If true, save all corrections back to the episode (default false — preview only)",
                    "required": False,
                    "default": False,
                },
            ],
        },
    ],
}


def _log(message: str) -> None:
    print(f"[ine-bridge] {message}", file=sys.stderr)


# ── Anna sampling (reverse JSON-RPC 2.0) ──────────────────────────────────────
# Set to the sampling_token from the current invoke context; None outside invokes.
_sampling_token: str | None = None
_sampling_invoke_id: str | None = None
_sample_seq: list[int] = [0]


def _sample(
    messages: list[dict[str, Any]],
    *,
    system_prompt: str | None = None,
    max_tokens: int = 4096,
) -> str:
    """Send sampling/createMessage to Anna and return the assistant text.

    Blocks synchronously by reading stdin until the response arrives.
    Must only be called during an invoke (i.e. _sampling_token is set).
    """
    if _sampling_token is None:
        raise RuntimeError("Anna sampling not available in this invoke context")
    _sample_seq[0] += 1
    req_id = f"sample-{_sample_seq[0]}-{int(time.time() * 1000)}"
    params: dict[str, Any] = {
        "messages": messages,
        "maxTokens": max_tokens,
        "sampling_token": _sampling_token,
        "metadata": {"invoke_id": _sampling_invoke_id} if _sampling_invoke_id else {},
    }
    if system_prompt:
        params["systemPrompt"] = system_prompt
    send({"jsonrpc": "2.0", "id": req_id, "method": "sampling/createMessage", "params": params})
    # Read stdin until the matching response arrives.
    while True:
        raw = sys.stdin.readline()
        if not raw:
            raise RuntimeError("stdin closed while waiting for Anna sampling response")
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == req_id:
            if "error" in msg:
                err = msg["error"]
                raise RuntimeError(f"sampling error {err.get('code')}: {err.get('message')}")
            return msg["result"]["content"]["text"]
        _log(f"unexpected message during sampling (id={msg.get('id')}), buffering")
        # Push back: prepend to a small buffer read by the main loop after this invoke finishes.
        _inbox_buffer.append(raw)


# Lines received out-of-band during a sampling call, to be processed after invoke returns.
_inbox_buffer: list[str] = []


def _fetch_context(
    credentials: dict[str, Any] | None,
    project_id: int,
    *,
    episode_id: int | None = None,
    rag_query: str | None = None,
    rag_limit: int = 6,
) -> dict[str, Any]:
    """Fetch story context from INE REST API — mirrors the backend's build() function."""
    characters = ine_call(credentials, "GET", f"/projects/{project_id}/characters") or []
    world = ine_call(credentials, "GET", f"/projects/{project_id}/world") or []
    plots = ine_call(credentials, "GET", f"/projects/{project_id}/plots") or []
    foreshadowings = ine_call(credentials, "GET", f"/projects/{project_id}/foreshadowings") or []
    episode: dict[str, Any] | None = None
    if episode_id:
        try:
            episode = ine_call(credentials, "GET", f"/episodes/{episode_id}")
        except Exception:
            pass
    rag: list[Any] = []
    if rag_query:
        try:
            result = ine_call(
                credentials, "POST", "/rag/search",
                json_body={"project_id": project_id, "query": rag_query, "limit": max(1, min(rag_limit, 20))},
            )
            rag = result.get("results", result) if isinstance(result, dict) else (result or [])
        except Exception:
            pass
    return {
        "characters": characters[:30],
        "world": world[:30],
        "plots": plots[:15],
        "foreshadowings": foreshadowings[:15],
        "rag": rag,
        "episode": episode,
    }


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
        or "https://neomedia.dynv6.net:6556"
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


_TASK_LABEL = {
    "continue": "本文の続きを書く",
    "summary": "本文を要約する",
    "plot": "次の展開を提案する",
    "proofread": "設定・表現・時系列を校正する",
}
_GENERATE_SYSTEM = (
    "あなたは長編小説の編集長AIです。作品の正本設定を最優先してください。"
)


def tool_generate(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    mode = (args.get("mode") or "continue").strip()
    allowed = set(_TASK_LABEL)
    if mode not in allowed:
        raise ValueError(f"mode must be one of {sorted(allowed)}")
    rag_limit = _int(args.get("rag_limit"), "rag_limit", required=False, default=6) or 6
    instruction = args.get("instruction") or ""
    episode_id = _int(args.get("episode_id"), "episode_id", required=False)

    if _sampling_token is not None:
        ctx = _fetch_context(
            credentials, pid,
            episode_id=episode_id,
            rag_query=instruction or "recent story context",
            rag_limit=rag_limit,
        )
        task = _TASK_LABEL.get(mode, "依頼を実行する")
        user_text = (
            f"作業: {task}\n\n"
            f"Context:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}\n\n"
            f"指示: {instruction or '続きを書いてください。'}\n"
            "日本語で出力してください。"
        )
        text = _sample(
            [{"role": "user", "content": {"type": "text", "text": user_text}}],
            system_prompt=_GENERATE_SYSTEM,
            max_tokens=4096,
        )
        return {
            "text": text,
            "model": "anna",
            "context": {
                "characters": len(ctx["characters"]),
                "world": len(ctx["world"]),
                "plots": len(ctx["plots"]),
                "foreshadowings": len(ctx["foreshadowings"]),
                "rag": len(ctx["rag"]),
            },
            "source": "anna_sampling",
        }

    body = _omit_none(
        {
            "project_id": pid,
            "episode_id": episode_id,
            "instruction": instruction,
            "mode": mode,
            "rag_limit": rag_limit,
        }
    )
    return ine_call(credentials, "POST", "/ai/generate", json_body=body, timeout=120)


def tool_chat(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    content = (args.get("content") or "").strip()
    if not content:
        raise ValueError("content is required")

    if _sampling_token is not None:
        ctx = _fetch_context(credentials, pid, rag_query=content, rag_limit=8)
        user_text = (
            f"Context:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}\n\n"
            f"質問: {content}\n"
            "日本語で出力してください。"
        )
        text = _sample(
            [{"role": "user", "content": {"type": "text", "text": user_text}}],
            system_prompt="あなたは長編小説のAIチャットアシスタントです。作品の正本設定を最優先してください。",
            max_tokens=2048,
        )
        return [
            {"role": "user", "content": content},
            {"role": "assistant", "content": text, "source": "anna_sampling"},
        ]

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


def tool_list_auto_write_jobs(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    return ine_call(credentials, "GET", f"/projects/{pid}/auto-write/jobs")


def tool_auto_write_step(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    """Execute LLM steps for an auto-write job using Anna sampling.

    Calls GET next-step → _sample() → POST submit-step up to `steps` times.
    Call repeatedly until done=true is returned.
    """
    if _sampling_token is None:
        raise RuntimeError(
            "Anna LLM sampling is required for auto_write_step. "
            "This tool must be called from an Anna session with sampling enabled."
        )

    job_id = _int(args.get("job_id"), "job_id")
    max_steps = min(_int(args.get("steps"), "steps", required=False, default=5) or 5, 6)
    steps_done = 0

    for _ in range(max_steps):
        next_step = ine_call(credentials, "GET", f"/auto-write/{job_id}/next-step")

        if next_step.get("done"):
            return {
                "done": True,
                "status": next_step.get("status", "completed"),
                "steps_done": steps_done,
            }

        step_id = next_step.get("step_id")
        prompt = next_step.get("prompt", "")
        max_tokens = next_step.get("max_tokens", 4096)

        result_text = _sample(
            [{"role": "user", "content": {"type": "text", "text": prompt}}],
            max_tokens=max_tokens,
        )

        ine_call(credentials, "POST", f"/auto-write/{job_id}/submit-step",
                 json_body={"step_id": step_id, "result": result_text})
        steps_done += 1

    job = ine_call(credentials, "GET", f"/auto-write/{job_id}")
    return {
        "done": False,
        "steps_done": steps_done,
        "progress_percent": job.get("progress_percent", 0),
        "current_phase": job.get("current_phase", ""),
        "current_episode": job.get("current_episode", 0),
        "last_message": job.get("last_message", ""),
    }


def tool_list_plots(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    return ine_call(credentials, "GET", f"/projects/{pid}/plots")


def tool_create_plot(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    title = (args.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    body = _omit_none(
        {
            "title": title,
            "plot_type": args.get("plot_type"),
            "status": args.get("status"),
            "start_episode": _int(args.get("start_episode"), "start_episode", required=False),
            "end_episode": _int(args.get("end_episode"), "end_episode", required=False),
            "objective": args.get("objective"),
            "conflict": args.get("conflict"),
            "resolution": args.get("resolution"),
        }
    )
    return ine_call(credentials, "POST", f"/projects/{pid}/plots", json_body=body)


def tool_list_foreshadowings(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    return ine_call(credentials, "GET", f"/projects/{pid}/foreshadowings")


def tool_create_foreshadowing(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    title = (args.get("title") or "").strip()
    if not title:
        raise ValueError("title is required")
    body = _omit_none(
        {
            "title": title,
            "description": args.get("description"),
            "setup_episode": _int(args.get("setup_episode"), "setup_episode", required=False),
            "payoff_episode": _int(args.get("payoff_episode"), "payoff_episode", required=False),
            "status": args.get("status"),
        }
    )
    return ine_call(credentials, "POST", f"/projects/{pid}/foreshadowings", json_body=body)


def tool_reflect_to_novel(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    pid = _int(args.get("project_id"), "project_id")
    kind = (args.get("kind") or "all").strip()
    allowed = {"characters", "plots", "foreshadowings", "all"}
    if kind not in allowed:
        raise ValueError(f"kind must be one of {sorted(allowed)}")
    return ine_call(credentials, "POST", f"/projects/{pid}/reflect-to-novel", json_body={"kind": kind}, timeout=60)


def tool_list_covers(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    """Return cover images for a project, each with url and metadata."""
    pid = _int(args.get("project_id"), "project_id")
    covers = ine_call(credentials, "GET", f"/projects/{pid}/covers") or []
    base_url = (credentials or {}).get("INE_BASE_URL") or "http://localhost:8000"
    base_url = base_url.rstrip("/")
    for c in covers:
        filename = c.get("filename") or c.get("file") or ""
        if filename and not c.get("url"):
            c["url"] = f"{base_url}/api/v1/projects/{pid}/covers/{filename}"
    return covers


_COVER_PROMPT_SYSTEM = (
    "You are an art director for a published novel. Write ONE English text-to-image prompt "
    "for its book-cover illustration: a single striking key scene or symbolic image that "
    "captures the story's genre, mood and protagonist. "
    "Requirements: vertical 2:3 composition, painterly/cinematic professional book-cover quality, "
    "leave calm space in the upper third for a title, and absolutely NO text, letters, or "
    "typography in the image. Output only the prompt (comma-separated phrases, under 120 words)."
)


def tool_generate_cover_prompt(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    if _sampling_token is None:
        raise RuntimeError(
            "Anna LLM sampling is required for generate_cover_prompt. "
            "This tool must be called from an Anna session with sampling enabled."
        )
    pid = _int(args.get("project_id"), "project_id")
    style = (args.get("style") or "").strip()

    project = ine_call(credentials, "GET", f"/projects/{pid}")
    episodes = ine_call(
        credentials, "GET", f"/projects/{pid}/episodes",
        query={"limit": 5, "offset": max(0, (project.get("episode_count") or 0) - 5)},
    ) or []
    if isinstance(episodes, dict):
        episodes = episodes.get("episodes") or episodes.get("items") or []
    characters = ine_call(credentials, "GET", f"/projects/{pid}/characters") or []

    lines = [
        f"Title: {project.get('name', '')}",
        f"Genre: {project.get('genre', '')}",
        f"Synopsis: {project.get('description', '')}",
    ]
    if characters:
        ch_names = ", ".join(c.get("name", "") for c in characters[:6] if c.get("name"))
        lines.append(f"Main characters: {ch_names}")
    if episodes:
        ep_summaries = "; ".join(
            e.get("summary") or e.get("title") or ""
            for e in episodes[-3:]
            if e.get("summary") or e.get("title")
        )
        lines.append(f"Recent episodes: {ep_summaries}")
    if style:
        lines.append(f"Art style: {style}")

    user_text = "\n".join(lines)
    prompt_text = _sample(
        [{"role": "user", "content": {"type": "text", "text": user_text}}],
        system_prompt=_COVER_PROMPT_SYSTEM,
        max_tokens=300,
    )
    return {
        "prompt": (prompt_text or "").strip().strip('"'),
        "project_id": pid,
        "style": style,
        "source": "anna_sampling",
    }


def tool_check_cover_services(_args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    """Diagnostic: report available image-generation services in the runtime environment."""
    env_vars: dict[str, str] = {}
    for key in sorted(os.environ):
        if any(word in key.lower() for word in ("anna", "image", "llm", "api_url", "comfy", "higgs")):
            env_vars[key] = "<設定済み>" if os.environ[key] else "<空>"

    cover_config: Any = None
    try:
        cover_config = ine_call(credentials, "GET", "/cover/config")
    except Exception as exc:
        cover_config = {"error": str(exc)}

    return {
        "python_version": sys.version,
        "relevant_env_vars": env_vars,
        "ine_cover_config": cover_config,
    }


def tool_generate_cover(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    """Generate a cover image for a project.

    If *prompt* is omitted and Anna sampling is available, a prompt is
    auto-generated from the project's story context via Anna's LLM.
    The image is rendered by the INE server using ComfyUI or Higgsfield.
    """
    pid = _int(args.get("project_id"), "project_id")
    prompt = (args.get("prompt") or "").strip()
    style = (args.get("style") or "").strip()
    provider = (args.get("provider") or "comfyui").strip()
    prompt_source = "provided"

    if not prompt:
        if _sampling_token is None:
            raise RuntimeError(
                "prompt パラメーターが必要です。または Anna チャットから呼び出して LLM で自動生成してください。"
            )
        project = ine_call(credentials, "GET", f"/projects/{pid}")
        episodes = ine_call(
            credentials, "GET", f"/projects/{pid}/episodes",
            query={"limit": 5, "offset": max(0, (project.get("episode_count") or 0) - 5)},
        ) or []
        if isinstance(episodes, dict):
            episodes = episodes.get("episodes") or episodes.get("items") or []
        characters = ine_call(credentials, "GET", f"/projects/{pid}/characters") or []

        lines = [
            f"Title: {project.get('name', '')}",
            f"Genre: {project.get('genre', '')}",
            f"Synopsis: {project.get('description', '')}",
        ]
        if characters:
            ch_names = ", ".join(c.get("name", "") for c in characters[:6] if c.get("name"))
            lines.append(f"Main characters: {ch_names}")
        if isinstance(episodes, list) and episodes:
            ep_summaries = "; ".join(
                e.get("summary") or e.get("title") or ""
                for e in episodes[-3:]
                if e.get("summary") or e.get("title")
            )
            if ep_summaries:
                lines.append(f"Recent episodes: {ep_summaries}")
        if style:
            lines.append(f"Art style: {style}")

        prompt = _sample(
            [{"role": "user", "content": {"type": "text", "text": "\n".join(lines)}}],
            system_prompt=_COVER_PROMPT_SYSTEM,
            max_tokens=300,
        )
        prompt = (prompt or "").strip().strip('"')
        prompt_source = "anna_sampling"

    if not prompt:
        raise ValueError("プロンプトを生成できませんでした。prompt パラメーターを直接指定してください。")

    job = ine_call(
        credentials, "POST", f"/projects/{pid}/cover/generate",
        json_body={"prompt": prompt, "style": style, "provider": provider, "overlay": False},
        timeout=30,
    )
    job_id = job.get("id")
    if not job_id:
        raise RuntimeError(f"ジョブの作成に失敗しました: {job}")

    _log(f"generate_cover: job {job_id} started pid={pid} provider={provider}")

    for _ in range(120):  # poll up to 10 minutes
        time.sleep(5)
        status = ine_call(credentials, "GET", f"/cover-jobs/{job_id}")
        st = status.get("status", "")
        if st in ("completed", "error", "cancelled"):
            base_url = ((credentials or {}).get("INE_BASE_URL") or "http://localhost:8000").rstrip("/")
            result: dict[str, Any] = {
                "project_id": pid,
                "job_id": job_id,
                "status": st,
                "filename": status.get("filename"),
                "prompt": prompt,
                "style": style,
                "provider": provider,
                "message": status.get("last_message", ""),
                "prompt_source": prompt_source,
            }
            if status.get("filename"):
                result["url"] = f"{base_url}/api/v1/projects/{pid}/covers/{status['filename']}"
            return result

    return {
        "job_id": job_id,
        "status": "timeout",
        "message": "10 分以内に完了しませんでした。cover-jobs/{id} で状態を確認してください。",
        "prompt": prompt,
    }


_AI_ENTITY_KINDS: dict[str, dict] = {
    "characters": {
        "label": "キャラクター",
        "list_path": "/characters",
        "create_path": "/characters",
        "key": "name",
        "fields": {
            "name": "名前",
            "role": "役割（主人公・ライバル等）",
            "personality": "性格",
            "speech_style": "口調",
            "goal": "目標",
            "status": "alive / dead / missing / unknown のいずれか",
            "description": "補足",
        },
        "choices": {"status": ["alive", "dead", "missing", "unknown"]},
        "defaults": {"status": "alive"},
    },
    "world": {
        "label": "世界観",
        "list_path": "/world",
        "create_path": "/world",
        "key": "name",
        "fields": {
            "name": "名称",
            "entity_type": "setting / location / technology / magic / organization / item のいずれか",
            "description": "説明",
            "rules": "ルール",
            "location": "場所",
            "era": "時代",
        },
        "choices": {"entity_type": ["setting", "location", "technology", "magic", "organization", "item"]},
        "defaults": {"entity_type": "setting"},
        "filter": lambda r: r.get("entity_type") != "glossary",
    },
    "glossary": {
        "label": "用語集",
        "list_path": "/world",
        "create_path": "/world",
        "key": "name",
        "fields": {"name": "用語", "description": "説明", "location": "カテゴリ"},
        "choices": {},
        "defaults": {"entity_type": "glossary"},
        "filter": lambda r: r.get("entity_type") == "glossary",
    },
    "plots": {
        "label": "プロット",
        "list_path": "/plots",
        "create_path": "/plots",
        "key": "title",
        "fields": {
            "title": "タイトル",
            "plot_type": "main_arc / arc / subplot のいずれか",
            "status": "planned / active / completed のいずれか",
            "start_episode": "開始話数（整数）",
            "end_episode": "終了話数（整数）",
            "objective": "目的",
            "conflict": "対立",
            "resolution": "決着",
        },
        "choices": {"plot_type": ["main_arc", "arc", "subplot"], "status": ["planned", "active", "completed"]},
        "defaults": {"plot_type": "arc", "status": "planned"},
        "ints": ("start_episode", "end_episode"),
    },
    "foreshadowings": {
        "label": "伏線",
        "list_path": "/foreshadowings",
        "create_path": "/foreshadowings",
        "key": "title",
        "fields": {
            "title": "タイトル",
            "description": "説明",
            "setup_episode": "設置話数（整数）",
            "payoff_episode": "回収話数（整数）",
            "status": "open / resolved / abandoned のいずれか",
        },
        "choices": {"status": ["open", "resolved", "abandoned"]},
        "defaults": {"status": "open"},
        "ints": ("setup_episode", "payoff_episode"),
    },
    "timeline": {
        "label": "年表",
        "list_path": "/timeline",
        "create_path": "/timeline",
        "key": "title",
        "fields": {
            "episode_number": "話数（整数）",
            "title": "出来事",
            "world_time": "世界内時間",
            "description": "説明",
        },
        "choices": {},
        "defaults": {"episode_number": 1},
        "ints": ("episode_number",),
    },
}


def _ai_entity_clean(spec: dict, raw: dict) -> dict | None:
    row = dict(spec["defaults"])
    for k, hint in spec["fields"].items():
        if k not in raw or raw[k] is None:
            continue
        v = raw[k]
        if k in spec.get("ints", ()):
            try:
                row[k] = int(v)
            except (TypeError, ValueError):
                pass
        else:
            v = str(v).strip()
            if k in spec["choices"] and v not in spec["choices"][k]:
                continue
            row[k] = v
    key = spec["key"]
    return row if row.get(key) not in (None, "") else None


def tool_add_ai_entities(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    if _sampling_token is None:
        raise RuntimeError(
            "Anna LLM sampling is required for add_ai_entities. "
            "This tool must be called from an Anna session with sampling enabled."
        )
    pid = _int(args.get("project_id"), "project_id")
    kind = (args.get("kind") or "").strip()
    if kind not in _AI_ENTITY_KINDS:
        raise ValueError(f"kind must be one of: {', '.join(_AI_ENTITY_KINDS)}")
    count = max(1, min(_int(args.get("count"), "count", required=False, default=10) or 10, 30))
    spec = _AI_ENTITY_KINDS[kind]

    project = ine_call(credentials, "GET", f"/projects/{pid}")
    existing_raw = ine_call(credentials, "GET", f"/projects/{pid}{spec['list_path']}") or []
    if isinstance(existing_raw, dict):
        existing_raw = existing_raw.get("items") or existing_raw.get(kind) or []
    filt = spec.get("filter")
    existing = [r for r in existing_raw if (filt is None or filt(r))]

    key_field = spec["key"]
    seen = {(r.get(key_field) or "").strip().lower() for r in existing if r.get(key_field)}
    existing_names = [str(r.get(key_field, "")) for r in existing[:120]]

    chars: list[str] = []
    if kind != "characters":
        char_list = ine_call(credentials, "GET", f"/projects/{pid}/characters") or []
        chars = [c.get("name", "") for c in char_list[:40] if c.get("name")]

    fields_text = "\n".join(f"- {k}: {hint}" for k, hint in spec["fields"].items())
    existing_text = ", ".join(existing_names) if existing_names else "（なし）"
    chars_text = ", ".join(chars) if chars else "（なし）"
    prompt = (
        f"あなたは長編小説の設定編集者です。次の作品に追加する「{spec['label']}」の新しい案を{count}件、考えてください。\n"
        f"作品名: {project.get('name', '')}\n"
        f"ジャンル: {project.get('genre', '')}\n"
        f"あらすじ: {project.get('description', '')}\n"
        f"ルール・方針: {project.get('rules', '')}\n"
        f"既存の登場人物: {chars_text}\n"
        f"既存の{spec['label']}（これらと重複しないこと）: {existing_text}\n\n"
        "出力はJSON配列のみ（前置き・説明・コードブロック不要）。各要素は次のキーを持つオブジェクトにしてください。\n"
        f"{fields_text}"
    )

    result_text = _sample(
        [{"role": "user", "content": {"type": "text", "text": prompt}}],
        max_tokens=4096,
    )

    match = re.search(r"\[.*\]", result_text or "", re.DOTALL)
    raw_rows: list[dict] = []
    if match:
        try:
            raw_rows = json.loads(match.group(0))
            if not isinstance(raw_rows, list):
                raw_rows = []
        except Exception:
            raw_rows = []

    created = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        row = _ai_entity_clean(spec, raw)
        if row is None:
            continue
        name_val = (row.get(key_field) or "").strip().lower()
        if name_val in seen:
            continue
        seen.add(name_val)
        try:
            ine_call(credentials, "POST", f"/projects/{pid}{spec['create_path']}", json_body=row)
            created.append(row.get(key_field, ""))
        except Exception as exc:
            _log(f"add_ai_entities: failed to create {row}: {exc}")
        if len(created) >= count:
            break

    return {
        "kind": kind,
        "project_id": pid,
        "created": len(created),
        "items": created,
        "source": "anna_sampling",
    }


def _build_proofread_prompt(style_guide: str, content: str) -> str:
    return (
        "あなたは日本語の校正者です。以下のスタイルガイドに従って本文を校正し、修正すべき箇所だけを列挙してください。\n\n"
        f"スタイルガイド:\n{style_guide}\n\n"
        f"本文:\n{content}\n\n"
        "出力は必ず次のJSON配列のみとし、他の説明文は一切含めないでください。修正不要なら空配列 [] を返してください。\n"
        '[{"original": "本文中に完全一致する修正対象の原文", "suggested": "修正後の文字列", "reason": "修正理由（簡潔に）"}]'
    )


def _parse_proofread_diffs(text: str, content: str) -> list[dict[str, str]]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    try:
        raw = json.loads(match.group(0) if match else text)
    except Exception:
        raw = []
    return [
        {"original": d.get("original", ""), "suggested": d.get("suggested", ""), "reason": d.get("reason", "")}
        for d in raw
        if isinstance(d, dict) and d.get("original") and d.get("original") in content
    ]


def tool_proofread_episode(args: dict[str, Any], credentials: dict[str, Any] | None) -> Any:
    if _sampling_token is None:
        raise RuntimeError(
            "Anna LLM sampling is required for proofread_episode. "
            "This tool must be called from an Anna session with sampling enabled."
        )
    eid = _int(args.get("episode_id"), "episode_id")
    apply_diffs = _bool(args.get("apply"), default=False)

    episode = ine_call(credentials, "GET", f"/episodes/{eid}")
    pid = episode.get("project_id")
    if pid is None:
        raise ValueError("episode has no project_id")

    project = ine_call(credentials, "GET", f"/projects/{pid}")
    style_guide = (project.get("style_guide") or "").strip()
    if not style_guide:
        raise ValueError(
            "スタイルガイドが設定されていません。先に「スタイルガイド生成」で作成してください。"
        )

    content = (episode.get("content") or "").strip()
    if not content:
        return {"diffs": [], "applied": 0, "message": "本文が空のため校正できません。"}

    prompt = _build_proofread_prompt(style_guide, content)
    result_text = _sample(
        [{"role": "user", "content": {"type": "text", "text": prompt}}],
        max_tokens=4096,
    )

    diffs = _parse_proofread_diffs(result_text, content)

    applied = 0
    if apply_diffs and diffs:
        new_content = content
        for d in diffs:
            new_content = new_content.replace(d["original"], d["suggested"], 1)
        if new_content != content:
            ine_call(credentials, "PUT", f"/episodes/{eid}", json_body={"content": new_content}, timeout=60)
            applied = len(diffs)

    return {
        "episode_id": eid,
        "episode_title": episode.get("title", ""),
        "diffs": diffs,
        "diff_count": len(diffs),
        "applied": applied,
        "source": "anna_sampling",
    }


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
    "auto_write_step": tool_auto_write_step,
    "get_auto_write_job": tool_get_auto_write_job,
    "stop_auto_write": tool_stop_auto_write,
    "list_auto_write_jobs": tool_list_auto_write_jobs,
    "list_plots": tool_list_plots,
    "create_plot": tool_create_plot,
    "list_foreshadowings": tool_list_foreshadowings,
    "create_foreshadowing": tool_create_foreshadowing,
    "reflect_to_novel": tool_reflect_to_novel,
    "list_covers": tool_list_covers,
    "generate_cover_prompt": tool_generate_cover_prompt,
    "check_cover_services": tool_check_cover_services,
    "generate_cover": tool_generate_cover,
    "add_ai_entities": tool_add_ai_entities,
    "proofread_episode": tool_proofread_episode,
}


def handle_describe(_params: dict[str, Any]) -> dict[str, Any]:
    return MANIFEST


def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocolVersion": "2.0",
        "server_info": {"name": MANIFEST["display_name"], "version": MANIFEST["version"]},
        "capabilities": {},
        "client_capabilities": {"sampling": {}},
    }


def handle_invoke(params: dict[str, Any]) -> dict[str, Any]:
    global _sampling_token, _sampling_invoke_id
    if not isinstance(params, dict):
        return {"success": False, "error": "params must be an object"}
    tool_name = params.get("tool")
    args = params.get("arguments") or {}
    ctx = params.get("context") or {}
    # sampling_token and invoke_id are at params top-level (protocol v2).
    _sampling_token = params.get("sampling_token") or ctx.get("sampling_token") or None
    _sampling_invoke_id = params.get("invoke_id") or ctx.get("invoke_id") or None
    try:
        if not isinstance(args, dict):
            raise ValueError("`arguments` must be an object")
        credentials = ctx.get("credentials") or {}
        fn = TOOL_DISPATCH.get(tool_name)
        if fn is None:
            raise ValueError(f"unknown tool: {tool_name!r}")
        payload = fn(args, credentials)
    except Exception as exc:  # noqa: BLE001 — surface as InvokeResult, not a transport crash
        _log(f"{tool_name} failed: {type(exc).__name__}")
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        _sampling_token = None
        _sampling_invoke_id = None
    return {"success": True, "data": payload}


def handle_health(_params: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ready"}


METHOD_DISPATCH = {
    "initialize": handle_initialize,
    "describe": handle_describe,
    "invoke": handle_invoke,
    "health": handle_health,
}


def send(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _process_line(line: str) -> None:
    line = line.strip()
    if not line:
        return
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"parse error: {exc}"}})
        return
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    handler = METHOD_DISPATCH.get(method)
    if handler is None:
        send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"method not found: {method}"}})
        return
    try:
        result = handler(params)
        send({"jsonrpc": "2.0", "id": req_id, "result": result})
    except Exception as exc:  # noqa: BLE001
        send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(exc)}})


def main() -> None:
    _log(f"{MANIFEST['display_name']} v{MANIFEST['version']} ready")
    while True:
        # Drain any lines buffered by _sample() during a previous invoke.
        while _inbox_buffer:
            _process_line(_inbox_buffer.pop(0))
        raw = sys.stdin.readline()
        if not raw:
            break
        _process_line(raw)


if __name__ == "__main__":
    main()
