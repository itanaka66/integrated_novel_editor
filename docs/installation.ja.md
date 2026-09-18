---
title: インストールマニュアル
layout: default
---

[← マニュアルトップ](index.md) | [English](installation.md)

# インストールマニュアル

先に [requirements.ja.md](requirements.ja.md) で動作要件を確認してください。

## 1. Ollamaのインストールとモデルの取得

Ollamaは常にホスト側で動かします（Docker Composeは起動しません）。以下のどちらの方式を選んでも、この手順は共通です。

1. https://ollama.com からOllamaをインストールします。
2. 使う予定のモデルを取得します。
   ```bash
   ollama pull qwen3:8b
   ollama pull qwen3.8:27b
   ollama pull qwen3:14b
   ollama pull nomic-embed-text
   ```
   `qwen3.8:27b`と`qwen3:14b`は大きなモデルです。執筆画面のAI支援（`qwen3:8b`）だけ使い、500話自動執筆機能はまだ使わないのであれば省略しても構いません。
3. 起動確認：`curl http://localhost:11434/api/tags` がJSONを返せばOKです。

## 2. 方式A — Docker Compose

```bash
git clone <このリポジトリのURL>
cd integrated_novel_editor
cp .env.example .env
```

`.env`を編集し、実際の`ADMIN_PASSWORD`を設定してください（未設定だとComposeが起動を拒否します。各変数の意味は[requirements.ja.md](requirements.ja.md)を参照）。Ollamaを別マシンで動かす場合は`OLLAMA_URL` / `CONTROLLER_OLLAMA_URL`も変更してください。`http://localhost:3000`以外（LAN内のIP、別のポート、独自ドメインなど）からWebアプリを開く場合は、`CORS_ORIGINS`もそのオリジンに設定してください。設定しないとブラウザがWebアプリからのAPI呼び出しをブロックします。

`.env`を手動で編集する代わりに、`./scripts/setup.sh`（Windowsでは`.\scripts\setup.ps1`）が同じ内容を対話形式で質問してくれます。以下の内蔵PostgreSQL/Qdrantコンテナを使うか外部の自前インスタンスに接続するか、Ollamaをどこで動かすかも含めて質問し、`.env`を自動生成します。何度でも再実行して答えを変更できます。

```bash
docker compose up --build
```

既定では4つのコンテナがビルド・起動します：`db`（Postgres）、`qdrant`、`api`（起動時に自動で`alembic upgrade head`を実行し、初回起動時にデモ作品を1件投入）、`web`。`db`と`qdrant`はComposeの*プロファイル*です。すでに自前のPostgreSQL・Qdrantを運用している場合は、内蔵版を使わずに済ませられます：`.env`の`COMPOSE_PROFILES`から`db`／`qdrant`を外し（または`scripts/setup.sh`／`setup.ps1`を実行して該当の質問に「いいえ」と答える）、`DATABASE_URL`／`QDRANT_URL`を自前のインスタンスに向けてください。この場合`api`と`web`だけが起動します。`COMPOSE_PROFILES`はコマンドライン一回限りの上書きにも使えます。例えば`docker compose --profile qdrant up --build`は、`.env`の内容に関わらず内蔵Qdrantだけを起動し（PostgreSQLは`DATABASE_URL`で指定した外部のものを使用）ます。ログが落ち着いたら以下を開きます。

- Webアプリ：http://localhost:3000
- APIインタラクティブドキュメント：http://localhost:8000/docs

ユーザー名`admin`と設定した`ADMIN_PASSWORD`でログインしてください。

停止：`docker compose down`。停止して**全データを削除**する場合：`docker compose down -v`。

### Linux: ガイド付きインストールスクリプト

