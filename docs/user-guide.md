---
title: User Guide
layout: default
---

[← Manual home](index.md) | [日本語](user-guide.ja.md)

# User Guide (Operation Manual)

A screen-by-screen reference. For setup, see the [Installation Manual](installation.md); for a gentler first walkthrough, see the [Beginner's Guide](getting-started.md).

## Login

Username/password sign-in checks a `users` table (multiple accounts are supported), not a single fixed pair — the account created automatically on first startup (`ADMIN_USERNAME`/`ADMIN_PASSWORD`, default `admin`) is just the first one. The browser resends the username/password as HTTP Basic Auth on every request, stored in this browser's `localStorage`.

The "Googleでログイン" / "GitHubでログイン" buttons are enabled once the server has that provider's client ID/secret configured (see [requirements.md](requirements.md#oauth2-login-google--github)) — otherwise they stay visible but disabled placeholders. A Google/GitHub login sets a signed session cookie instead of using localStorage, and auto-creates its own account (no password — it can only sign in through that same provider) the first time a given email logs in.

The sidebar/dashboard's "⏻ ログアウト" button clears whichever of these applies — the stored Basic Auth pair, the session cookie, or both.

**Display language.** The login screen (always shown in English, since no language has been chosen yet) has a "Display language" selector with eight languages: 日本語, English, 简体中文, 繁體中文, 한국어, Español, Français and Deutsch. The choice is saved in this browser and applied right after you sign in (the page reloads once if it differs from the current one). It can only be changed on the login screen — sign out and back in to switch. It affects the app's interface only: AI prompts and generated text, the novel content itself, and messages coming from the server (e.g. some error details) stay in Japanese.

Forgot your password? "パスワードをお忘れですか？" on the login screen emails a time-limited reset link to that account's email address (only accounts that have one set — see "Account settings" below). If the server has no mail server configured (`SMTP_HOST`, see [requirements.md](requirements.md#account-management-password-change--reset--adding-users)), the link is only written to the `api` container's log instead of actually emailed.

## Dashboard

Lists your works as a **tree**: an original work is a parent card, and the works made from it — translations and digests (総集編) — are indented beneath it with a language/「総集編」 tag (▾/▸ collapses a parent). Each card shows genre and a progress bar (episodes written ÷ that project's episode target). Works created before the parent link existed (see below) simply appear as top-level cards. The panel on the right shows detailed stats — episode count, open continuity issues, and an overall health score — for your most recently created project. Click a card to open that project. "＋ 新規作品作成" opens the new-project form.

When something is running on the server, a **「サーバーで実行中の処理」** card appears above the list: auto-write, imports, translations, "全翻訳", cover generation and 複数画像作成, each with its work name, progress and a **キャンセル** button (plus 「すべてキャンセル」 when there are several). These jobs run on the server, so they keep going after you log out (or are logged out after 10 idle minutes) and show up here again when you return. Work already done is kept when you cancel; auto-write stops after the current step, the others stop immediately. Translation and cover jobs are held in memory, so a server restart ends them.

### Account settings

"⚙ アカウント設定" opens a form to change your own password (current password required). An admin account (`is_admin=true` — the bootstrap `ADMIN_USERNAME` account always is) also sees a "ユーザー管理" section here listing every account, with a form to add a new one — username, initial password, an optional email (needed for that account to be able to use "パスワードをお忘れですか？"), and whether to grant it admin rights.

*The "AI利用状況" (AI usage) stat mentioned in early design sketches is not implemented — nothing tracks token/request usage yet.*

## Creating a project

Fields: name (required), genre, synopsis (あらすじ), free-text "rules" (詳細設定 — anything you want the AI to always respect: tone, audience, hard constraints), and a target episode count (episode_goal, default 500). All of these except the target count map directly to a `Project` record and can be edited later from Settings.

## Project Home

The landing screen after opening a project: header with name/genre/synopsis and progress, a 3×3 icon grid to every other screen, and a "最近の更新" (recent activity) list of the 5 highest-numbered episodes. Below it are cards for:

- **出版情報 (publishing info)** — opens a dialog with everything a store listing asks for (see [Publishing info and posting destinations](#publishing-info-and-posting-destinations)), and the **投稿先** links.
- **多言語化 (translation)** — one button per language, **全翻訳** and a progress/cancel area (see [Translation](#translation)).
- **総集編 (digest)** — creates a ~1/2-length digest as a new work, shown as a child of the original on the dashboard.

## Importing from a text file

Two ways in, both from a plain `.txt` file in the "なろう" (Shosetsuka ni Naro) bracket-section export format:

- **Dashboard → "ファイルからインポート"**: creates a brand-new project from a full novel export — a metadata header (title/synopsis/genre) followed by episodes delimited by `------- エピソードN開始 -------` separators. The parsed title/synopsis/genre become the new project's fields, and every episode is created.
- **Settings → "インポート" tab, inside an existing project**: adds or updates episodes in *that* project from either the same full-export format or a headerless draft-episodes file (episodes delimited by `-------第N話「タイトル」-------`, title embedded in the separator itself). An episode number that already exists gets its content overwritten (the prior content is snapshotted to that episode's revision history first, same as any other edit); a new number is created.

Both run as a background job you can watch progress on (`GET /api/v1/import-jobs/{id}`, polled every 2 seconds) rather than a single blocking request. **Importing only stores the text — no AI runs afterwards** (no embedding/indexing, no character-state extraction, no continuity audit); an imported episode is indexed for semantic search the next time it is saved, and you can run the audit from the app whenever you want. A large import can still take a while because every episode is written to the database and the disk mirror. The progress bar shows "episodes processed / total episodes", and closing the dialog does not cancel the job (a dashboard import carries on in the background; the Settings-tab import keeps polling while that tab is open) — it can be cancelled from the dashboard's running-jobs card. Starting an import also asks for [desktop-notification permission](#auto-write-自動執筆) and notifies when the job ends, with the same caveats as auto-write (works only while this tab is open; not a push notification).

The parser auto-detects which of the two formats a file is — you don't pick a mode. A file matching neither (no recognizable episode separators) is rejected up front with a 400, before any job is created.

## Write

The core writing screen, three columns:

- **Left**: the episode list for this project, plus "＋ 新規エピソード" to add the next one (numbered automatically).
- **Center**: title, one-line summary, and the main body textarea for the selected episode. "保存＋人物状態更新" saves the episode, re-indexes it for semantic search, and asks the AI to extract character-state changes from the new text — if either of those background steps fails (e.g. Ollama or Qdrant is down), a warning banner appears above the editor instead of failing silently.
- **Right ("AI EDITOR-IN-CHIEF")**: a Context Builder–backed assistant. "⚠ 連続性を監査" runs a continuity audit against everything registered for the project. The four main actions (続きを書く / 次の展開 / 要約 / 校正) and the six "QUICK CUSTOM CHECKS" buttons all send a prompt to the AI along with the current story context; the result appears in the AI RESULT box, and "＋ 本文に追加" appends it to the episode body.
- **Editor toolbar**: B / I / H / ❝ buttons wrap the current selection (or insert at the cursor) with Markdown syntax (`**bold**`, `*italic*`, `## heading`, `> quote`) rather than applying real rich-text formatting — the stored content is still plain Markdown text. "プレビュー" renders that Markdown to HTML so you can check how it reads; "編集に戻る" switches back to the raw textarea. A live character count (whitespace excluded) is shown next to the toolbar.
- **🕘 履歴 (revision history)**: every time you save different content than what was there before, the previous version is snapshotted (kept up to 20 per episode). This button lists them with a "この版に復元" (restore) action — restoring itself snapshots the version you're leaving, so restoring is itself undoable.

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

**Two helpers on every one of these screens:**

- **CSV import skips duplicates.** A row is skipped when it matches an existing row (or an earlier row in the same file) on its key — the name or title, and for 年表 the episode number plus title — compared ignoring full-/half-width, case and spaces. The result line reports how many were skipped.
- **「＋ AIで10個追加」** asks the AI for about 10 new rows (in the work's language), using the synopsis, genre, rules, existing characters and the rows already there as context. Rows that duplicate existing ones are dropped before saving, so pressing it again adds fresh ideas. It shows up in the LLM queue as 「設定のAI追加」. Review what it adds — it is a starting point.

## Analytics (分析)

A tabbed dashboard built on the "Story Digital Twin" (`GET /api/v1/projects/{id}/story-twin`):

- **概要 (Overview)**: episode/character/world/plot/foreshadowing counts, a health score, prose coverage (% of episodes with non-empty content), active plots, and open foreshadowing.
- **人物関係図 / 世界観グラフ / 時系列グラフ**: relationship graphs. Character/world edges come from explicit relations you've registered *plus* a same-episode co-occurrence heuristic (two characters mentioned in the same episode text get a weak automatic link) — don't read too much into faint auto-inferred edges.
- **状態履歴 (State history)**: the most recent character-state snapshots the AI has extracted after each episode save.
- **文字数 (Word count)**: total/average character counts (whitespace excluded) and a cumulative-character-count-by-episode-order chart — a rough proxy for writing pace, not a time-based one (it has no notion of *when* an episode was written, only its position in the sequence).
- **連続性 (Continuity)**: run or review the same continuity audit available from the Write screen, project-wide.

The health score is a heuristic (continuity issue counts + episode coverage), not a measure of prose quality.

## Search (検索)

Semantic search over your episode text via Qdrant. If Qdrant is unreachable, it silently falls back to a plain PostgreSQL substring match (`ILIKE`) — the screen tells you which one actually served the results ("セマンティック検索 (Qdrant)" vs "全文一致 (PostgreSQL フォールバック)"). "再構築" (Rebuild) re-indexes every episode in the project (this button only appears when searching the current project — see below).

Checking "すべての作品を検索対象にする" (search all projects) switches to `POST /api/v1/rag/search-all`, which searches across every project's episodes instead of just the current one. Each result shows which project it came from. There's no "rebuild index" button in this mode — rebuild from each project's own Search screen instead.

### Search and replace-all (検索・全置換)

The "検索・全置換" tab on the same screen is a separate, plain-text (not semantic) find/replace scoped to the current project's episodes (`GET`/`POST /api/v1/projects/{id}/text-search` and `/text-replace`). Enter a search string and optional replacement, toggle case sensitivity, and search — each matching episode is listed with its hit count and a few surrounding snippets, and is pre-selected for replacement (uncheck any you want to skip). Replacing is scoped to whichever episodes are checked; each affected episode's prior content is snapshotted to its revision history first (see Write screen's revision history), so a replace-all can always be undone episode by episode afterward.

## AI Chat (AIチャット)

A free-form chat with the same story context the Write screen's assistant uses. Conversation history is **persisted per project** (`GET`/`POST`/`DELETE /api/v1/projects/{id}/chat`) — it's still there when you come back to this screen or reload the page. "履歴を削除" permanently deletes it for that project. Replies are rendered as Markdown (headings, bold, tables, rules), same as the Write screen's preview — not shown as raw `##`/`**`/`|` syntax.

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

Clicking "▶ 自動執筆を開始" also asks the browser for notification permission (if not already granted/denied) — when granted, a desktop notification fires the moment the job finishes (completed, stopped, or errored), so you don't have to keep watching the progress bar. This only works while this tab stays open; it's a plain browser `Notification`, not a push notification, so it can't reach you if the tab or browser is closed. The [file import](#importing-from-a-text-file) jobs behave the same way.

The range's last episode defaults to the work's own **episode target** (総話数目標) rather than a fixed 500, and the episode list/"add episode" screens handle works of any length (the list is no longer cut off at 200). Planning beyond episode 500 is generated on demand.

## Settings (設定)

- **基本設定 (Basic)**: edit the project's name, genre, synopsis, rules, and episode target. Saves immediately via the API.
- **AI設定 (AI settings)**: sets *this browser's* default Writer/Controller model names, which prefill the Auto-write start form.
- **接続設定 (Connection settings)**: Qdrant URL and both Ollama endpoints/models (Writer and Controller) can be changed here and take effect immediately, no restart needed — see [Connection settings](#connection-settings) below. SQL (the database itself) and the CORS allowed-origins list are shown read-only.
- **エクスポート (Export)**: downloads every episode's prose (title + summary + body only — no characters/world/plot/foreshadowing data) as a single file in one of three formats: plain text (`.txt`), Markdown (`.md`), or a minimal but valid EPUB3 (`.epub`) you can open in any e-reader. `GET /api/v1/projects/{id}/export?format=txt|md|epub`.
- **表紙画像 (Cover image)**: the ComfyUI server URL (with a 接続テスト that lists the installed checkpoints), the common ComfyUI/Higgsfield values, and — per look (see below) — the prompt direction/suffix and ComfyUI/Higgsfield overrides, including a checkpoint per look. Saving writes `cover_config.json`; the next generation uses it (admins only). See the [ComfyUI Guide](comfyui.md).
- **作品の削除 (Delete work)**: deletes the work and everything in it. A JSON backup of all its data downloads first (nothing is deleted if that fails). A work that still has children (translations/digests) cannot be deleted until they are all deleted. Vector-search entries are derived data and are not removed.

The エクスポート tab also offers **KDP出版パッケージ (.zip)** and the JSON backup (`GET /api/v1/projects/{id}/export?format=json`, every project table plus the publishing info) — see [Publishing info and posting destinations](#publishing-info-and-posting-destinations). 「インポート開始」 and 「今すぐバックアップ」 are blue like the other action buttons.

### Connection settings

`GET`/`PUT /api/v1/system-settings`. Each of Qdrant URL, Ollama 1 (Writer) URL/model/embedding-model, and Ollama 2 (Controller) URL/model can be overridden from this screen; a field shows "（上書き中）" when it's currently an override rather than the server's environment-variable default. Saving an empty value for a field reverts it to that default. These overrides are stored in the database and take effect on the very next AI/search call — Qdrant and Ollama clients are constructed fresh per call, so there's nothing to restart.

The database connection (`DATABASE_URL`) and the CORS allowed-origins list (`CORS_ORIGINS`) are deliberately **not** editable from here, for two different reasons: `DATABASE_URL` because the app would have to swap the very connection it's using to read this settings screen out from under itself mid-request, which isn't safe to do live; `CORS_ORIGINS` because it's a security control over which origins may talk to this API at all, and letting any signed-in user flip it open to `*` from the UI is a bigger blast radius than a wrong Ollama URL. Change either one via its environment variable ([requirements.md](requirements.md#cross-origin-access-cors_origins)) and recreate/restart the server.

Every row (including the read-only SQL one) has a "接続テスト" (test connection) button — `POST /api/v1/system-settings/test-connection`. It probes the *value currently in that field*, whether or not it's been saved yet, so you can check a new URL before committing to it: a real `SELECT 1` for the database, `get_collections()` for Qdrant, and `GET /api/tags` for either Ollama endpoint (the two model fields additionally check that the named model is actually pulled, not just that the server answers). Each probe times out after 8 seconds and reports round-trip latency alongside success/failure — it never touches what's saved, only what you're about to save.

## Publishing info and posting destinations

**出版情報** (Project Home) gathers what a store listing such as Amazon KDP asks for: title, subtitle, author (pen name OK), description (up to 4000 characters, defaults to the synopsis), keywords (up to 7, 50 characters each), category, whether it contains adult content, and the reader age range. Title and author are the work's own fields (so they also feed the cover lettering and the EPUB); the rest is saved as `publishing.json` beside the episode files. "まとめてコピー" copies everything as text. `GET`/`PUT /api/v1/projects/{id}/publishing`.

**KDP出版パッケージ** (Settings → エクスポート) builds one ZIP per work: `book.epub` (with the chosen cover), the cover image, and `kdp_info.csv` / `kdp_info.md` — the listing details in KDP's order plus a **draft** of KDP's AI-generated-content disclosure (text / images / translation) inferred from the app's own records (auto-write history, translated-from link, cover provider). KDP counts AI-made text, images and translations as AI-generated even when edited, so confirm the answers yourself. Registering and publishing stay manual on KDP — the app never logs in or posts. Translated works are separate works: export each one separately and edit its listing text.

**投稿先** buttons open the posting pages of Kindle Direct Publishing, 小説家になろう, Wattpad, Royal Road, Inkitt, Wuxiaworld, Webnovel, Chuangshi (創世中文網) and Munpia (문피아) in a new tab, and 「投稿先の詳細」 shows notes per service (supported languages, how the language is set, translation delivery, cautions). The notes are research notes that may go out of date; 編集 lets an admin change names, URLs and notes, add or remove destinations, or 初期値に戻す (`GET`/`PUT /api/v1/publish-targets`, stored as `publish_targets.json`, http/https URLs only, shared by all users). Note that 小説家になろう requires AI-use disclosure and forbids works written entirely by AI, and there is no official posting API for it or for KDP.

## Translation

**Omission check** (on by default, `TRANSLATION_OMISSION_CHECK`): after translating a chunk, the source and translated sentences are embedded with a multilingual embedding model (`TRANSLATION_EMBED_MODEL`, default `bge-m3` — run `ollama pull bge-m3`) and a source sentence with no similar counterpart is treated as omitted; the chunk is then translated again with that sentence named, and the new answer is kept only if it brings the sentence back. It is one cheap embedding call per chunk and is skipped silently if the model is not installed. In a test it found a really dropped sentence (best similarity 0.58 vs 0.73–0.95 for translated ones) without flagging the faithful translations.

**Optional AI check** (`TRANSLATION_REVIEW=true`, off by default): the Controller model compares each translated chunk with its source and, if it reports problems, the chunk is translated again with its findings. It adds one Controller call per chunk. In a live test with qwen3:14b it was **not reliable** — it flagged a faithful translation as faulty and missed a real omission — so treat its findings as a hint, not proof, and expect extra time.

Each chunk is checked after translation: if the answer is empty, far too short, or still mostly in the source language (some models return the Japanese unchanged or translate only part), it is translated once more with a firmer prompt and the better answer is kept. One call may take up to `TRANSLATOR_TIMEOUT_SECONDS` (default 900). For Qwen3 models the app adds `/no_think`, which skips the long reasoning phase and is several times faster.

Whatever model translates, its answer is cleaned the same way before saving: `<think>` reasoning, a code fence around the whole answer, an announcing first line ("Here is the translation:") and a closing remark ("Note: …", "I hope this helps") are removed. Only whole leading/trailing lines matching strict patterns are dropped, never text inside the translation.

Project Home → 多言語化 translates the whole work into a new work (the original is untouched), one button per language. **全翻訳** translates into every other language, one after another, as a **single server-side job** (so it survives logout; `POST /api/v1/projects/{id}/translate-all`) — a failing language does not stop the rest, and failures are listed at the end.

A translated work remembers its source (`source_project_id`). Translating the same work into the same language again **continues that work instead of duplicating it**: missing episodes, characters and world entries are added, and a title/summary/body that is empty or shorter than 25% of the original is translated again; complete episodes are skipped. (Translations made before this link existed are not recognised and start a new work.) **翻訳をキャンセル / 全翻訳をキャンセル** stops the job; what is already translated stays and the next run continues from it.

## Local-disk mirror and GitHub auto-save

Every episode save also writes a plain Markdown copy to disk (`NOVEL_STORAGE_DIR`, one folder per project, one `.md` file per episode — filenames are keyed by episode number and id, so renaming a title never orphans a file). The database stays authoritative for everything the app reads; this is a write-through mirror, kept for readability outside the app and as the basis for GitHub sync.

If `GIT_REMOTE_URL` is set (a git remote URL with your Personal Access Token embedded, e.g. `https://<token>@github.com/<you>/<repo>.git`), a background loop commits whatever changed in that mirror and pushes it every `GIT_AUTOSYNC_INTERVAL_SECONDS` (default 300). Nothing is pushed if `GIT_REMOTE_URL` is unset — the local-disk mirror still works on its own. Push/commit failures (no network, bad token, remote rejected) are logged and simply retried on the next tick; they never interrupt saving in the app itself.

## Backup and restore

Settings → "バックアップ" tab (a server-wide feature, not scoped to the current project): shows whether scheduled backups are on, the interval/retention currently configured, and a list of backups taken so far with what each one covers and its size. "今すぐバックアップ" (Backup now) triggers one on demand and shows its result (success/failure per component) right there.

Scheduled backups are **off by default** — set `BACKUP_ENABLED=true` (`BACKUP_INTERVAL_SECONDS`, default 86400 = daily; `BACKUP_RETENTION_COUNT`, default 7, older ones are deleted automatically) to turn them on. Each run does the same thing `scripts/backup.sh` does by hand — a PostgreSQL dump (`pg_dump`) plus a Qdrant collection snapshot, if anything's been indexed — written to a timestamped folder under `BACKUP_DIR` (a container volume by default in the Docker Compose / desktop-installer setups). Unlike the standalone script, it resolves the Qdrant URL the same way the rest of the app does, including any live override set from 接続設定, not just a fixed env var.

To restore, use `scripts/restore.sh <backup-dir>` at the repo root, run from a machine with the `docker-compose` stack up — **it replaces the current database contents with no confirmation prompt**, so double-check the path before running it. There's no restore button in the UI; restoring is inherently destructive to whatever's currently in the database, so it stays a deliberate command-line step. Ollama models aren't covered by any of this; re-pull them separately if needed. The local-disk episode mirror (and its GitHub sync, if configured) is a separate, always-on backstop for episode text specifically — it isn't part of the backup/restore flow above.

## Mobile

Below 700px width the sidebar collapses into a wrapping horizontal bar at the top instead of a fixed left column, and grids (icon grid, entity-edit forms) drop to fewer columns. It's usable but optimized for desktop use, given the amount of text entry the app requires.

## Cover images and digests: what is saved

- **Cover look and prompt.** Before generating, pick the look — アニメ風 (anime), 劇画風 (gekiga), 実写風 (photorealistic), 水彩画 (watercolor), 浮世絵風 (ukiyo-e), ドット絵 (pixel art), アダルト (a mature, sensual-mood look that is deliberately non-explicit) or その他 (type your own) — and the prompt, and the image model/settings for that look, follow from it. The prompt, look and engine are saved to disk as you type and are still there after leaving the screen or reloading; your own edits to the prompt are what gets sent to the image model.
- **Generated images** are saved automatically on the server's disk (`COVERS_DIR/<project id>/`, with a small `.json` beside each recording the prompt, look and settings used) and listed on the cover panel; click one to enlarge it or to use it as the EPUB cover.
- **複数画像作成** (next to the title/author checkbox) generates many images in one background job: アニメ風 10, 劇画風 10, 水彩画 5, 浮世絵風 5, ドット絵 5, アダルト 10 (45). It writes one prompt per look, then that look's images in turn; progress shows as n/45 and the gallery fills as images arrive. It stops early if two images in a row fail (for example ComfyUI is down). One batch per project at a time; cancellable from the dashboard. `POST /api/v1/projects/{id}/cover/batch`.
- **Deleting images.** Click an image to enlarge it, then 「この画像を削除」 removes it (with its `.json` and its `raw/` original; if it was the adopted cover, the adoption is cleared).
- **Lettering rules.** Titles of up to 12 full-width characters per line are split into balanced lines (3–4 lines for long titles, breaking after punctuation where possible, never starting a line with 、。！？」); if a line is still too wide the font shrinks to fit. If the project has no author, the logged-in user's name is used. Limits are `overlay.max_title_chars` / `overlay.max_title_lines` in `cover_config.json`.
- **Title and author on the image.** When generation finishes, the project name and author (set under the project's basic settings) are drawn onto the image automatically — toggle with "タイトルと著者名を画像に入れる". The untouched original stays in `COVERS_DIR/<project id>/raw/`. Font, sizes, colors and positions are in the `overlay` section of `cover_config.json`; if no Japanese font is installed, point `overlay.font` at a font file (the Docker image ships IPAGothic).
- **Image models and settings** are not built into the app: they are in `cover_config.json` (`COVER_CONFIG_PATH`; created with defaults on first use). Per look you can set the ComfyUI checkpoint, size, steps, CFG, sampler, scheduler, negative prompt, the Higgsfield model, and the wording that steers the prompt. The file is re-read whenever it changes, so edits apply to the next generation without restarting; if you save a broken file the last good one keeps being used.
- **Digest (総集編).** The digest is its own work (open it from "総集編を開く"), saved like any other, and its episode files are mirrored to disk. The cover/digest panel remembers the last digest made from a work, and its size is read live, so edits you make to the digest show up.

With Docker Compose these live in the `covers` volume (`/covers` in the `api` container, including `cover_config.json`), so they survive rebuilds. To edit the config: `docker compose exec api vi /covers/cover_config.json`, or copy it out and back with `docker compose cp`. `COMFYUI_URL` defaults to `http://host.docker.internal:8188` there (ComfyUI running on the Docker host).
