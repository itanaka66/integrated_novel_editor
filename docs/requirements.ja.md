---
title: 動作要件
layout: default
---

[← マニュアルトップ](index.md) | [English](requirements.md)

# 動作要件

## 方式A — Docker（推奨）

| 要件 | バージョン | 補足 |
|---|---|---|
| Docker Engine | 24以上 | Docker Compose v2プラグイン(`docker compose`。古い`docker-compose`ではない)を含むこと |
| 空きディスク容量 | 10GB以上 | Postgres/Qdrantのボリューム＋ビルド済みイメージ |
| メモリ | 8GB以上 | 同じマシンでOllamaも動かす場合は16GB以上推奨 |

Windows/macOSはDocker Desktop、LinuxはDocker Engine + Composeプラグインのどちらでも動作します。

`db`（PostgreSQL）と`qdrant`は常時起動サービスではなくComposeの「プロファイル」です。すでに自前のPostgreSQL・Qdrantをお持ちの場合は、内蔵版を使わずに`DATABASE_URL`／`QDRANT_URL`を自前のインスタンスに向けられます。`scripts/setup.sh`／`setup.ps1`で対話的に選ぶか、`.env`の`COMPOSE_PROFILES`を直接編集してください。具体的なコマンドは[インストールマニュアル](installation.ja.md)の「方式A」を参照してください。

## 方式B — Dockerを使わずネイティブに構築する場合

