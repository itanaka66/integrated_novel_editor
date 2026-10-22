# 自動執筆（Auto-writer）フロー

## 概要

`apps/api/app/auto_writer.py` が実装する自動執筆エンジン。  
1 話ずつ **6 フェーズ** で処理し、フェーズ 1・6 で並列実行することで待機時間を削減する。

---

## 全体フロー図

```
run_job(job_id)
│
├── [前処理] Series Planner: EP.1-500 の全体構成を確認・生成（1回のみ）
│
└── for n in [resume_from … end_episode]:
      │
      ├── Phase 1 ──────────────────────────── [並列]
      │   ├── Context Build          ← RAG 検索 + DB スナップショット
      │   │   (isolated session)       ├ キャラクター / 世界観 / プロット / 伏線
      │   │                            └ Qdrant 意味検索 (上位 8 件)
      │   └── Hierarchical Planning  ← メインセッション
      │       ├ ensure_arc   (100 話単位)
      │       ├ ensure_mini  (10 話単位)
      │       └ ensure_episode (1 話単位)
      │
      ├── Phase 2 ─ Controller Preflight ─── [逐次]
      │   └─ BLOCK 時: Episode Plan を修正して再実行
      │
      ├── Phase 3 ─ Writer 本文生成 ────────── [逐次]
      │   (Writer モデル / RTX3090)
      │
      ├── Phase 4 ─ Controller Final Gate ─── [逐次]
      │   └─ BLOCK 時: Writer 再執筆 → Controller 再審査
      │
      ├── Phase 5 ─ エピソード保存 ────────── [逐次]
      │   DB に INSERT / UPDATE してコミット
      │
      └── Phase 6 ──────────────────────────── [並列]
          ├── update_plot_statuses       ← ルールベース (同期、高速)
          ├── _post_char_states          ← AI でキャラクター状態抽出
          │   (isolated session)           → CharacterState テーブルに書き込み
          ├── _post_foreshadow           ← AI で伏線 setup / resolved 検出
          │   (isolated session)           → Foreshadowing テーブルに書き込み
          └── index(ep_chunks)           ← Qdrant RAG インデックス更新

          [5 話ごと] check_continuity    ← 全体整合性チェック (AI)
```

---

## フェーズ詳細

### 前処理 — Series Plan（1 回のみ）

| 処理 | モデル | 出力 |
|---|---|---|
| `planner.ensure_series` | Controller モデル | `SeriesPlan`（500 話全体方針） |

SeriesPlan が DB に存在する場合はスキップ。

---

### Phase 1 — Context Build + Hierarchical Planning（**並列**）

```
asyncio.create_task(_build_ctx_isolated(...))   ← 別セッションで並列開始
      │
      ↓  同時進行  ↓
ensure_arc   →  ensure_mini  →  ensure_episode   ← メインセッション（逐次）
      │
ctx = await ctx_task                              ← 合流
```

**依存関係**  
- `ensure_mini` は `ensure_arc` の結果を使う（内部で呼び出し）  
- `ensure_episode` は `ensure_mini` の結果を使う（内部で呼び出し）  
- `build()` (context) は上記すべてと独立 → **並列実行可能**

**各 Plan の生成条件**  

| Plan | 生成タイミング | AI 呼び出し |
|---|---|---|
| `SeriesPlan` | 初回のみ | Controller モデル（高速） |
| `ArcPlan` | アーク切り替え時（100 話ごと）| Controller モデル |
| `MiniArcPlan` | ミニアーク切り替え時（10 話ごと）| Controller モデル |
| `EpisodePlan` | 毎話（未存在時のみ生成）| Controller モデル |

キャッシュ済みの場合は DB から即返却（LLM 呼び出しなし）。

---

### Phase 2 — Controller Preflight

- **担当**: 時系列・人物状態・世界観・プロットの4項目のみ（文章表現は対象外）
- **判定**:  
  - `PASS` / `WARN` → そのまま Phase 3 へ  
  - `BLOCK` → Episode Plan を修正して再実行（1 回のみ）

