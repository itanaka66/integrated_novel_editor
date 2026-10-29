# INE Bridge

**Anna Executa Plugin** — v0.2.14

Connect Anna to a local Integrated Novel Editor instance. List works, manage story structure, generate prose and cover art, and run fully automated novel-writing jobs using Anna's own LLM.

---

## Overview

INE Bridge is a JSON-RPC 2.0 stdio plugin (Executa) that lets Anna talk to a running **Integrated Novel Editor** API. It exposes tools for browsing and editing novel projects, and for using Anna's own LLM — via reverse-RPC sampling — to generate, proofread, and automatically write long-form fiction.

The plugin is a single Python file (`anna/executas/ine-bridge/ine_plugin.py`) packaged as a self-contained binary. It uses only the standard library plus `uv` for the runtime; no extra dependencies are needed.

**What you can do:**

| 機能 | 説明 |
|------|------|
| Browse | List and search projects, episodes, characters, and world entities |
| Edit | Create and update episodes, characters, plots, and foreshadowings |
| Generate | Continue prose, chat about the story, and run the continuity audit |
| Auto-write | Plan and write a 500-episode novel autonomously with Anna's LLM |
| Covers | Generate cover images via ComfyUI or Higgsfield, with LLM-authored prompts |
| Reflect | Sync manually-edited entities back into the Story Digital Twin |

---

## Setup & Credentials

Anna installs the plugin automatically when you add it as an Executa. Three credential fields are available:

| Credential | Required | Description |
|------------|----------|-------------|
| `INE_BASE_URL` | Optional | Base URL of the INE API, without trailing slash. Defaults to `http://localhost:8000`. Set to your remote URL (e.g. `https://neomedia.dynv6.net:6556`) if INE is running on another machine. |
| `INE_USERNAME` | **Required** | HTTP Basic auth username — the same account you use to log into the INE web app. |
| `INE_PASSWORD` | **Required** | HTTP Basic auth password. Stored as a sensitive credential; Anna does not log or display it. |

Credentials can also be provided as environment variables with the same names, which is useful when running the binary directly for testing.

---

## Protocol

INE Bridge speaks **JSON-RPC 2.0 over stdio**. Anna launches the binary, writes newline-delimited JSON requests to its stdin, and reads responses from stdout. Logs (prefixed `[ine-bridge]`) go to stderr and never appear on stdout.

### Methods

```
initialize   → handshake, declares sampling capability
describe     → returns the full MANIFEST (tool list, credentials, version)
invoke       → calls a named tool with arguments and credentials
health       → lightweight ready-check (no auth needed)
```

### invoke request shape

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "invoke",
  "params": {
    "tool": "list_episodes",
    "arguments": { "project_id": 42, "limit": 20 },
    "context": {
      "credentials": {
        "INE_BASE_URL": "https://…",
        "INE_USERNAME": "alice",
        "INE_PASSWORD": "secret"
      },
      "sampling_token": "…"
    }
  }
}
```

### invoke response shape

```json
// success
{ "jsonrpc": "2.0", "id": "1", "result": { "success": true, "data": { … } } }

// error
{ "jsonrpc": "2.0", "id": "1", "result": { "success": false, "error": "ValueError: …" } }
```

---

## Anna Sampling (Reverse RPC)

Several tools use Anna's own LLM rather than the INE server's LLM. They do this by sending a `sampling/createMessage` request back to Anna over the same stdio connection while handling an `invoke`.

> **Requires sampling context.** Tools marked `[sampling]` below only work when called from an active Anna chat session. They raise a `RuntimeError` if no `sampling_token` is present in the invoke context.

```
1. Anna calls invoke
   → 2. Plugin sends sampling/createMessage
      → 3. Anna's LLM responds
         → 4. Plugin continues tool logic
            → 5. invoke result returned
