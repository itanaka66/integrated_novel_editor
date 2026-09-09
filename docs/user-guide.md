# User Guide (Operation Manual)

A screen-by-screen reference. For setup, see the [Installation Manual](installation.md); for a gentler first walkthrough, see the [Beginner's Guide](getting-started.md).

## Login

One shared account, configured via the `ADMIN_USERNAME` (default `admin`) / `ADMIN_PASSWORD` environment variables — not per-user accounts. There is no session or token: the browser resends this username/password as HTTP Basic Auth on every request, stored in this browser's `localStorage`. Logging out isn't a feature as such; clearing the browser's site data (or getting a 401, e.g. from a wrong password) drops you back to the login screen.

The "Googleでログイン" / "GitHubでログイン" buttons are visible but disabled — there's no OAuth integration. Don't wait for them to work.

## Dashboard

Lists all projects as cards, each showing genre and a progress bar (episodes written ÷ that project's episode target). The panel on the right shows detailed stats — episode count, open continuity issues, and an overall health score — for your most recently created project. Click a card to open that project. "＋ 新規作品作成" opens the new-project form.

*The "AI利用状況" (AI usage) stat mentioned in early design sketches is not implemented — nothing tracks token/request usage yet.*

## Creating a project

Fields: name (required), genre, synopsis (あらすじ), free-text "rules" (詳細設定 — anything you want the AI to always respect: tone, audience, hard constraints), and a target episode count (episode_goal, default 500). All of these except the target count map directly to a `Project` record and can be edited later from Settings.

## Project Home

The landing screen after opening a project: header with name/genre/synopsis and progress, a 3×3 icon grid to every other screen, and a "最近の更新" (recent activity) list of the 5 highest-numbered episodes.

## Write

The core writing screen, three columns:

- **Left**: the episode list for this project, plus "＋ 新規エピソード" to add the next one (numbered automatically).
- **Center**: title, one-line summary, and the main body textarea for the selected episode. "保存＋人物状態更新" saves the episode, re-indexes it for semantic search, and asks the AI to extract character-state changes from the new text — if either of those background steps fails (e.g. Ollama or Qdrant is down), a warning banner appears above the editor instead of failing silently.
- **Right ("AI EDITOR-IN-CHIEF")**: a Context Builder–backed assistant. "⚠ 連続性を監査" runs a continuity audit against everything registered for the project. The four main actions (続きを書く / 次の展開 / 要約 / 校正) and the six "QUICK CUSTOM CHECKS" buttons all send a prompt to the AI along with the current story context; the result appears in the AI RESULT box, and "＋ 本文に追加" appends it to the episode body.

## Plot / Characters / World / Timeline / Foreshadowing / Glossary

These six screens share one underlying list-and-form UI (create, edit, delete), differing only in their fields:

| Screen | Fields |
|---|---|
| プロット (Plot) | title, type, status, start/end episode, objective, conflict, resolution |
| キャラクター (Characters) | name, role, personality, speech style, goal, status (alive/dead/missing/unknown), notes |
| 世界観 (World) | name, type, description, rules, location, era |
| 年表 (Timeline) | episode number, title, in-world time, description |
| 伏線 (Foreshadowing) | title, description, setup/payoff episode, status (open/resolved/abandoned) |
| 用語集 (Glossary) | term (name), description, category (location field) |

**用語集 (Glossary) is not a separate data type** — it's stored as a World entity with `entity_type: "glossary"`, filtered client-side. The 世界観 screen only shows entities that are *not* tagged as glossary, so the two lists never overlap. This keeps the backend simpler at the cost of a slightly indirect implementation; if you ever query the API directly (`GET /api/v1/projects/{id}/world`), glossary terms are mixed in there too.

Everything you register here is fed into the AI's context for every generation and continuity check — this is the mechanism the app uses to keep long-running stories consistent.

## Analytics (分析)

A tabbed dashboard built on the "Story Digital Twin" (`GET /api/v1/projects/{id}/story-twin`):

- **概要 (Overview)**: episode/character/world/plot/foreshadowing counts, a health score, prose coverage (% of episodes with non-empty content), active plots, and open foreshadowing.
- **人物関係図 / 世界観グラフ / 時系列グラフ**: relationship graphs. Character/world edges come from explicit relations you've registered *plus* a same-episode co-occurrence heuristic (two characters mentioned in the same episode text get a weak automatic link) — don't read too much into faint auto-inferred edges.
- **状態履歴 (State history)**: the most recent character-state snapshots the AI has extracted after each episode save.
- **連続性 (Continuity)**: run or review the same continuity audit available from the Write screen, project-wide.

The health score is a heuristic (continuity issue counts + episode coverage), not a measure of prose quality.

## Search (検索)

Semantic search over your episode text via Qdrant. If Qdrant is unreachable, it silently falls back to a plain PostgreSQL substring match (`ILIKE`) — the screen tells you which one actually served the results ("セマンティック検索 (Qdrant)" vs "全文一致 (PostgreSQL フォールバック)"). "再構築" (Rebuild) re-indexes every episode in the project.

## AI Chat (AIチャット)

A free-form chat with the same story context the Write screen's assistant uses. **Conversation history is kept only in this browser tab's memory** — nothing is persisted server-side, so reloading the page or switching projects clears it.

## Auto-write (自動執筆)

Generates a range of episodes (1 up to 500) with minimal human intervention, using a hierarchical planning pipeline:

```
Series Planner   (whole 1–500 arc)
  → Arc Planner       (5 arcs of 100 episodes)
    → Mini Arc Planner (10 mini-arcs of 10 episodes each, per arc)
      → Episode Planner (one blueprint per episode)
        → Writer         (generates the actual prose)
        → Controller gate (timeline/character/world/plot check; can force a rewrite)
```

Two model roles are involved (see [Software Requirements](requirements.md) for how to configure them):

- **Writer** — generates prose. Default `qwen3.8:27b`, overridable per job.
- **Controller** — does all the planning levels above plus the pre-write and post-write quality gates (timeline, character-state, world-setting, plot consistency only — it does not judge prose quality). Default `qwen3:14b`, overridable per job.

Starting a job: pick a start/end episode range, optionally a free-text "premise" (additional guidance), and whether to overwrite episodes that already have content (off by default — existing non-empty episodes are skipped). The plan (Series/Arc/Mini-Arc levels) is generated once and reused across episodes in range; it's expanded lazily, only as far as the requested range needs.

Progress display: a percentage, a phase label (queued / series_planner / arc_planner / controller_preflight / writer / controller_gate / completed / stopped / error), and counts of how many Arcs/Mini-Arcs/Episode-plans exist and how many episodes have actual written content. It's polled every 3 seconds while a job is active. "■ 停止する" requests a graceful stop — the job finishes its current episode, then stops rather than stopping mid-generation. The job history list at the bottom shows recent jobs for the project; click one to view it even after it's finished.

Every 5th episode written also triggers a full continuity audit automatically.

## Settings (設定)

- **基本設定 (Basic)**: edit the project's name, genre, synopsis, rules, and episode target. Saves immediately via the API.
- **AI設定 (AI settings)**: sets *this browser's* default Writer/Controller model names, which prefill the Auto-write start form. This does **not** change the actual Ollama server addresses — those are fixed server-side via `CONTROLLER_OLLAMA_URL`/`OLLAMA_URL` and can only be changed by whoever deploys the app (see [Software Requirements](requirements.md)).

## Mobile

Below 700px width the sidebar collapses into a wrapping horizontal bar at the top instead of a fixed left column, and grids (icon grid, entity-edit forms) drop to fewer columns. It's usable but optimized for desktop use, given the amount of text entry the app requires.
