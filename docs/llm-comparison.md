# LLM呼び出し方式の比較：Ollama URL vs Reverse RPC

このプロジェクトにはLLMを呼び出す経路が2つある。INEサーバー側（Python FastAPI）が直接Ollamaを叩く経路と、ine-bridgeがAnnaのLLMをReverse RPCで借りる経路だ。どちらも同じプロンプトを流せるが、アーキテクチャが根本的に違う。

---

## 比較表

| 観点 | Ollama URL方式 | Reverse RPC（Anna sampling）方式 |
|------|---------------|----------------------------------|
| **実装の場所** | `apps/api/app/ollama.py`、`auto_writer.py` | `anna/executas/ine-bridge/ine_plugin.py` |
| **LLMの所有者** | INEサーバーが管理するローカルOllama（またはOpenAI互換API） | Annaが持つLLM（Anna App内のモデル） |
| **通信プロトコル** | HTTP POST `/api/generate`（Ollama REST API） | JSON-RPC 2.0 over stdio（`sampling/createMessage` リクエストをAnnaに送信） |
| **通信の向き** | INEサーバー → Ollama（アウトバウンド） | ine-bridge → Anna（**逆方向**：呼ばれた側がホストにリクエストを返す） |
| **呼び出しモデル** | 設定で指定したモデル（`qwen3.8:27b`、`qwen3:14b` など） | AnnaがセッションのLLMとして使用しているモデル（Anna App側の設定に依存） |
| **環境変数による切り替え** | `ANNA_LLM_URL` を設定するとOllama URLをAnnaのOpenAI互換エンドポイントで上書き可能 | 切り替え不要。Annaセッション外では使用できない（`_sampling_token` がない場合 RuntimeError） |
| **ブロッキング挙動** | 非同期（`async/await`）。FastAPIのイベントループ内で並列実行可能 | 同期ブロッキング。stdoutにリクエストを書き、stdinからレスポンスを `readline()` で待つ |
| **セッション依存** | なし。常に利用可能 | あり。Annaセッション内のinvoke中のみ有効（`_sampling_token` がグローバル変数で管理） |
| **コンテキスト長** | Writer: `num_ctx=65536`、`num_predict=32768`（固定オプション） | 呼び出し時に `maxTokens` で指定（ツールごとに異なる：4096〜8192） |
| **LLMキュー管理** | あり。`llm_queue.slot()` で Writer/Controller/Embed/Translator の同時実行数を制御 | なし。Annaが側でキューを管理する（ine-bridgeには制御コードなし） |
| **自動書き込みでの使われ方** | `auto_writer.py`：INEサーバー側がジョブを自走。LLM呼び出しも全てサーバー内で完結 | `auto_write_steps.py` + `ine_plugin.py`：サーバーはプロンプトを組んで返すだけ。実際のLLM呼び出しはine-bridge（→Anna）が行う |

---

## アーキテクチャ

### Ollama URL方式（INEサーバー自走）

```
Auto-write job（INEサーバー内で進行）
  → ollama.generate()  [HTTP POST /api/generate]
    → Ollamaプロセス（ローカル or リモートGPU）
      → テキスト返却
        → INEサーバーがDBに保存
```

`auto_writer.py` がジョブ全体を非同期ループで回す。各エピソードは次のフェーズを順番に実行する：

1. **Context build + 階層プランニング**（並列）— `asyncio.gather` でコンテキスト構築と Arc/Mini-arc/Episode計画を同時実行
2. **Controller preflight**（`controller_generate`）— 時系列・人物・世界観・プロットを事前監査
3. **Writer 本文生成**（`generate`）— 監査結果と上位計画を踏まえて本文を生成
4. **Controller final gate**（`controller_generate`）— 生成された本文を再監査。BLOCKなら再執筆
5. **Episode保存 + 後処理**（並列）— 文字状態更新・伏線更新・RAGインデックスを並列実行

### Reverse RPC方式（Annaが実行主体）

```
Annaセッション（ユーザーが「自動書き込み」を依頼）
  → ine-bridge invoke: auto_write_step
    → GET /auto-write/{id}/next-step  [INEサーバーからプロンプト取得]
      → sampling/createMessage  [stdoutでAnnaに送信 ← 逆方向]
        → Anna LLM（テキスト生成）
          → POST /auto-write/{id}/submit-step  [結果をINEサーバーに返却]
            → 次のstepへ（done=trueまでループ）
```

`auto_write_steps.py` はステートマシンとして機能する：
- `get_next_step()` — 現在のジョブ状態を読み、次に必要なプロンプトを返す（`step_id`付き）
- `apply_step_result()` — LLMが返したテキストを受け取り、DBに保存してジョブ状態を進める

ine-bridgeは `step_id` で冪等性を確保し、途中でセッションが切れても再開できる。

---

## どちらを使うか

### Ollama URL方式を選ぶとき

- INEサーバーが独立したGPU（RTX 3090 + A770など）を持っている
- Annaセッションなしでバックグラウンド処理したい
- `/auto-write/start` エンドポイントを直接叩くケース（Web UIからの操作など）

### Reverse RPCを選ぶとき

- ローカルGPUがない、またはAnnaのLLMを使いたい
- Annaチャット内で「〇〇話から書いて」と自然言語で指示したい
- `auto_write_step`・`generate`・`proofread_episode` などine-bridgeのツールから呼ぶケース

---

## ANNA_LLM_URL による統合

INEサーバーの `.env` に `ANNA_LLM_URL` を設定すると、`ollama.py` の `_resolve_writer_endpoint()` / `_resolve_controller_endpoint()` がローカルOllamaの代わりにそのURLを使う。これにより「Ollama URL方式」でもAnna互換API（OpenAI互換エンドポイント）を指せるようになり、サーバー自走とAnna呼び出しを同一エンドポイントに統合できる。

```env
# apps/api/.env
ANNA_LLM_URL=https://anna.partners/api/llm/v1
ANNA_LLM_API_KEY=sk-…
ANNA_LLM_MODEL=claude-sonnet-4-5  # 省略可: runtime_configのollama_modelを使用
```

`ANNA_LLM_URL` が設定されると Writer と Controller の両方がそのエンドポイントを使う（個別の `controller_ollama_url` は無視される）。

---

## コード上の対応関係

| 役割 | Ollama URL方式 | Reverse RPC方式 |
|------|---------------|-----------------|
| Writer LLM呼び出し | `ollama.generate(prompt, job.writer_model)` | `_sample([{"role":"user","content":{"type":"text","text":prompt}}])` |
| Controller LLM呼び出し | `ollama.controller_generate(prompt)` | 同上（ine-bridgeはWriter/Controllerを区別しない） |
| プロンプト構築 | `auto_writer.py` 内でインライン | `auto_write_steps.py` の `get_next_step()` が返す |
| 結果の受け取り | `await` で直接受け取る | `apply_step_result()` がstep_idで照合して受け取る |
| ジョブ状態管理 | `job.status` / `job.current_episode` をループ内で直接更新 | `job.pending_step_id` / `job.current_write_context` でステートマシン管理 |
| 停止チェック | `_check_stopped(db, job)` をループの各フェーズで呼ぶ | `get_next_step()` の先頭で `job.status == 'stopping'` を確認 |
