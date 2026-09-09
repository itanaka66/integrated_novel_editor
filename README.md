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


## v0.8 Autonomous 1→500 Writing

- Separate Ollama Controller / Writer architecture
- Controller default: `qwen3:8b`
- Writer default: `qwen3.8:27b`
- Generate episodes sequentially from 1 to 500
- Existing episodes are skipped by default; optional overwrite
- After each episode: Character State update + Qdrant indexing
- Every 5 episodes: continuity audit
- Start/stop/progress API and Web UI

### Dual Ollama environment

`OLLAMA_URL` / `OLLAMA_MODEL` control the Writer. `CONTROLLER_OLLAMA_URL` / `CONTROLLER_OLLAMA_MODEL` control the planning AI. They can point to the same Ollama server with different models, or to two separate Ollama servers.


## v0.8 Controller Quality Control
Controller Ollama is responsible for episode planning plus a subset of quality checks: timeline, character state, world setting, and plot consistency. It performs a preflight check before Writer generation and a draft gate after generation. BLOCK results trigger one repair/revision pass. Writer Ollama remains responsible for final prose generation.

## v0.9 Hierarchical Story Planner

A770 Controller now owns a four-level planning hierarchy:

- Series Planner: EP001-EP500
- Arc Planner: 5 × 100 episodes
- Mini Arc Planner: 50 × 10 episodes
- Episode Planner: 500 individual episode blueprints

The hierarchy is persisted in PostgreSQL. AutoWrite lazily expands only the Arc/Mini Arc/Episode plans needed for the requested episode range. RTX 3090 Writer receives the final Episode Blueprint. Controller remains responsible for timeline, character-state, world-setting and plot quality gates.

### Planner API

- `POST /api/v1/planner/series`
- `POST /api/v1/planner/arc`
- `POST /api/v1/planner/mini-arc`
- `POST /api/v1/planner/episode`
- `GET /api/v1/projects/{project_id}/planner`

### 500話Planner構造検証

A770 ControllerのSeries → Arc → Mini Arc → Episode階層には決定論的な構造バリデータを搭載しています。LLMが「5 Arc」「100話」「50 Mini Arc」「500 Episode」を正しく生成したかを、欠番・重複・範囲ずれまで自動検証します。
