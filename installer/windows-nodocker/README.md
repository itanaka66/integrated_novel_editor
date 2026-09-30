# No-Docker Windows installer

Produces `dist\INE-NoDocker-Setup-<version>.exe` — an alternative to
[`installer/windows`](../windows) for a machine that can't or shouldn't run
Docker Desktop. Everything INE needs (other than Ollama) is bundled and run
as plain Windows processes instead of containers:

| Component | Docker installer | This installer |
|---|---|---|
| API | Docker image (Python + Postgres driver) | `ine-api.exe` — `apps/api` frozen with PyInstaller (`desktop_main.py`), runs Alembic migrations in-process on launch |
| Database | PostgreSQL container | **SQLite**, a single file under `.\data\ine.db` |
| Vector search | Qdrant container | Bundled `qdrant.exe` (official Windows release binary) |
| Web | Docker image (Next.js) | `web\server.js` (Next.js `output: "standalone"` build) run by a bundled portable `node.exe` |
| Ollama | Host, not containerized either way | Same — still a separate prerequisite, not bundled |

No admin rights, no virtualization/WSL2 requirement, no Docker Hub/GHCR
pull at first launch — the trade-off is a larger installer (~85 MB
compressed) and no multi-user/production deployment story: SQLite is a
single-writer file database, fine for one person writing on their own
machine, not for the Postgres-backed Docker Compose setup's concurrent
multi-user or remote-server use cases (see [docs/installation.md](../../docs/installation.md)
for those).

## Build

```powershell
installer\windows-nodocker\build.ps1
```

Requires (see the script's own header comment for the full list):
a Python venv at `apps\api\.venv` with `apps/api/requirements.txt`
installed, Node.js (build-time only — `next build`), Inno Setup 6, and
internet access the first time (downloads and caches portable
`node.exe`/`qdrant.exe` under `.cache\`).

## Design notes worth knowing before touching this

- **`apps/api/desktop_main.py`** is the frozen entry point, not
  `app.main` directly — it resolves two different base directories
  (PyInstaller's `--onefile` unpacks to a temp dir on every launch;
  `.env`/the SQLite file/`novel_storage/` must instead live next to the
  installed `.exe` to persist between runs) and runs `alembic upgrade
  head` in-process (no `alembic` command is on PATH in a frozen build).
- **`launch.ps1`'s process-ID list is named `$processIds`, not `$pids`.**
  PowerShell variable names are case-insensitive, so `$pids` silently
  aliases the built-in `$PID` (the script's own process ID) — every
  `+=` onto it fights a read-only automatic variable instead of
  building a real list, and `.pids` (the tracking file `stop.ps1`
  reads) ends up never written. Cost a fair amount of debugging time
  once already; don't reintroduce it.
- `editor_common.db.create_db()` passes `check_same_thread=False` only
  for `sqlite://` URLs (see that repo's own history) — required because
  FastAPI runs sync request handlers in a thread pool, which a bare
  SQLite connection otherwise refuses to be used from.
- Qdrant's storage path/port are set via `QDRANT__STORAGE__STORAGE_PATH`
  / `QDRANT__SERVICE__HTTP_PORT` env vars in `launch.ps1`, not a config
  file — that's how the official binary takes overrides.