```

The plugin blocks synchronously on stdin while waiting for the sampling response. Any other JSON-RPC messages that arrive on stdin during this wait are buffered and processed after the invoke completes.

**Tools that use sampling:** `generate`, `chat`, `auto_write_step`, `generate_cover_prompt`, `generate_cover`, `add_ai_entities`, `proofread_episode`

---

## Tool Reference

### Project Tools

#### `health`
Ping the INE API. Auth is optional.

*(No parameters)*

---

#### `list_projects`
List all INE works: id, name, genre, description.

*(No parameters)*

---

#### `get_project`
Get one INE work by project_id.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |

---

#### `create_project`
Create a new INE work.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Work title |
| `description` | string | No | Synopsis |
| `genre` | string | No | Genre |
| `rules` | string | No | Hard setting rules the AI must obey |
| `language` | string | No | ISO language code (default `ja`) |
| `author` | string | No | Author name |
| `episode_goal` | integer | No | Target episode count (default 500) |

---

#### `get_story_twin`
Story Digital Twin: health score, coverage, continuity, plots. Graphs omitted unless `include_graphs=true`.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `include_graphs` | boolean | No | Include character/world/timeline graphs (large payload) |

---

### Episode Tools

#### `list_episodes`
List episodes of a work (paginated). Returns up to 200 per page.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `limit` | integer | No | Page size (default 50, max 200) |
| `offset` | integer | No | Offset (default 0) |

---

#### `get_episode`
Get one episode including full Markdown content.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `episode_id` | integer | Yes | INE episode id |

---

#### `create_episode`
Add an episode to a work.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `number` | integer | Yes | Episode number |
| `title` | string | Yes | Episode title |
| `summary` | string | No | Short summary |
| `content` | string | No | Markdown body |
| `chapter` | string | No | Chapter label |

---

#### `save_episode`
Update an episode. Also snapshots a revision and may update character state.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `episode_id` | integer | Yes | INE episode id |
| `title` | string | No | Episode title |
| `summary` | string | No | Short summary |
| `content` | string | No | Markdown body |
| `chapter` | string | No | Chapter label |

---

#### `search`
Semantic (RAG) search over episode text, with PostgreSQL substring fallback.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `query` | string | Yes | Search query |
| `limit` | integer | No | Max hits (default 8, max 40) |

---

### Characters & World Tools

#### `list_characters`
List characters for a work.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |

---

#### `create_character`
Add a character to a work.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `name` | string | Yes | Character name |
| `role` | string | No | protagonist, ally, antagonist, … |
| `personality` | string | No | Personality |
| `speech_style` | string | No | Speech style |
| `goal` | string | No | Goal |
| `status` | string | No | `alive` / `dead` / `missing` / `unknown` |
| `description` | string | No | Notes |

---

#### `list_world`
List world entities (places, tech, glossary, …) for a work.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |

---

#### `create_world`
Add a world entity.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `name` | string | Yes | Entity name |
| `entity_type` | string | No | `setting` / `location` / `technology` / `glossary` / `magic` / `organization` / `item` |
| `description` | string | No | Description |
| `rules` | string | No | Hard rules |
| `location` | string | No | Location |
| `era` | string | No | Era |

---

#### `add_ai_entities` `[sampling]`
Generate and add story-knowledge rows (characters, world, glossary, plots, foreshadowings, timeline) using Anna's LLM. Reads existing rows to avoid duplicates.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `kind` | string | Yes | `characters` / `world` / `glossary` / `plots` / `foreshadowings` / `timeline` |
| `count` | integer | No | Number of rows to generate (default 10, max 30) |

---

### Story Structure Tools

#### `list_plots`
List plot arcs for a work (planned, active, resolved, …).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |

---

#### `create_plot`
Add a plot arc to a work.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `title` | string | Yes | Plot title |
| `plot_type` | string | No | `arc` / `sub` / `twist` / … (default `arc`) |
| `status` | string | No | `planned` / `active` / `resolved` (default `planned`) |
| `start_episode` | integer | No | Episode number where the arc begins |
| `end_episode` | integer | No | Episode number where the arc ends |
| `objective` | string | No | What needs to happen |
| `conflict` | string | No | The central conflict |
| `resolution` | string | No | How it resolves |

---

#### `list_foreshadowings`
List foreshadowing items for a work (open, fulfilled, …).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |

---

#### `create_foreshadowing`
Add a foreshadowing item to a work.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `title` | string | Yes | Foreshadowing title / label |
| `description` | string | No | What is foreshadowed |
| `setup_episode` | integer | No | Episode where it is set up |
| `payoff_episode` | integer | No | Episode where it pays off |
| `status` | string | No | `open` / `fulfilled` (default `open`) |

---

#### `check_continuity`
Run INE's continuity audit (timeline, character, world, foreshadowing).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `episode_id` | integer | No | Optional episode to focus the audit |

---

#### `list_continuity_issues`
List stored open/recent continuity issues for a work.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |

---

#### `reflect_to_novel`
Re-sync entity data back into the novel after manual edits. Characters: re-extracts state from 3 most recent episodes. Plots/foreshadowings: re-runs the continuity checker.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `kind` | string | No | `characters` / `plots` / `foreshadowings` / `all` (default `all`) |

---

### AI Generation Tools

#### `generate` `[sampling]`
Use Anna's LLM (or the INE server's LLM if sampling is not available) to continue, summarize, plot, or proofread using the project's Story Digital Twin as context.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `episode_id` | integer | No | Episode to ground the prompt |
| `instruction` | string | No | Extra instruction |
| `mode` | string | No | `continue` / `summary` / `plot` / `proofread` (default `continue`) |
| `rag_limit` | integer | No | RAG snippets to include (default 6) |

---

#### `chat` `[sampling]`
Send a chat turn about a work. INE persists chat history; responses use the project's story context.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `content` | string | Yes | User message |

---

#### `proofread_episode` `[sampling]`
Proofread an episode using the project's style guide. Returns corrections. With `apply=true`, saves them all. Requires a style guide to be set on the project.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `episode_id` | integer | Yes | INE episode id |
| `apply` | boolean | No | If true, save all corrections to the episode (default `false`) |

---

### Auto-write Tools

#### `start_auto_write`
Create an auto-write job (queued state). Then call `auto_write_step` in a loop to drive it forward.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `start_episode` | integer | No | First episode number (default 1) |
| `end_episode` | integer | No | Last episode number (default 500) |
| `premise` | string | No | Optional extra premise for planners |
| `overwrite` | boolean | No | Overwrite existing episode text (default `false`) |
| `writer_model` | string | No | Writer model name |
| `controller_model` | string | No | Controller model name |

---

#### `auto_write_step` `[sampling]`
Execute up to `steps` LLM steps for an auto-write job. Call repeatedly until `done=true`.

Pipeline: series plan → arc plan → mini-arc plan → episode outline → episode prose.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | integer | Yes | Auto-write job id from `start_auto_write` |
| `steps` | integer | No | Max LLM steps per call (1–6, default 5) |

---

#### `get_auto_write_job`
Poll an auto-write job's status and progress.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | integer | Yes | Auto-write job id |

---

#### `stop_auto_write`
Request stop of a running auto-write job.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | integer | Yes | Auto-write job id |

---

#### `list_auto_write_jobs`
List all auto-write jobs for a work, including completed and stopped ones.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |

---

### Cover Tools

#### `list_covers`
List cover images for a project. Each item includes filename, url, style, provider, and created_at.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |

---

#### `generate_cover_prompt` `[sampling]`
Generate an English text-to-image prompt for a novel cover illustration using Anna's LLM. Reads synopsis, genre, recent episodes, and characters. Returns a ready-to-use prompt string (under 120 words).

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `style` | string | No | Art style hint: anime, realistic, watercolor, … |

---

#### `generate_cover` `[sampling]`
Two-step cover generation. Step 1: Anna's LLM writes the prompt (if `prompt` is omitted). Step 2: the INE server renders the image via ComfyUI or Higgsfield. Polls up to 10 minutes and returns status, filename, and a direct URL.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `project_id` | integer | Yes | INE project id |
| `prompt` | string | No | English text-to-image prompt. Omit to auto-generate via Anna LLM. |
| `style` | string | No | `anime` / `gekiga` / `watercolor` / `photo` / `ukiyoe` / `pixel` / `adult` / `other` |
| `provider` | string | No | `comfyui` / `higgsfield` (default `comfyui`) |

---

#### `check_cover_services`
Diagnostic: report available image-generation services in the runtime environment. Returns Python version, relevant env var names, and the INE server's cover config.

*(No parameters)*

---

## Workflow: Writing a Novel

To write a 500-episode novel with Anna's LLM:

1. **Create project** — Set name, genre, synopsis, rules, language.
2. **Add entities** — Use `add_ai_entities` to seed characters, world, plots, foreshadowings.
3. **Start job** — `start_auto_write` creates the job in `queued` state.
4. **Step loop** — Call `auto_write_step` repeatedly until `done: true`. ~270+ calls for 500 episodes.
5. **Review** — Use `get_story_twin`, `check_continuity`, and `reflect_to_novel` to audit.

### Step pipeline

Each `auto_write_step` call runs up to 6 LLM steps through this ordered pipeline:

```
Series plan (×1)  →  Arc plan (×5)  →  Mini-arc plan (×50)
  →  Episode outline (×N)  →  Episode prose (×N × 2 passes)
```

A full 500-episode novel requires roughly 270+ step calls. The tool returns the current progress percentage, phase, and episode number so you can display progress to the user.

---

## Workflow: Proofreading an Episode

> **Prerequisite:** The project must have a style guide set. Generate one via the INE web app (「スタイルガイド生成」) before using `proofread_episode`.

**Preview mode** (default): returns a list of suggested corrections without saving.

```
proofread_episode(episode_id=123)
→ { diffs: [{original, suggested, reason}, …], diff_count: 5, applied: 0 }
```

**Apply mode**: saves all corrections back to the episode in one PUT.

```
proofread_episode(episode_id=123, apply=true)
→ { diffs: […], diff_count: 5, applied: 5 }
```
