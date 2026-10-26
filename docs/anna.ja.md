# Anna Framework 連携

INEは [Anna](https://anna.partners/developers) の App として使えます。stdio の Executa プラグイン、執筆コーチ用 Skill、小さなダッシュボードウィンドウです。

作品の正本はこれまでどおり INE（PostgreSQL、Qdrant、ローカル Ollama）にあります。Anna はそれらの代わりにはなりません。Anna のチャットで `#ine` と書くと、エージェントが `http://localhost:8000/api/v1`（または設定したオリジン）へツール経由でアクセスします。

## 同梱物

| 部品 | パス | 役割 |
|---|---|---|
| リスティング | [`anna/app.json`](../anna/app.json) | スラッグ `ine`、同梱 Executa |
| マニフェスト | [`anna/manifest.json`](../anna/manifest.json) | schema 3、UI とプロンプト追記 |
| Tool | [`anna/executas/ine-bridge/`](../anna/executas/ine-bridge/) | JSON-RPC 2.0（stdio）→ INE REST |
| Skill | [`anna/executas/novel-coach/SKILL.md`](../anna/executas/novel-coach/SKILL.md) | ツールの使い方 |
| UI | [`anna/bundle/`](../anna/bundle/) | ヘルス・作品・ストーリーツイン |

## ツール

`health`、`list_projects`、`get_project`、`create_project`、`get_story_twin`、`list_episodes`、`get_episode`、`create_episode`、`save_episode`、`list_characters`、`create_character`、`list_world`、`create_world`、`search`、`generate`、`chat`、`check_continuity`、`list_continuity_issues`、`start_auto_write`、`get_auto_write_job`、`stop_auto_write`。

資格情報: `INE_BASE_URL`（任意、既定 `http://localhost:8000`）、`INE_USERNAME`、`INE_PASSWORD`（Web と同じ HTTP Basic）。

## 動かし方

1. いつもどおり INE を起動する。
2. [`@anna-ai/cli`](https://www.npmjs.com/package/@anna-ai/cli) を入れ、`anna/` で `anna-app dev` を実行する。
3. Executa に 3 つの資格情報を設定する（stdio の煙テストなら環境変数でも可）。

詳細とプライバシー: [anna/README.md](../anna/README.md)。
