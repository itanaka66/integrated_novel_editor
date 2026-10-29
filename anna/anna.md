# Anna AI OS Integration — まとめ

## アーキテクチャ

```
[Browser / INE Web App]
        │ HTTP
        ▼
[FastAPI Server (apps/api)]
        │ HTTP (INE REST API)
        ▲
        │
[Anna AI OS] ── stdio JSON-RPC 2.0 ──▶ [ine-bridge Executa]
        │                                      │
        │◀── sampling/createMessage ───────────┘
        │    (reverse RPC)
   [Anna LLM]
```

### 通信プロトコル

- **Anna → ine-bridge**: `invoke` (forward RPC, stdio)
- **ine-bridge → Anna LLM**: `sampling/createMessage` (reverse RPC, 同じ stdio)
- **ine-bridge → INE API**: HTTP REST (Basic 認証)
- プロトコルバージョン: **v2.0**

### initialize ハンドシェイク (公式仕様準拠)

```python
def handle_initialize(params):
    return {
        "protocolVersion": "2.0",
        "server_info": {"name": "INE Bridge", "version": "..."},
        "capabilities": {},
        "client_capabilities": {"sampling": {}},   # ← v2 必須
    }
```

manifest.json の静的宣言:
```json
{ "host_capabilities": ["llm.sample"] }
```

---

## ine-bridge バージョン履歴

| app ver | executa ver | plugin ver | 主な変更 |
|---------|-------------|------------|---------|
| 0.2.10  | 0.2.9       | 0.1.5      | sampling capability 宣言 |
| 0.2.12  | 0.2.10      | 0.1.6      | `generate_cover_prompt` 追加 |
| 0.2.13  | 0.2.11      | 0.1.7      | `proofread_episode` 追加 |
| 0.2.14  | 0.2.12      | 0.1.8      | protocol spec 修正（`client_capabilities`） |
| **0.2.15** | **0.2.13** | **0.1.9** | `add_ai_entities` 追加 ← 最新 |

---

## Anna LLM (reverse RPC) を使うツール一覧

### `generate_cover_prompt`
表紙画像用の英語プロンプトを生成。

```
generate_cover_prompt(project_id, style?)
```
- プロジェクト情報・キャラクター・最近のエピソードを参照
- 返却: `{prompt, project_id, style, source: "anna_sampling"}`

---

### `proofread_episode`
スタイルガイドに基づきエピソードを校正。

```
proofread_episode(episode_id, apply=false)
```
- プロジェクトのスタイルガイドが必要（未設定時はエラー）
- 返却: `{diffs: [{original, suggested, reason}], diff_count, applied}`
- `apply=true` で修正をエピソードに自動保存

**注意**: Web UI の「📐 文章校正」ボタンは無効（Ollama 必要）

---

### `add_ai_entities`
キャラクター・世界観などのエンティティを AI で生成・追加。

```
add_ai_entities(project_id, kind, count=10)
```

| kind | 追加先 | キーフィールド |
|------|--------|--------------|
| `characters` | /projects/{id}/characters | name |
| `world` | /projects/{id}/world | name |
| `glossary` | /projects/{id}/world (entity_type=glossary) | name |
| `plots` | /projects/{id}/plots | title |
| `foreshadowings` | /projects/{id}/foreshadowings | title |
| `timeline` | /projects/{id}/timeline | title |

- 既存行を取得して重複スキップ
- 返却: `{kind, project_id, created, items, source: "anna_sampling"}`

**注意**: Web UI の「＋ AIで10個追加」ボタンは無効（Ollama 必要）

---

### `auto_write_step`
自動執筆ジョブの LLM ステップを実行（既存ツール）。

```
auto_write_step(job_id, steps=5)
```
- Series plan → Arc plan → Mini Arc → Episode plan → Episode write の順に処理
- `done=true` になるまで繰り返し呼ぶ

---

### `generate` / `chat`（既存、sampling 対応済み）
sampling_token がある場合は Anna LLM を使用、ない場合は INE サーバー側にフォールバック。

---

## sampling 実装 (`_sample` 関数)

```python
def _sample(messages, *, system_prompt=None, max_tokens=4096) -> str:
    # sampling/createMessage を stdout に送信
    # stdin から response が来るまでブロック
    # invoke_id を metadata に echo（課金・監査用）
```

- `_sampling_token` は invoke の `context.sampling_token` から取得
- invoke 終了時に `None` にリセット
- sampling 中に届いた他メッセージは `_inbox_buffer` に退避

---

## サーバー側の LLM 利用状況

| 機能 | 現状 | 対応方法 |
|------|------|---------|
| 文章校正 | ❌ Ollama 必要 | Anna: `proofread_episode` |
| AI エンティティ追加 | ❌ Ollama 必要 | Anna: `add_ai_entities` |
| 表紙プロンプト生成 | ❌ Ollama 必要 | Anna: `generate_cover_prompt` |
| 自動執筆 | ✅ Anna sampling | `auto_write_step` |
| スタイルガイド生成 | ❌ Ollama 必要 | 未対応 |
| 翻訳 | ❌ Ollama 必要 | 未対応 |
| 連続性監査 | ❌ Ollama 必要 | 未対応 |

`ANNA_LLM_URL` を `.env` に設定すれば、サーバー側も Anna の LLM エンドポイントを使える可能性あり（要調査）。

---

## Web UI の変更点

| ボタン | 状態 | 理由 |
|--------|------|------|
| 📐 文章校正 | disabled | Ollama 不可 → Anna `proofread_episode` |
| ＋ AIで10個追加 | disabled | Ollama 不可 → Anna `add_ai_entities` |
| CSVテンプレート | ✅ 有効 | Ollama 不要 |
| CSVインポート | ✅ 有効 | Ollama 不要 |
| 小説に反映 | ✅ 有効 | Ollama 不要 |
| タイトルと著者名を画像に入れる (cover) | disabled | 画像生成未実装 |
| 複数画像作成 (cover) | disabled | 未実装 |

---

## Anna App リリース手順

```bash
cd anna/

# 1. ソース変更後、バイナリビルド（Windows）
cd executas/ine-bridge
pyinstaller --onefile --name integrated-novel-editor-ine-bridge _launcher.py

# 2. Linux バイナリ（Docker）
docker run --rm -v "$PWD:/build" -v "$PWD/dist:/output" python:3.12-bookworm \
  bash -c "pip install pyinstaller -e /build --quiet && \
  pyinstaller --onefile --name integrated-novel-editor-ine-bridge /build/_launcher.py && \
  cp /build/dist/integrated-novel-editor-ine-bridge /output/"

# 3. Anna に登録・スナップショット
cd ../../
anna-app apps push
anna-app apps cut X.Y.Z

# 4. リリース（手動実行が必要）
anna-app apps release X.Y.Z
```

**注意**: `anna-app apps release` は auto-mode でブロックされるため、ターミナルで手動実行。

---

## git ブランチ

- 作業ブランチ: `feature/anna`
- メインブランチ: `main`

本番デプロイ後に `feature/anna` → `main` へのマージ PR を作成予定。