Linuxには専用のデスクトップインストーラはありませんが、`./scripts/install-linux.sh`が上記の方式Aと同じ内容を一括のガイド付きで行います。Dockerの有無を確認し、無ければ[公式インストールスクリプト](https://docs.docker.com/engine/install/)でのインストールを提案します（`sudo`が必要な操作の前には必ず確認します）。Ollamaの有無も確認し、無ければ[公式インストールスクリプト](https://ollama.com)を提案します。その後`scripts/setup.sh`を実行し、最後に起動するかどうかも尋ねます。

```bash
git clone <このリポジトリのURL>
cd integrated_novel_editor
./scripts/install-linux.sh
```

何度でも再実行できます。

## 2b. 方式A2 — デスクトップインストーラ（Windows / macOS）

`git clone`やターミナル操作をしたくない場合は、[Releasesページ](https://github.com/itanaka66/integrated_novel_editor/releases)からインストーラをダウンロードしてください。

- **Windows**：`INE-Setup-<version>.exe`を実行します。コード署名証明書が無いため未署名で、SmartScreenが警告を出します。「詳細情報」→「実行」で進めてください。`%LOCALAPPDATA%\INE`（「すべてのユーザー用」を選んだ場合は`Program Files`）にインストールされ、スタートメニュー・デスクトップに「INEを起動」「INEを停止」ショートカットが作成されます。
- **macOS**：`INE-Setup-<version>.pkg`を開き、案内に従って進めます。未署名・未公証のため、初回はGatekeeperにブロックされます。`.pkg`を右クリック→「開く」で一度だけ回避してください。`/Applications`に「INEを起動.app」「INEを停止.app」がインストールされます。

いずれの場合も、[Docker Desktop](https://www.docker.com/products/docker-desktop/)は別途インストールが必要な前提条件です。先にインストールしてください。起動ショートカットはDockerの有無を確認し、起動していなければ立ち上げ、方式Aと同じ4つのコンテナを（ローカルビルドではなくGHCRの既成イメージをpullして）起動し、http://localhost:3000 を開きます。初回起動時にランダムな`ADMIN_PASSWORD`を生成してインストール先の`.env`に書き込み、一度だけダイアログで表示します。控えておいてください。このインストーラはOllamaを**インストールしません**。どちらの方式でも手順1は必須です。

このインストーラは方式Aを手軽にした薄いラッパーであり、別のデプロイ方式ではありません。インストール先に同じ形の`docker-compose.yml`/`.env`を書き込み、内部で`docker compose`を実行しているだけなので、本マニュアルや[requirements.ja.md](requirements.ja.md)の環境変数・ポート・トラブルシューティングの説明はそのまま当てはまります。設定画面の[接続設定](user-guide.ja.md#接続設定-1)も全く同じように使えます。

## 2c. 方式A3 — クラウド／リモートサーバー

方式A（Docker Compose）を自分のPCではなくリモートマシン（AWS/GCP/Azure/DigitalOceanなどのクラウドVM、またはSSHでログインできる任意のサーバー）で動かす方式です。自分以外の人からも、複数のマシンからもアクセスできるようになります。方式Aとの違いは、すべて「別のマシンから到達できるようにする」ための追加手順です。

1. **LinuxのVMを用意します。** Ubuntu 22.04／24.04が最も動作確認されています。RAM 8GB・ディスク10GB以上が最低要件です（[requirements.ja.md](requirements.ja.md)参照）。同じVMでOllamaも動かす場合はさらに必要です。
2. **上記のLinuxガイド付きスクリプト（`./scripts/install-linux.sh`）**、または方式Aの手動手順でINEをインストール・起動します。`scripts/setup.sh`が「アクセス用ホスト名／IP」を尋ねてきたら、`localhost`ではなく**VMのパブリックIPまたはドメイン名**を答えてください。これで`CORS_ORIGINS`と`NEXT_PUBLIC_API_URL`の両方が正しく設定されます。クラウド構築で最もよくある失敗はこの手順の誤りです（下記の注記も参照）。
3. **ファイアウォールを開放します。** ポート`3000`（Webアプリ）と`8000`（API）へのインバウンドTCP接続を、接続元（自分のIP、または本当に公開する必要があるなら`0.0.0.0/0`）から許可してください。多くのクラウドプロバイダでは、OSレベルのファイアウォール（`ufw`など）とは別に、管理コンソール側の「セキュリティグループ」的な設定も必要です。ポート`11434`（Ollama）はインターネットに公開しないでください（下記のセキュリティ注記参照）。
4. **Ollamaはどこで動かすべきか？** 同じVM上（GPU付きインスタンスタイプでないと小さいモデル以外は実用的な速度が出ません）か、すでに持っているGPUマシン（プライベートネットワーク／VPN経由でVMから到達可能）のどちらかです。実際に動かす場所に合わせて`OLLAMA_URL`／`CONTROLLER_OLLAMA_URL`を設定してください。
5. どのマシンからでも`http://<VMのIPまたはドメイン>:3000`を開き、いつも通りログインできます。

**なぜここで`NEXT_PUBLIC_API_URL`が特に重要なのか：** この値はWebアプリのJavaScriptに焼き込まれ、サーバーではなく**あなたのブラウザ**が読む値です。そのため値が「localhost」のままだと、常に「訪問者自身のPC」を指してしまい、VM上で直接ブラウザを開いた場合以外は全てのAPI呼び出しが静かに失敗します。`scripts/setup.sh`で答えたホスト名から自動的に設定されますが、このスクリプトを使わない場合は`docker compose up --build`の前に`.env`で手動設定してください（後で変更する場合は`web`コンテナの作り直しが必要です。例：`docker compose up -d --build web` — 新しく作られたコンテナでのみ置換が実行されるためです）。

**セキュリティ注記 — Ollamaには認証機能がありません。** ポートに到達できる人は誰でもあなたのGPUを使い、モデルが生成する内容を取得できてしまいます。ポート`11434`を絶対にインターネットへ直接公開しないでください。プライベートネットワークに留めるか、ファイアウォールでINEサーバーのIPだけに制限するか、SSHトンネル／VPN経由でアクセスするようにしてください。

**任意 — 独自ドメイン＋HTTPS化：** 上記の構成はカスタムポートでの平文HTTP配信であり、テストや信頼できる小規模チームでの利用には十分です。本格的に一般公開する場合は、[Caddy](https://caddyserver.com/)などのリバースプロキシをポート3000/8000の前段に置くことをお勧めします。Caddyは自分が所有するドメインに対して自動的にTLS証明書を取得・更新してくれるため、`:3000`／`:8000`のポート指定なしで`https://your-domain`だけでアクセスできるようになります。切り替えた際は`CORS_ORIGINS`／`NEXT_PUBLIC_API_URL`も`https://`のドメインに合わせて更新してください。

## 3. 方式B — ネイティブ構築

### バックエンド

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate   # Windowsの場合: .venv\Scripts\activate
pip install -r requirements-dev.txt   # テストが不要ならrequirements.txtでも可
```

起動中のPostgres・Qdrantを指すよう設定します（全項目は[requirements.ja.md](requirements.ja.md)参照）。一番簡単なのは`apps/api/.env.example`を`apps/api/.env`にコピーして編集する方法です。起動時にこのファイルが自動的に読み込まれます（Docker Composeが読むリポジトリルートの`.env`とは別物で、混ざることはありません）。

```bash
cp .env.example .env   # DATABASE_URL / QDRANT_URL / ADMIN_PASSWORD などを編集
```

シェルで`export DATABASE_URL=...`する方法でも構いません。その場合は`.env`の値より優先されます。

マイグレーションを実行してからサーバーを起動します。

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### フロントエンド

```bash
cd apps/web
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local
npm run dev
```

http://localhost:3000 を開きます。

この開発サーバー（`npm run dev`。本番ビルドではない）に`localhost`以外（LAN内のIP、リバースプロキシ経由の独自ドメインなど）でアクセスすると、Next.jsが警告を出し、開発用のアセット（HMR/websocket。`CORS_ORIGINS`やAPIとは無関係）へのアクセスをブロックします。起動前に`NEXT_DEV_ALLOWED_ORIGINS`を設定すると許可できます：

```bash
NEXT_DEV_ALLOWED_ORIGINS=https://your-dev-domain.example npm run dev
```

## 4. 初回ログイン

ユーザーごとのアカウントではなく、共有の管理者アカウントが1つだけ存在します（理由は[requirements.ja.md](requirements.ja.md)と[操作マニュアルのログイン項目](user-guide.ja.md#ログイン)を参照）。ユーザー名`admin`と設定した`ADMIN_PASSWORD`でログインしてください。ログイン画面のGoogle/GitHubボタンは意図的に無効化されています。OAuthには対応していません。

## 5. 動作確認

- `GET http://localhost:8000/api/v1/health` が `{"status":"ok",...}` を返すこと（このエンドポイントはログイン不要）。
- 新規データベースで初めてログインした際、ダッシュボードにデモ作品（「恐竜時代文明開拓記 DEMO」）が表示されること。
- バックエンドのテスト：`cd apps/api && pytest -q`（執筆時点で52件）。
- フロントエンドのビルド/lint：`cd apps/web && npm run lint && npm run build`。

## API仕様書

サーバー起動中は、常に`http://localhost:8000/docs`でインタラクティブなAPIドキュメント（Swagger UI）を確認できます。Postman/Insomniaへのインポートやクライアントコード生成、オフラインでの確認用に、静的ファイルとして書き出したものは[docs/openapi.json](openapi.json)にあります（プレーンなOpenAPI 3.1形式）。エンドポイントを変更した後は再生成してください：

```bash
cd apps/api
python scripts/export_openapi.py
```

## CORS_ORIGINSの設定方法

`CORS_ORIGINS`は、ブラウザからこのAPIを呼び出すことを許可するオリジン（`スキーム://ホスト:ポート`）のカンマ区切りリストです。実際にWebアプリを開いているアドレスと一致していないと、ログインを含む全てのAPI呼び出しが、分かりやすいエラーも出さずに失敗します（ブラウザがサーバーに届く前にリクエストをブロックするため）。設定できる場所は3つあり、以下の順に優先されます：

1. **設定＞接続設定画面での上書き** — 保存すると、以下のどの設定よりも優先されます。空欄で保存すると上書きを解除し、`.env`の値に戻ります。
2. **`.env`**（Docker Compose・リポジトリルート）または **`apps/api/.env`**（ネイティブ実行時。[方式B](#3-方式b--dockerを使わずネイティブに構築する場合)参照）— 両方同時に読まれることはなく、それぞれの構成が自分のファイルのみを見ます。
3. どちらも設定していない場合のコード上のデフォルト値`http://localhost:3000`。

**設定画面から変更する場合（おすすめ・再起動不要）：** ログイン → 設定＞接続設定 →「CORS許可オリジン」を設定 → 保存。次のリクエストから即座に反映されます。

**`.env`で設定する場合：**
```
CORS_ORIGINS=http://localhost:3000,http://192.168.1.10:3000
```
Docker Composeの場合は編集後に`api`コンテナを作り直してください（`docker compose up -d`。単なる再起動では`.env`は再読み込みされません）。ネイティブ実行の場合、`uvicorn --reload`が編集済みの`apps/api/.env`を検知して自動的に再起動時に反映します。

**値の書き方：** ブラウザのアドレスバーに表示される値と完全に一致させてください（スキーム・ホスト・ポート全て。`http`と`https`は別オリジンです）。末尾に`/`は付けません。複数指定はカンマ区切りです。`*`を指定すると全オリジンを許可します（デバッグ用途。信頼できないネットワークに公開する環境では避けてください。詳しくは[requirements.ja.md](requirements.ja.md#クロスオリジンアクセスcors_origins)参照）。

**実際に有効な値を確認する方法：**
```bash
curl -u admin:パスワード http://localhost:8000/api/v1/system-settings
```
`cors_origins`（現在有効な値）と`cors_origins_is_override`（`true`なら設定画面の上書きが有効で、`.env`の値は無視されています）を確認してください。

## トラブルシューティング

| 症状 | 想定される原因 |
|---|---|
| `docker compose up`が`ADMIN_PASSWORD`エラーで即失敗する | `.env.example`から`.env`を作成していない、または`ADMIN_PASSWORD`が未設定 |
| ダッシュボードが「確認中...」「起動中...」のまま固まる | `NEXT_PUBLIC_API_URL`にAPIが到達できていない、またはログインできていない（ブラウザのネットワークタブで401か接続エラーかを確認） |
| ログインが「APIに接続できませんでした」で失敗する／`OPTIONS`リクエストが`400`を返す | `CORS_ORIGINS`がページの実際のアドレスと一致していません。上記の[CORS_ORIGINSの設定方法](#cors_originsの設定方法)を参照してください。設定画面の上書き値にタイプミス（末尾の`/`など）があると、`.env`側が正しくても優先されてしまうため、`cors_origins_is_override`も確認してください |
| 自動執筆ジョブがすぐに`error`になり接続エラーが表示される | Ollamaが起動していない、または`OLLAMA_URL`/`CONTROLLER_OLLAMA_URL`が誤っている（`http://host.docker.internal:11434`はWindows/macOSのDocker内からのみ解決可能。Linuxではホストのアドレスを別途指定するか、Ollamaを同じComposeネットワークで動かしてください） |
| `api`コンテナ起動時に`relation "projects" already exists`エラー | このプロジェクトがAlembic導入前に作られた古いPostgresボリュームが残っています。`docker compose down -v`でリセット（**全データ削除**）するか、データを残したい場合はそのDBに対して手動で`alembic stamp head`を実行してください |
| 検索が常に「全文一致 (PostgreSQL フォールバック)」になる | `QDRANT_URL`にQdrantが到達できていません。セマンティック検索は失敗時に単純な`ILIKE`一致検索へ自動的に切り替わります |
