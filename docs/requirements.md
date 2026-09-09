# Software Requirements

## Option A — Docker (recommended)

| Requirement | Version | Notes |
|---|---|---|
| Docker Engine | 24+ | Includes the Docker Compose v2 plugin (`docker compose`, not the old `docker-compose`) |
| Disk space | 10 GB+ free | Postgres/Qdrant volumes + built images |
| RAM | 8 GB+ | 16 GB+ recommended if you also run Ollama on the same machine |

Docker Desktop (Windows/macOS) or Docker Engine + the Compose plugin (Linux) both work.

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