---

### Phase 3 — Writer 本文生成

- **入力**: Series / Arc / Mini Arc / Episode Blueprint + Controller 制約 + Story Digital Twin
- **出力**: 完成した日本語小説本文

Writer モデルは `job.writer_model`（通常 `qwen3.8:27b` / RTX3090）で実行。

---

### Phase 4 — Controller Final Gate

- 本文が上位計画・Story Twin と整合しているか監査
- **判定**:  
  - `PASS` / `WARN` → Phase 5 へ  
  - `BLOCK` → Writer 再執筆 → Controller 再審査（1 回のみ）

---

### Phase 5 — エピソード保存

```python
# 新規 or 上書き（overwrite=True の場合）
Episode.insert / update → ep_obj.status = 'completed' → db.commit()
```

---

### Phase 6 — Post-processing（**並列**）

```
update_plot_statuses(db, pid, n)     # 同期・高速・メインセッション
asyncio.gather(
    _post_char_states(pid, ep_id),   # isolated session
    _post_foreshadow(pid, ep_id),    # isolated session
    index(ep_chunks),                # Qdrant only (DB 不要)
    return_exceptions=True,          # 失敗しても次話へ進む
)
```

| タスク | 処理内容 | セッション |
|---|---|---|
| `update_plot_statuses` | `start_episode` 到達 → `active`、`end_episode` 超過 → `completed` | メイン |
| `_post_char_states` | AI でエピソードからキャラクター状態を抽出し `CharacterState` に書き込み | 分離 |
| `_post_foreshadow` | AI で伏線の「設置」「回収」を検出し `Foreshadowing.status` を更新 | 分離 |
| `index(ep_chunks)` | エピソード本文を Qdrant に埋め込みインデックス | なし |

**5 話ごとに** `check_continuity` を実行し、`ContinuityIssue` テーブルに記録。

---

## 並列化による効果

```
[Before]                          [After]
─────────────────────────────     ──────────────────────────────
build()         ████              build()         ████
ensure_arc          ██            ensure_arc      ████  (overlap)
ensure_mini           ██          ensure_mini         ██
ensure_episode          ██        ensure_episode        ██
Controller Pre            ███     Controller Pre          ███
Writer                      ████  Writer                    ████
Controller Gate               ██  Controller Gate              ██
char_states                    ██ char_states    ████
foreshadow                      █ foreshadow     ████  (overlap)
index                           █ index          ████  (overlap)
─────────────────────────────     ──────────────────────────────
                 長い →                           短い ←
```

- **Phase 1**: `build()` の RAG 検索（通常 1〜3 秒）がプランニングと重なる
- **Phase 6**: キャラクター状態 AI・伏線 AI・RAG インデックスが並列実行

---

## 停止制御

各 Phase の間に `_check_stopped(db, job)` を呼び、`job.status == 'stopping'` の場合は `'stopped'` に遷移して即終了。最終エピソードの後処理後にも 1 回確認する。

---

## エラー処理

| 箇所 | 動作 |
|---|---|
| Phase 6 (gather) | `return_exceptions=True` — 各タスクの失敗はログに残し次話へ継続 |
| continuity check | `try/except` — 失敗しても次話へ継続 |
| ジョブ全体 | 未捕捉例外は `job.status = 'error'` として記録 |

---

## 関連ファイル

| ファイル | 役割 |
|---|---|
| `apps/api/app/auto_writer.py` | メインエンジン（本ドキュメント） |
| `apps/api/app/planner/planner_service.py` | 階層プランナー (Series/Arc/Mini/Episode) |
| `apps/api/app/context.py` | Story Digital Twin コンテキストビルダー |
| `apps/api/app/continuity.py` | キャラクター状態・プロット・伏線同期、整合性チェック |
| `apps/api/app/ollama.py` | Ollama LLM 呼び出しラッパー |
| `apps/api/app/rag.py` | Qdrant RAG 検索・インデックス |
