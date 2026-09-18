---
title: Software Requirements
layout: default
---

[← Manual home](index.md) | [日本語](requirements.ja.md)

# Software Requirements

## Option A — Docker (recommended)

| Requirement | Version | Notes |
|---|---|---|
| Docker Engine | 24+ | Includes the Docker Compose v2 plugin (`docker compose`, not the old `docker-compose`) |
| Disk space | 10 GB+ free | Postgres/Qdrant volumes + built images |
| RAM | 8 GB+ | 16 GB+ recommended if you also run Ollama on the same machine |

Docker Desktop (Windows/macOS) or Docker Engine + the Compose plugin (Linux) both work.

`db` (PostgreSQL) and `qdrant` are Compose profiles rather than always-on services — already have your own PostgreSQL and/or Qdrant? Skip the bundled one(s) and point `DATABASE_URL`/`QDRANT_URL` at your own instance instead, either interactively via `scripts/setup.sh`/`setup.ps1` or by editing `COMPOSE_PROFILES` in `.env` yourself. See the [Installation Manual](installation.md#2-option-a--docker-compose) for the exact commands.

## Option B — Running services natively (no Docker)

| Component | Requirement |
|---|---|
| Backend (`apps/api`) | Python 3.13 |
| Frontend (`apps/web`) | Node.js 22, npm |
| Database | PostgreSQL 17 (a newer 15/16 will likely work too, but 17 is what's tested) |
| Vector store | Qdrant (any recent version; used via its HTTP API) |
| Local LLM runtime | [Ollama](https://ollama.com) |

Native installs still need Ollama and (if you want vector search) Qdrant — Docker only replaces Postgres/Qdrant/the app containers, not the LLM runtime, which almost always runs on the host to use its GPU.

## Ollama models

| Role | Config | Default model | Purpose |
|---|---|---|---|
| Writer (default) | `OLLAMA_URL` / `OLLAMA_MODEL` | `qwen3:8b` | Powers the manual AI-assist actions (続きを書く, 要約, 校正, custom prompts) in the write screen and chat |
| Writer (auto-write) | per-job `writer_model`, defaults to `qwen3.8:27b` | `qwen3.8:27b` | Generates episode prose during a 500-episode auto-write job; overridable per job in the 自動執筆 screen |
| Controller | `CONTROLLER_OLLAMA_URL` / `CONTROLLER_OLLAMA_MODEL` | `qwen3:14b` | Series/Arc/Mini-Arc/Episode planning and the pre/post quality gates during auto-write |
| Embeddings | `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | RAG semantic search indexing |

The Controller and Writer can point at the **same** Ollama server (just different model names) or at **two separate** Ollama servers/GPUs — set `CONTROLLER_OLLAMA_URL` to a second machine's address to split them. Larger models (`qwen3.8:27b`, `qwen3:14b`) need a GPU with enough VRAM to hold them; check the model's Ollama listing for its size before pulling it on modest hardware.

Qdrant URL and both Ollama endpoints/models above can also be changed live from the app's 設定 > 接続設定 screen — see the [User Guide](user-guide.md#connection-settings) — which is usually more convenient than editing these env vars and restarting.

## Local-disk / GitHub episode storage

| Config | Default | Purpose |
|---|---|---|
| `NOVEL_STORAGE_DIR` | `./novel_storage` | Where episode text is mirrored to disk as Markdown, one file per episode, on every save |
| `GIT_REMOTE_URL` | *(unset)* | A git remote URL with your token embedded (e.g. `https://<token>@github.com/<you>/<repo>.git`); when set, the mirror is auto-committed and pushed on a timer. Unset = disk mirror only, no GitHub sync |
| `GIT_AUTOSYNC_INTERVAL_SECONDS` | `300` | How often the auto-commit/push loop runs |

## Scheduled backups

| Config | Default | Purpose |
|---|---|---|
| `BACKUP_ENABLED` | `false` | Turns on the scheduled PostgreSQL + Qdrant backup loop. Off by default; a manual backup ("今すぐバックアップ" in Settings, or `scripts/backup.sh`) works either way |
| `BACKUP_DIR` | `./backups` | Where timestamped backup folders are written (a container volume in the Docker Compose / desktop-installer setups) |
| `BACKUP_INTERVAL_SECONDS` | `86400` | How often a scheduled backup runs (default: daily) |
| `BACKUP_RETENTION_COUNT` | `7` | How many of the most recent backups to keep; older ones are deleted automatically after each run |

Restoring is a manual, command-line-only step (`scripts/restore.sh`) — see [User Guide](user-guide.md#backup-and-restore) for why.

## Cross-origin access (CORS_ORIGINS)

| Config | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated list of origins the browser is allowed to call the API from |

Set this to whatever origin you actually open the web app from — a LAN IP, a different port, a custom domain — or the browser blocks the web app's requests to the API even though both are reachable. Multiple origins are comma-separated (e.g. `http://localhost:3000,http://192.168.1.10:3000`).

Setting it to `*` allows **any** origin — effectively disabling this check. This is occasionally useful while debugging where a request is actually coming from, but it means any website a logged-in user's browser visits could call this API on their behalf (the shared admin/password login is still required, but a browser that's already cached HTTP Basic Auth credentials for this origin — e.g. from opening the API's URL directly and typing them into the browser's native login prompt — sends them automatically on a credentialed cross-origin request once CORS allows it). Don't leave `*` set on anything reachable from an untrusted network.

Unlike Qdrant/Ollama, this is **not** editable from 設定 > 接続設定 (Settings > Connection settings) — it's a security control (which origins may talk to this API at all), not a connectivity convenience, so it's deliberately env/`.env`-only. Editing `.env` requires recreating the `api` container (`docker compose up -d`); a plain restart doesn't re-read it.

## The API address the browser uses (NEXT_PUBLIC_API_URL)

| Config | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | The API URL baked into the web app's JavaScript at build/container-start time |

Unlike most settings here, this one is read by the **browser**, not the server — "localhost" in this value always means the visitor's own machine, not wherever the app is hosted. If you access the web app from anywhere other than the Docker host itself (a LAN IP, a cloud VM's address, a domain), this must be set to that address's `:8000/api/v1`, or every API call will silently fail to connect for anyone but someone opening a browser directly on the host. `scripts/setup.sh`/`setup.ps1` set this for you from the hostname you give it. Changing it later requires recreating the `web` container (e.g. `docker compose up -d --build web`) — restarting the same container does not pick up the new value.

## Ports used

| Port | Service |
|---|---|
| 3000 | Web frontend |
| 8000 | API (also serves `/docs` — interactive OpenAPI UI) |
| 5432 | PostgreSQL |
| 6333 / 6334 | Qdrant (HTTP / gRPC) |
| 11434 | Ollama (not started by Docker Compose — runs on the host) |

## Browser

Any current Chrome, Edge, Firefox, or Safari. No IE/legacy-Edge support.
