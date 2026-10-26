# Anna Framework integration

INE can be driven from [Anna](https://anna.partners/developers) as an App: a stdio Executa plugin plus a writing-coach skill and a small dashboard window.

The novel still lives in INE (PostgreSQL, Qdrant, local Ollama). Anna never replaces those services. When you `#ine` in Anna chat, the agent calls tools that hit `http://localhost:8000/api/v1` (or whatever origin you configure).

## What ships

| Piece | Path | Role |
|---|---|---|
| App listing | [`anna/app.json`](../anna/app.json) | Slug `ine`, bundled Executas |
| Manifest | [`anna/manifest.json`](../anna/manifest.json) | Schema 3, UI + prompt addendum |
| Tool | [`anna/executas/ine-bridge/`](../anna/executas/ine-bridge/) | JSON-RPC 2.0 over stdio → INE REST |
| Skill | [`anna/executas/novel-coach/SKILL.md`](../anna/executas/novel-coach/SKILL.md) | How Anna should use the tools |
| UI | [`anna/bundle/`](../anna/bundle/) | Health / works / story-twin dashboard |

## Tools

`health`, `list_projects`, `get_project`, `create_project`, `get_story_twin`, `list_episodes`, `get_episode`, `create_episode`, `save_episode`, `list_characters`, `create_character`, `list_world`, `create_world`, `search`, `generate`, `chat`, `check_continuity`, `list_continuity_issues`, `start_auto_write`, `get_auto_write_job`, `stop_auto_write`.

Credentials: `INE_BASE_URL` (optional, default `http://localhost:8000`), `INE_USERNAME`, `INE_PASSWORD` (HTTP Basic, same as the INE web login).

## Run it

1. Start INE as usual.
2. Install [`@anna-ai/cli`](https://www.npmjs.com/package/@anna-ai/cli) and from `anna/` run `anna-app dev`.
3. Set the three credentials on the Executa (or export them for a raw stdio smoke test).

Details and privacy notes: [anna/README.md](../anna/README.md).
