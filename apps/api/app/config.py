import os
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
 # Real OS/container environment variables always win; a .env file here
 # (apps/api/.env — not the repo-root one docker-compose reads) is only a
 # convenience for running `uvicorn` natively from this directory without
 # having to `export` everything by hand every time — see .env.example.
 # Tests set NOVEL_SKIP_DOTENV so a developer's own apps/api/.env (real
 # LAN addresses, CORS_ORIGINS=*, etc.) never leaks into the test suite —
 # see tests/conftest.py.
 model_config=SettingsConfigDict(env_file=None if os.environ.get('NOVEL_SKIP_DOTENV') else '.env',env_file_encoding='utf-8',extra='ignore')
 database_url:str='postgresql+psycopg2://novel:novel@localhost:5432/novel'; qdrant_url:str='http://localhost:6333'; ollama_url:str='http://localhost:11434'; ollama_model:str='qwen3.8:27b'; ollama_embed_model:str='nomic-embed-text'; cors_origins:str='http://localhost:3000'
 admin_username:str='admin'; admin_password:str='novel-studio-change-me'
 controller_ollama_url:str='http://localhost:11434'; controller_ollama_model:str='qwen3:14b'
 # Sent as "Authorization: Bearer <key>" on every Ollama request (Writer/
 # embeddings and Controller respectively) when set — see
 # editor_common.ollama's module docstring. A bare local `ollama serve` has
 # no auth at all, so both are blank by default; set one only if your Ollama
 # sits behind something that does check one (a gated reverse proxy, a
 # hosted/cloud Ollama offering, an OpenAI-API-compatible gateway). Secrets
 # like this stay env/.env-only, never exposed or editable from 設定 >
 # 接続設定, unlike the URL/model overrides there.
 ollama_api_key:str=''; controller_ollama_api_key:str=''
 # OAuth2 ("Googleでログイン" / "GitHubでログイン") — see editor_common.oauth.
 # A provider only appears as a login option once BOTH its client_id and
 # client_secret are set (empty strings, the default, leave that provider
 # off entirely — no broken button, no startup requirement to configure
 # any of this). session_secret signs the login cookie those flows set
 # (editor_common.session_tokens) — change it from the placeholder before
 # exposing this beyond your own machine, the same way ADMIN_PASSWORD
 # needs to be. oauth_redirect_base_url must be the externally-reachable
 # *API* address (this is what Google/GitHub redirect back to after
 # consent, not what the browser opens) — it has to match, character for
 # character, the "Authorized redirect URI" registered with each provider.
 # oauth_login_redirect_url is the web app's own address, where the browser
 # ends up after a successful login.
 session_secret:str='change-me-session-secret'
 google_client_id:str=''; google_client_secret:str=''
 github_client_id:str=''; github_client_secret:str=''
 oauth_redirect_base_url:str='http://localhost:8000'
 oauth_login_redirect_url:str='http://localhost:3000'
 # Local-disk mirror of episode text, optionally auto-committed/pushed to a
 # git remote on a timer. git_remote_url takes a token embedded the way git
 # expects (https://<token>@host/owner/repo.git) or a plain URL if the
 # remote is otherwise authenticated (e.g. SSH agent, credential helper).
 novel_storage_dir:str='./novel_storage'
 git_remote_url:str=''; git_autosync_interval_seconds:int=300
 # Scheduled backups (PostgreSQL dump + Qdrant snapshot, mirroring what
 # scripts/backup.sh does manually). Off by default — opt in with
 # BACKUP_ENABLED=true so existing deployments don't suddenly start writing
 # to disk on a timer. Interval default is once a day; retention keeps the
 # N most recent backups and deletes older ones.
 backup_enabled:bool=False; backup_dir:str='./backups'; backup_interval_seconds:int=86400; backup_retention_count:int=7
 # Password-reset emails (POST /auth/forgot-password). smtp_host empty
 # (the default) means "no mail server configured" — the reset link is
 # logged instead of emailed, so forgot-password still works end-to-end
 # in dev/CI without any SMTP setup; see app/mailer.py. The reset link
 # points at oauth_login_redirect_url (the web app's own address) + a
 # /reset-password route, since that's already the externally-reachable
 # frontend address this app knows about.
 smtp_host:str=''; smtp_port:int=587; smtp_username:str=''; smtp_password:str=''; smtp_from:str='noreply@example.com'; smtp_use_tls:bool=True
 password_reset_max_age_seconds:int=3600
 # Book-cover generation (see app/cover.py). ComfyUI is a local server's HTTP
 # API; comfyui_checkpoint blank = use the first installed checkpoint.
 # Higgsfield needs "<api-key>:<api-secret>" from cloud.higgsfield.ai and the
 # optional `higgsfield-client` package; the key stays env/.env-only.
 covers_dir:str='./covers'
 comfyui_url:str='http://localhost:8188'; comfyui_checkpoint:str=''
 higgsfield_key:str=''; higgsfield_model:str='bytedance/seedream/v4/text-to-image'
settings=Settings()
