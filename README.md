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


## v0.5 Story Digital Twin

作品を「文章の集合」ではなく、人物・世界・時系列・プロット・伏線・キャラクター状態・連続性を統合したStory Digital Twinとして扱います。

### Digital Twin API
- `GET /api/v1/projects/{id}/story-twin`
- 統合メトリクス
- 作品健全性スコア
- キャラクター関係グラフ
- 世界観グラフ
- 時系列グラフ
- キャラクター状態履歴
- 未解決の連続性問題
- アクティブなプロット
- 未回収伏線

Story Digital Twin画面では、これらを1つの作品状態として俯瞰できます。
