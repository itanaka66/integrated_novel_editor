---
title: Installation Manual
layout: default
---

[← Manual home](index.md) | [日本語](installation.ja.md)

# Installation Manual

See [requirements.md](requirements.md) first to confirm your machine meets the prerequisites.

## 1. Install Ollama and pull the models

Ollama always runs on the host (Docker Compose does not start it), so do this regardless of which option below you choose.

1. Install Ollama from https://ollama.com.
2. Pull the models you plan to use:
   ```bash
   ollama pull qwen3:8b
   ollama pull qwen3.8:27b
   ollama pull qwen3:14b
   ollama pull nomic-embed-text
   ```
   `qwen3.8:27b` and `qwen3:14b` are large; skip them if you only want the write-screen AI assist (`qwen3:8b`) and don't plan to use the 500-episode auto-write feature yet.
3. Confirm it's listening: `curl http://localhost:11434/api/tags` should return JSON.

## 2. Option A — Docker Compose

```bash
git clone <this repository's URL>
cd integrated_novel_editor
cp .env.example .env
```

Edit `.env` and set a real `ADMIN_PASSWORD` (Compose refuses to start without one — see [requirements.md](requirements.md) for what each variable does). If Ollama runs on a different machine, also change `OLLAMA_URL` / `CONTROLLER_OLLAMA_URL`. If you'll open the web app from anywhere other than `http://localhost:3000` (a LAN IP, a different port, a custom domain), also set `CORS_ORIGINS` to that origin — the browser will otherwise block the web app's API calls.

Instead of editing `.env` by hand, `./scripts/setup.sh` (`.\scripts\setup.ps1` on Windows) walks through the same questions interactively — including whether to use the bundled PostgreSQL/Qdrant containers below or point at your own external instances, and where Ollama runs — and writes `.env` for you. Safe to re-run any time to change your answers.

```bash
docker compose up --build
```

By default this builds and starts four containers: `db` (Postgres), `qdrant`, `api` (runs `alembic upgrade head` automatically before starting, then seeds one demo project on first launch), and `web`. `db` and `qdrant` are Compose *profiles* — if you already run your own PostgreSQL and/or Qdrant, skip the bundled one(s) instead: remove `db`/`qdrant` from `COMPOSE_PROFILES` in `.env` (or run `scripts/setup.sh`/`setup.ps1` and answer "no" to the relevant question), point `DATABASE_URL`/`QDRANT_URL` at your own instance, and only `api`+`web` start. `COMPOSE_PROFILES` also works as a one-off command-line override, e.g. `docker compose --profile qdrant up --build` starts only the bundled Qdrant (using an external Postgres from `DATABASE_URL`) regardless of what's in `.env`. Wait for the logs to settle, then open:

- Web app: http://localhost:3000
- API interactive docs: http://localhost:8000/docs

Log in with the username `admin` and the `ADMIN_PASSWORD` you set.

To stop: `docker compose down`. To stop **and delete all data** (Postgres + Qdrant volumes): `docker compose down -v`.

### Linux: guided install script

On Linux there's no separate desktop installer, but `./scripts/install-linux.sh` covers the same ground as Option A above in one guided pass: it checks for Docker and offers to install it via the [official convenience script](https://docs.docker.com/engine/install/) (confirms before running anything that needs `sudo`), checks for Ollama and offers to install it via the [official install script](https://ollama.com), then runs `scripts/setup.sh` for you and offers to start the stack immediately.

```bash
git clone <this repository's URL>
cd integrated_novel_editor
./scripts/install-linux.sh
```

Safe to re-run any time.

## 2b. Option A2 — Desktop installer (Windows / macOS)

For a machine that shouldn't need `git clone` or a terminal, download the installer from the [Releases page](https://github.com/itanaka66/integrated_novel_editor/releases):

- **Windows**: run `INE-Setup-<version>.exe`. It's unsigned (no code-signing certificate), so SmartScreen will warn — choose "More info" → "Run anyway". Installs to `%LOCALAPPDATA%\INE` (or `Program Files` if you choose "for all users") with Start Menu / desktop shortcuts "INEを起動" and "INEを停止".
- **macOS**: open `INE-Setup-<version>.pkg` and follow the installer. It's unsigned/unnotarized — Gatekeeper will block the first open; right-click the `.pkg` → "Open" to bypass it once. Installs `INEを起動.app` / `INEを停止.app` to `/Applications`.

