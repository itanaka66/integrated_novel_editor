# AI Novel Studio v0.3

AI-powered long-form novel IDE for 300–500+ episode stories.

## v0.3 highlights
- AI continuity checker: character / timeline / world / ability / foreshadowing contradictions
- Automatic character-state extraction after episode save
- Character state history by episode
- PostgreSQL as story truth, Qdrant as semantic memory, Ollama as local AI
- RAG + Context Builder + AI generation

## Quick start
```bash
docker compose up --build
```
Open `http://localhost:3000` and API docs at `http://localhost:8000/docs`.

For local Ollama:
```bash
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

> The first v0.3 implementation uses LLM JSON extraction for state updates and continuity findings. Always review AI findings before treating them as canonical story facts.