| コンポーネント | 要件 |
|---|---|
| バックエンド（`apps/api`） | Python 3.13 |
| フロントエンド（`apps/web`） | Node.js 22、npm |
| データベース | PostgreSQL 17（15/16でもおそらく動作しますが、動作確認済みは17です） |
| ベクトルストア | Qdrant（比較的新しいバージョンであればOK。HTTP API経由で利用） |
| ローカルLLM実行環境 | [Ollama](https://ollama.com) |

ネイティブ構築でもOllamaと（ベクトル検索を使うなら）Qdrantは別途必要です。DockerはPostgres/Qdrant/アプリのコンテナだけを代替するもので、LLM実行環境（GPUを使うためほぼ常にホスト側で動かします）は含まれません。

## Ollamaモデル

| 役割 | 設定項目 | デフォルトモデル | 用途 |
|---|---|---|---|
| Writer（通常） | `OLLAMA_URL` / `OLLAMA_MODEL` | `qwen3:8b` | 執筆画面・AIチャットでの手動AI支援（続きを書く、要約、校正、カスタムプロンプト） |
| Writer（自動執筆） | ジョブごとの`writer_model`（既定値`qwen3.8:27b`） | `qwen3.8:27b` | 500話自動執筆ジョブでの本文生成。自動執筆画面でジョブごとに上書き可能 |
| Controller | `CONTROLLER_OLLAMA_URL` / `CONTROLLER_OLLAMA_MODEL` | `qwen3:14b` | Series/Arc/Mini Arc/Episode Plannerの計画立案と、自動執筆時の事前・事後品質チェック |
| 埋め込み | `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | RAGセマンティック検索の索引生成 |

ControllerとWriterは**同じ**Ollamaサーバー（モデル名だけ変える）でも、**別々の**Ollamaサーバー／GPUでも構いません。別マシンに分ける場合は`CONTROLLER_OLLAMA_URL`をそのマシンのアドレスに設定してください。大きめのモデル（`qwen3.8:27b`、`qwen3:14b`）を動かすには十分なVRAMを持つGPUが必要です。非力なマシンで導入する前に、Ollamaのモデル一覧でサイズを確認してください。

上記のQdrant URLと両方のOllamaのURL/モデルは、アプリの設定＞接続設定画面からも実行中に変更できます（[操作マニュアル](user-guide.ja.md#接続設定)参照）。多くの場合、環境変数を編集して再起動するよりこちらの方が手軽です。

## ローカルディスク／GitHubへのエピソード保存

| 設定項目 | デフォルト | 用途 |
|---|---|---|
| `NOVEL_STORAGE_DIR` | `./novel_storage` | エピソード本文が保存のたびにMarkdownとしてミラーされるディスク上の場所（エピソードごとに1ファイル） |
| `GIT_REMOTE_URL` | （未設定） | トークンを埋め込んだgitリモートURL（例：`https://<token>@github.com/<you>/<repo>.git`）。設定するとこのミラーがタイマーで自動コミット・プッシュされます。未設定の場合はディスクへのミラーのみでGitHub同期は行われません |
| `GIT_AUTOSYNC_INTERVAL_SECONDS` | `300` | 自動コミット・プッシュを実行する間隔（秒） |

## 自動バックアップ

| 設定項目 | デフォルト | 用途 |
|---|---|---|
| `BACKUP_ENABLED` | `false` | PostgreSQL＋Qdrantの自動バックアップループを有効化します。既定は無効。手動バックアップ（設定画面の「今すぐバックアップ」、または`scripts/backup.sh`）はどちらでも利用可能です |
| `BACKUP_DIR` | `./backups` | タイムスタンプ付きバックアップフォルダの保存先（Docker Compose／デスクトップインストーラ構成では既定でコンテナボリューム） |
| `BACKUP_INTERVAL_SECONDS` | `86400` | 自動バックアップの実行間隔（既定：1日ごと） |
| `BACKUP_RETENTION_COUNT` | `7` | 保持する直近バックアップの件数。それより古いものは実行のたびに自動削除されます |

リストアはコマンドライン操作（`scripts/restore.sh`）のみです。理由は[操作マニュアル](user-guide.ja.md#バックアップとリストア)を参照してください。

## クロスオリジンアクセス（CORS_ORIGINS）

| 設定項目 | デフォルト | 用途 |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000` | ブラウザからAPIへのアクセスを許可するオリジンのカンマ区切りリスト |

Webアプリを実際に開くオリジン（LAN内のIP、別のポート、独自ドメインなど）に合わせて設定してください。設定していないと、APIとWebアプリの両方に到達できていてもブラウザがリクエストをブロックします。複数指定する場合はカンマ区切りです（例：`http://localhost:3000,http://192.168.1.10:3000`）。

`*`を設定すると**任意のオリジン**を許可します（事実上この制限を無効化します）。どこからのリクエストか分からず切り分けたいときのデバッグ用途では便利ですが、このAPIは常に`Access-Control-Allow-Credentials`を送るため、もし過去に一度でもブラウザの標準認証ダイアログ（Basic認証のネイティブポップアップ。例えばAPIのURLを直接ブラウザで開いた場合など）でこのオリジンの認証情報を入力・キャッシュされたことがあると、`*`を設定している間は悪意あるサイトが被害者のブラウザ経由でその認証情報を使ってAPIを呼び出せてしまう可能性があります。信頼できないネットワークからアクセス可能な環境で`*`を設定したままにしないでください。

この値はアプリの「設定＞接続設定」画面からも、Qdrant・OllamaのURLと同じように再起動なしでその場で変更できます（[操作マニュアル](user-guide.ja.md#接続設定)参照）。すでにデプロイ済みで、ログインやAPI呼び出しが想定と違うオリジンから失敗していることに気づいた場合は、こちらの方が手軽です。`.env`の編集は、誰も設定画面を開く前の初回起動時にブラウザが最初に見るデフォルト値として、引き続き有効です。

## ブラウザが使うAPIのアドレス（NEXT_PUBLIC_API_URL）

| 設定項目 | デフォルト | 用途 |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Webアプリのビルド／コンテナ起動時にJavaScriptへ焼き込まれるAPIのURL |

ここに載っている他のほとんどの設定と異なり、この値はサーバーではなく**ブラウザ**が読みます——値が「localhost」だと、常に「訪問者自身のマシン」を指してしまい、アプリが実際にホストされている場所ではありません。Dockerを動かしているホスト自身以外（LAN内のIP、クラウドVMのアドレス、独自ドメインなど）からWebアプリにアクセスする場合は、そのアドレスの`:8000/api/v1`に設定する必要があります。設定しないと、ホスト上で直接ブラウザを開いた場合を除き、すべてのAPI呼び出しが静かに失敗します。`scripts/setup.sh`／`setup.ps1`は、入力したホスト名からこの値を自動設定します。後で変更する場合は`web`コンテナの作り直しが必要です（例：`docker compose up -d --build web`）——同じコンテナを再起動しただけでは新しい値は反映されません。

## 使用ポート

| ポート | サービス |
|---|---|
| 3000 | フロントエンド（Web） |
| 8000 | API（`/docs`でOpenAPIのインタラクティブUIも提供） |
| 5432 | PostgreSQL |
| 6333 / 6334 | Qdrant（HTTP / gRPC） |
| 11434 | Ollama（Docker Composeでは起動しません。ホスト側で起動してください） |

## ブラウザ

最新のChrome、Edge、Firefox、Safariのいずれか。IEおよび旧Edgeは非対応です。