Either way, [Docker Desktop](https://www.docker.com/products/docker-desktop/) is still a separate prerequisite — install it first. The launcher shortcut checks for Docker, starts it if it's not already running, brings up the same four containers as Option A (pulling prebuilt images from GHCR instead of building them locally, so there's no build step), and opens http://localhost:3000. First launch generates a random `ADMIN_PASSWORD` into an `.env` file next to the installed files and shows it once in a dialog — write it down. Ollama is **not** installed by this installer; do step 1 above regardless of which option you use.

This installer path is a thin convenience layer over Option A, not a different deployment: it writes the same `docker-compose.yml`/`.env` shape into the install folder and drives `docker compose` under the hood, so anything in this manual or in [requirements.md](requirements.md) about environment variables, ports, or troubleshooting still applies verbatim — the settings screen's [connection settings](user-guide.md#connection-settings) work exactly the same way.

## 2c. Option A3 — Cloud / remote server

This is Option A (Docker Compose) run on a remote machine instead of your own — a cloud VM (AWS/GCP/Azure/DigitalOcean/etc.) or any server you can SSH into, so you and others can reach the app from more than one computer. The extra steps beyond Option A are all about the app being reachable from *another* machine at all.

1. **Provision a Linux VM.** Ubuntu 22.04/24.04 is the most tested choice. 8 GB RAM / 10 GB disk minimum (see [requirements.md](requirements.md)) — more if Ollama also runs on this same VM.
2. **Install and start INE** using the Linux guided installer above (`./scripts/install-linux.sh`), or Option A's manual steps. When `scripts/setup.sh` asks for the "access hostname or IP", answer with the VM's public IP or domain name — **not** `localhost`. This sets both `CORS_ORIGINS` and `NEXT_PUBLIC_API_URL` correctly; getting this step wrong is the most common cloud-deployment mistake (see the note below).
3. **Open the firewall.** Allow inbound TCP on port `3000` (web app) and `8000` (API) from wherever you'll connect — your own IP, or `0.0.0.0/0` if it truly needs to be public. Most cloud providers also require a separate "security group" / firewall rule in their console in addition to any OS-level firewall (`ufw`, etc.). Do **not** open port `11434` (Ollama) to the internet — see the security note below.
4. **Where should Ollama run?** Either on the same VM (needs a GPU-equipped instance type to be usable for anything beyond the smallest models) or on a GPU machine you already own, reachable from the VM over a private network/VPN. Point `OLLAMA_URL`/`CONTROLLER_OLLAMA_URL` at wherever it actually runs.
5. Open `http://<vm-ip-or-domain>:3000` from any machine and log in as usual.

**Why `NEXT_PUBLIC_API_URL` matters here specifically:** it's baked into the web app's JavaScript and read by *your browser*, not the server — so "localhost" in that value always means the visitor's own laptop, not the VM, and every API call would silently fail to connect for anyone except someone opening a browser directly on the VM itself. `scripts/setup.sh` sets it for you from the hostname you give it; if you skip that script, set it by hand in `.env` before running `docker compose up --build` (changing it later requires recreating the `web` container, e.g. `docker compose up -d --build web`, since it only takes effect for a fresh container).

**Security note — Ollama has no built-in authentication.** Anyone who can reach its port can use your GPU and pull whatever text out of it your models will produce. Never expose port `11434` directly to the public internet; keep it on a private network, restrict it with firewall rules to only the INE server's IP, or reach it over an SSH tunnel / VPN.

**Optional — a real domain with HTTPS:** the setup above serves plain HTTP on custom ports, which is fine for testing or a trusted small team. For a public deployment on a real domain, put a reverse proxy such as [Caddy](https://caddyserver.com/) in front of ports 3000/8000 — Caddy issues and renews a TLS certificate automatically for a domain you own, letting you drop the `:3000`/`:8000` ports entirely and access everything over `https://your-domain`. Remember to update `CORS_ORIGINS`/`NEXT_PUBLIC_API_URL` to the `https://` domain once you do.

### Optional — Cloudflare Tunnel instead of opening ports

[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (`cloudflared`) is the easier alternative to the firewall step above for a home server or a machine behind NAT/a dynamic IP (a "サーバー" with no stable public address) — a small always-running process on the server opens an *outbound* connection to Cloudflare, so **no inbound port needs to be opened at all** (skip step 3 above entirely). Cloudflare's edge terminates HTTPS for you, so there's no origin certificate to manage either.

1. **Add your domain to Cloudflare** (free plan is fine) and point its nameservers there, if you haven't already.
2. **Install `cloudflared`** on the same machine running `docker compose`, then authenticate and create a tunnel:
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create ine
   ```
3. **Route one hostname to both the web app and the API**, using a path rule so the browser never needs to cross origins at all — create `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: ine
   credentials-file: /home/<user>/.cloudflared/<TUNNEL_ID>.json

   ingress:
     - hostname: novel.your-domain.com
       path: ^/api/.*
       service: http://localhost:8000
     - hostname: novel.your-domain.com
       service: http://localhost:3000
     - service: http_status:404
   ```
   The `path` rule **must** come before the catch-all rule for the same hostname — `cloudflared` checks ingress rules top to bottom and uses the first match.
4. **Create the DNS record and run it as a service:**
   ```bash
   cloudflared tunnel route dns ine novel.your-domain.com
   sudo cloudflared service install
   sudo systemctl enable --now cloudflared
   ```
5. **Update `.env`** to match this single hostname, then recreate the containers so `NEXT_PUBLIC_API_URL` gets baked in (`docker compose up -d --build`):
   ```
   CORS_ORIGINS=https://novel.your-domain.com
   NEXT_PUBLIC_API_URL=https://novel.your-domain.com/api/v1
   ```
   Because the web app and the API now share one hostname (only the `/api/...` path differs), the browser sees them as the same origin — `CORS_ORIGINS` above is mostly a formality here, not the everyday failure point it is with a separate API port/subdomain.
6. Open `https://novel.your-domain.com` from anywhere and log in as usual.

**Known limitations behind Cloudflare (Tunnel or otherwise):**
- **Long-running SSE progress streams (自動執筆) can be cut off around 100 seconds** on Cloudflare's Free/Pro plans — that's an edge-side timeout on the proxied HTTP connection itself, unrelated to this app. The auto-write job keeps running server-side either way (it's a background task, not tied to that connection); only the *live* progress updates in the browser stop arriving. Reopening the 自動執筆 screen re-fetches the job's current status, so this is an inconvenience, not data loss.
- **The per-IP login lockout in `apps/api/app/auth.py` sees the tunnel's local connection, not the visitor's real IP** — Cloudflare forwards the original IP via a `CF-Connecting-IP` header, but this app doesn't read it yet, so behind a reverse proxy of any kind (Cloudflare included) the brute-force guard's IP-based bucketing is less precise than on a direct connection. Not a reason to avoid a reverse proxy, just worth knowing.
- If you'd rather use routed subdomains (`web.your-domain.com` / `api.your-domain.com`) instead of one hostname with a path split, that works too — just set `CORS_ORIGINS`/`NEXT_PUBLIC_API_URL` to the actual separate hostnames, since that setup *is* cross-origin from the browser's perspective.

## 3. Option B — Running natively

### Backend

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # or requirements.txt if you don't need the test suite
```

Point it at a running Postgres and Qdrant instance — see [requirements.md](requirements.md) for the full list. Easiest: copy `apps/api/.env.example` to `apps/api/.env` and edit it; the app loads that file automatically on startup (this is separate from the repo-root `.env` docker-compose reads — the two are never mixed).

```bash
cp .env.example .env   # then edit DATABASE_URL / QDRANT_URL / ADMIN_PASSWORD etc.
```

A plain `export DATABASE_URL=...` in your shell works too and always overrides whatever's in `.env`, if you prefer that instead.

Run migrations, then start the server:

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd apps/web
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local
npm run dev
```

Open http://localhost:3000.

Accessing this dev server (`npm run dev`, not the production build) through anything other than `localhost` — a LAN IP, a reverse-proxied custom domain — makes Next.js log a warning and block its own dev-only assets (HMR/websocket; this is unrelated to `CORS_ORIGINS`/the API). Set `NEXT_DEV_ALLOWED_ORIGINS` before starting it to allow that host:

```bash
NEXT_DEV_ALLOWED_ORIGINS=https://your-dev-domain.example npm run dev
```

## 4. First login

There is a single shared admin account, not per-user accounts — see [requirements.md](requirements.md) and the [user guide](user-guide.md#login) for why. Log in with username `admin` and whatever `ADMIN_PASSWORD` you configured. The Google/GitHub buttons on the login screen are intentionally disabled; there is no OAuth support.

## 5. Verifying the install

- `GET http://localhost:8000/api/v1/health` should return `{"status":"ok",...}` — this endpoint does not require login.
- The demo project ("恐竜時代文明開拓記 DEMO") should appear on the dashboard after logging in for the first time against a fresh database.
- Backend tests: `cd apps/api && pytest -q` (52 tests as of this writing).
- Frontend build/lint: `cd apps/web && npm run lint && npm run build`.

## API reference

The live interactive API docs (Swagger UI) are always at `http://localhost:8000/docs` while the server is running. For a static copy — to import into Postman/Insomnia, generate a client SDK, or review offline — see [docs/openapi.json](openapi.json), a plain OpenAPI 3.1 export. Regenerate it after changing any endpoint:

```bash
cd apps/api
python scripts/export_openapi.py
```

## Setting CORS_ORIGINS

`CORS_ORIGINS` is a comma-separated list of origins (`scheme://host:port`) the browser is allowed to call the API from. If it doesn't match the address you actually open the web app from, every API call — including login — fails with no obvious error (the browser blocks the request before it reaches the server). Three places can set it, checked in this order:

1. **The 設定 > 接続設定 (Settings > Connection settings) screen** — an override saved here beats everything else below. Blank the field and save to clear it and fall back to `.env`.
2. **`.env`** (Docker Compose, repo root) or **`apps/api/.env`** (native run — see [Option B](#3-option-b--running-natively)) — never both at once; each setup only reads its own file.
3. The code default, `http://localhost:3000`, if neither of the above set anything.

**Via Settings (recommended, no restart):** log in → 設定 > 接続設定 → set "CORS許可オリジン" → save. Takes effect on the very next request.

**Via `.env`:**
```
CORS_ORIGINS=http://localhost:3000,http://192.168.1.10:3000
```
For Docker Compose, recreate the `api` container after editing (`docker compose up -d` — a plain restart does not re-read `.env`). For a native run, `uvicorn --reload` picks up the edited `apps/api/.env` on its own restart.

**Writing the value:** it must exactly match what's in the browser's address bar — scheme, host, and port all included (`http` and `https` are different origins), no trailing slash. Multiple origins are comma-separated. `*` allows any origin (useful for debugging; don't leave it set on anything reachable from an untrusted network — see [requirements.md](requirements.md#cross-origin-access-cors_origins)).

**Checking what's actually in effect:**
```bash
curl -u admin:<password> http://localhost:8000/api/v1/system-settings
```
Look at `cors_origins` (the value currently used) and `cors_origins_is_override` (`true` means the Settings-screen override is active and `.env` is being ignored).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `docker compose up` fails immediately with an `ADMIN_PASSWORD` error | You didn't create `.env` from `.env.example`, or left `ADMIN_PASSWORD` unset |
| Dashboard stuck on "確認中..." / "起動中..." forever | The API isn't reachable at `NEXT_PUBLIC_API_URL`, or you're not logged in — check the browser's network tab for 401s vs connection errors |
| Login fails with "APIに接続できませんでした" / an `OPTIONS` request returns `400` | `CORS_ORIGINS` doesn't match the page's actual address — see [Setting CORS_ORIGINS](#setting-cors_origins) above. A Settings-screen override with a typo (e.g. a trailing `/`) beats a correct `.env` value, so check `cors_origins_is_override` too |
| Auto-write jobs immediately go to `error` with a connection message | Ollama isn't running, or `OLLAMA_URL`/`CONTROLLER_OLLAMA_URL` don't point at it (`http://host.docker.internal:11434` only resolves from inside Docker on Windows/macOS; on Linux use the host's LAN IP or run Ollama in the same Compose network) |
| `relation "projects" already exists` on `api` container startup | You have an old Postgres volume created before this project adopted Alembic migrations. Run `docker compose down -v` to reset it (**destroys all data**) or manually `alembic stamp head` against that database if you need to keep it |
| Search always falls back to "全文一致 (PostgreSQL フォールバック)" | Qdrant isn't reachable at `QDRANT_URL` — semantic search silently degrades to a plain `ILIKE` match instead of failing |
