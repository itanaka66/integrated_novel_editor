# Anna App — Integrated Novel Editor

This folder is an [Anna](https://anna.partners/developers) app that connects Anna chat (and a small dashboard window) to a **running** Integrated Novel Editor instance.

INE stays the system of record. Anna does not embed Ollama, PostgreSQL, or the Next.js UI; the Executa plugin calls the INE REST API with the same HTTP Basic login the web app uses.

## Layout

```
anna/
├── app.json                 # store listing + bundled Executa paths
├── manifest.json            # schema 3 app manifest
├── bundle/                  # iframe dashboard (static SPA)
└── executas/
    ├── ine-bridge/          # JSON-RPC stdio tool → INE /api/v1
    └── novel-coach/         # SKILL.md writing protocol
```

## Prerequisites

1. INE is up (`docker compose up` or the desktop launcher) at `http://localhost:8000` (API) / `http://localhost:3000` (UI).
2. Node 22+ and the Anna CLI, if you want the local harness:

   ```bash
   npm i -g @anna-ai/cli
   anna-app doctor
   ```

## Credentials

Configure these on the Executa (Anna injects them into every `invoke`; for local stdio tests they can be environment variables):

| Name | Required | Default |
|---|---|---|
| `INE_BASE_URL` | no | `http://localhost:8000` |
| `INE_USERNAME` | yes | — |
| `INE_PASSWORD` | yes | — |

`INE_BASE_URL` is the API origin **without** `/api/v1`.

## Local harness

From this directory:

```bash
anna-app dev
```

Open the printed dashboard URL. Load works from the window, or `#ine` in chat.

Smoke-test the plugin without Anna:

```bash
cd executas/ine-bridge
echo '{"jsonrpc":"2.0","method":"describe","id":1}' | python ine_plugin.py
```

Invoke (needs a live INE and credentials):

```bash
# PowerShell
$env:INE_USERNAME='admin'; $env:INE_PASSWORD='your-password'
'{"jsonrpc":"2.0","id":2,"method":"invoke","params":{"tool":"list_projects","arguments":{}}}' | python ine_plugin.py
```

Plugin tests (stdlib + pytest, no INE process required):

```bash
cd executas/ine-bridge
python -m pytest -q
```

## Publish

Mint/publish through the Anna Developer Console (`anna-app validate`, then `anna-app publish`). `anna-app publish` rewrites `bundled:ine-bridge` / `bundled:novel-coach` to server-minted ids; keep the `bundled:` form in git.

## Privacy

The plugin sends requests only to `INE_BASE_URL`. It does not log passwords (stderr is captured by Anna — never print credentials). Episode text you fetch or generate is returned in tool results and is therefore visible to the Anna model for that turn.
