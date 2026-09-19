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

### 任意 — ポート開放の代わりにCloudflare Tunnelを使う

[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)（`cloudflared`）は、上記のファイアウォール開放の手間を避けたい場合、特に自宅サーバーやNAT配下・動的IPのマシン（固定の公開アドレスを持たない「サーバー」）に向いた代替手段です。サーバー上で常駐する小さなプロセスがCloudflareへ**アウトバウンド**接続を張るだけで済むため、**インバウンドのポートを一切開放する必要がありません**（上記の手順3自体が不要になります）。HTTPS終端もCloudflareのエッジ側で行われるため、オリジン証明書の管理も不要です。

1. **ドメインをCloudflareに追加**します（Freeプランで構いません）。まだの場合はネームサーバーをCloudflareに向けてください。
2. **`cloudflared`をインストール**します。`docker compose`を動かしている同じマシンに入れ、ログインしてトンネルを作成します：
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create ine
   ```
3. **1つのホスト名でWebアプリとAPIの両方をルーティング**します。パスによる振り分けにすることで、ブラウザから見て両者が常に同一オリジンになるようにできます。`~/.cloudflared/config.yml`を作成：
   ```yaml
   tunnel: ine
   credentials-file: /home/<user>/.cloudflared/<TUNNEL_ID>.json

   ingress:
     - hostname: novel.your-domain.com
       path: ^/api/.*
       service: http://localhost:8000
     - hostname: novel.your-domain.com
       service: http://localhost:3000
     - service: http_status:404
   ```
   `cloudflared`は上から順にingressルールを評価し、最初に一致したものを使うため、同じホスト名に対する`path`指定ルールは、それを持たないルールより**必ず上**に書いてください。
4. **DNSレコードを作成し、サービスとして常駐させます：**
   ```bash
   cloudflared tunnel route dns ine novel.your-domain.com
   sudo cloudflared service install
   sudo systemctl enable --now cloudflared
   ```
5. **`.env`をこの1つのホスト名に合わせて更新**し、`NEXT_PUBLIC_API_URL`を焼き込み直すためコンテナを作り直します（`docker compose up -d --build`）：
   ```
   CORS_ORIGINS=https://novel.your-domain.com
   NEXT_PUBLIC_API_URL=https://novel.your-domain.com/api/v1
   ```
   WebアプリとAPIが同じホスト名（パスの`/api/...`部分だけが違う）を共有するため、ブラウザからは同一オリジンとして見えます。別ポート・別サブドメイン構成のときによくある失敗点である`CORS_ORIGINS`の不一致は、この構成ではほぼ気にする必要がなくなります。
6. どこからでも`https://novel.your-domain.com`を開いてログインしてください。

#### `cloudflared`をホストに直接インストールせず、Dockerコンテナとして動かす

上記の手順1〜3はそのままです（`cloudflared tunnel login`/`tunnel create`は、認証して`~/.cloudflared/<TUNNEL_ID>.json`を作成するために、やはり一度だけCLIが必要です）。変わるのはトンネルの**動かし方**だけで、`cloudflared service install`の代わりに公式イメージを使います。`docker-compose.yml`に、`db`/`api`/`web`と並べて次のサービスを追加してください：

```yaml
  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel run ine
    volumes:
      - ~/.cloudflared:/etc/cloudflared:ro
    environment:
      TUNNEL_CONFIG: /etc/cloudflared/config.yml
    depends_on:
      - api
      - web
    restart: unless-stopped
```

**ホスト直接インストールとの重要な違いが1つあります。** `config.yml`は同じ`~/.cloudflared/`ディレクトリ（上記で読み取り専用マウント）に置いたうえで、`service:`の向き先を`http://localhost:8000`/`:3000`から、Composeの**サービス名**である`http://api:8000`・`http://web:3000`に変更してください。`cloudflared`コンテナの中では`localhost`はそのコンテナ自身を指し、他のコンテナを指しません。`api`/`web`という名前で正しく解決できるのは、同じ`docker-compose.yml`内のサービスがComposeによって自動的に同じDockerネットワークに置かれるためです：

```yaml
tunnel: ine
credentials-file: /etc/cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: novel.your-domain.com
    path: ^/api/.*
    service: http://api:8000
  - hostname: novel.your-domain.com
    service: http://web:3000
  - service: http_status:404
```

あとは`docker compose up -d`を実行するだけで、他のサービスと一緒にトンネルも起動します。ホスト側に`systemctl`も個別インストールも一切不要です。`docker compose logs -f cloudflared`で接続状況を確認でき、`config.yml`を編集した際は`docker compose restart cloudflared`で反映されます。

**Cloudflare配下（Tunnelに限らず）での既知の制限：**
- **自動執筆の進捗を表すSSEのような長時間接続は、Cloudflareの無料／Proプランでは約100秒でエッジ側から切断されることがあります。** これはこのアプリとは無関係な、Cloudflareのプロキシ自体が持つHTTP接続のタイムアウトです。自動執筆ジョブ自体はサーバー側のバックグラウンドタスクとして動作し続けるため（そのブラウザ接続に紐づいてはいません）、切れるのはブラウザへの**リアルタイム進捗表示**だけです。自動執筆画面を開き直せばジョブの現在の状態を再取得するので、データ消失ではなく単なる不便さです。
- **`apps/api/app/auth.py`のIPごとのログイン失敗回数制限は、訪問者の本当のIPではなくトンネル側のローカル接続を見ています。** Cloudflareは`CF-Connecting-IP`ヘッダーで元のIPを転送してきますが、このアプリはまだそれを読んでいないため、Cloudflare（に限らずリバースプロキシ全般）配下では、直接接続時と比べてIPベースの総当たり対策の精度が落ちます。リバースプロキシを使わない理由にはなりませんが、知っておく価値はあります。
- 1つのホスト名＋パス分割の代わりに、サブドメインで振り分ける構成（`web.your-domain.com`／`api.your-domain.com`）でも構いません。その場合は`CORS_ORIGINS`／`NEXT_PUBLIC_API_URL`を実際の別々のホスト名に設定してください——この構成はブラウザから見て**クロスオリジン**になるためです。

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

ユーザー名`admin`と設定した`ADMIN_PASSWORD`でログインしてください。`users`テーブルが空の状態で初回起動すると、このアカウントが自動的に作成されます。Basic認証の追加アカウントを手動で作るUIはまだありませんが、Google/GitHubログイン（下記）は初回利用時に自動でアカウントを作成します。

### 任意 — OAuth2ログイン（Google／GitHub）

ログイン画面のGoogle/GitHubボタンは、該当プロバイダーの`_CLIENT_ID`／`_CLIENT_SECRET`を設定すると有効になります（全項目は[requirements.ja.md](requirements.ja.md#oauth2ログインgooglegithub)参照）。両方とも空欄のままなら、これまで通り無効化されたプレースホルダーのままです。設定手順：

1. **プロバイダー側でOAuthアプリを作成：**
   - Google：[Google Cloud Console](https://console.cloud.google.com/apis/credentials) →「認証情報を作成」→「OAuthクライアントID」→「ウェブアプリケーション」
   - GitHub：[github.com/settings/developers](https://github.com/settings/developers) →「New OAuth App」
2. **リダイレクトURIを正確に**`<OAUTH_REDIRECT_BASE_URL>/auth/callback/google`（または`/github`）**に設定**してください——これはWebアプリではなく**API**の外部到達可能なアドレスです。ローカルのDocker Compose構成であれば`http://localhost:8000/auth/callback/google`になります。ここが1文字でもズレる（末尾のスラッシュ、ポート番号、`http`と`https`の違いなど）と、プロバイダー側の独自エラー画面が出るだけで分かりにくいので、最もよくある失敗ポイントです。
3. **発行されたクライアントID/シークレット、`OAUTH_REDIRECT_BASE_URL`、`OAUTH_LOGIN_REDIRECT_URL`を`.env`に設定**し、`SESSION_SECRET`もプレースホルダーから変更してください——ログインクッキーの署名に使われる値で、`ADMIN_PASSWORD`と同じ考え方です。
4. `api`コンテナを作り直してください（`docker compose up -d --build api`）——これらは起動時に一度だけ読み込まれる設定で、設定画面から実行時に変更することはできません。

Google/GitHubで初めてログインすると、メールアドレスのローカル部をユーザー名としてアカウントが自動作成されます（パスワードなし——そのプロバイダー経由でのみログイン可能）。別途「招待」の手順は不要です。

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

`CORS_ORIGINS`は、ブラウザからこのAPIを呼び出すことを許可するオリジン（`スキーム://ホスト:ポート`）のカンマ区切りリストです。実際にWebアプリを開いているアドレスと一致していないと、ログインを含む全てのAPI呼び出しが、分かりやすいエラーも出さずに失敗します（ブラウザがサーバーに届く前にリクエストをブロックするため）。これは**環境変数のみ**で設定します。Qdrant・OllamaのURLとは異なり、設定＞接続設定画面からは意図的に変更できません——どのオリジンにAPIへのアクセスを許可するかというセキュリティ上の制御であり、単なる接続先の便宜的な設定ではないためです（詳しくは[requirements.ja.md](requirements.ja.md#クロスオリジンアクセスcors_origins)参照）。

**設定方法：**
- Docker Composeの場合：リポジトリルートの`.env`で`CORS_ORIGINS`を編集後、`api`コンテナを作り直します（`docker compose up -d`。単なる再起動では`.env`は再読み込みされません）。
- ネイティブ実行の場合：`apps/api/.env`（[方式B](#3-方式b--dockerを使わずネイティブに構築する場合)参照）で編集。`uvicorn --reload`が検知して自動的に再起動時に反映します。
- どちらも未設定の場合はコード上のデフォルト値`http://localhost:3000`が使われます。

**値の書き方：** ブラウザのアドレスバーに表示される値と完全に一致させてください（スキーム・ホスト・ポート全て。`http`と`https`は別オリジンです）。末尾に`/`は付けません。複数指定はカンマ区切りです。`*`を指定すると全オリジンを許可します（デバッグ用途。信頼できないネットワークに公開する環境では避けてください）。

**実際に有効な値を確認する方法：**
```bash
curl -u admin:パスワード http://localhost:8000/api/v1/system-settings
```
レスポンスの`cors_origins`が現在有効な値です（読み取り専用——このエンドポイントに`PUT`で送っても変更されません）。

## アップグレード方法

```bash
git pull
docker compose up -d --build
```

通常はこれで十分です。Dockerは、実際に内容が変わったファイルを含むコンテナだけを再ビルドします。ただし1つだけ例外があります。**`apps/api/requirements.txt`は共有ライブラリ`editor_common`を、バージョン番号ではなく`git+...@main`という「動く」参照でピン留めしています**（`editor-common @ git+https://github.com/itanaka66/editor-common-module.git@main`）。この*上流リポジトリ側*にだけ新しいコミットが追加された場合——`requirements.txt`自体のテキストは変わらないため——Dockerのレイヤーキャッシュは`COPY requirements.txt`のステップを「変更なし」と判断して`pip install`を再実行せず、`api`コンテナはビルド時点の`editor_common`のまま動き続けます。上流側の変更を静かに取りこぼしたまま、というわけです。この症状は、一見正しく見えるコードから`TypeError: ... got an unexpected keyword argument '...'`のようなエラーが出る、という形で現れます——このアプリのコード自体は、コンテナに実際にインストールされているものより新しい`editor_common`のAPIを呼び出している、ということです。この状況が疑われる場合は明示的に強制してください：

```bash
docker compose build --no-cache api
docker compose up -d api
```

実際に稼働中のコンテナにどのバージョンが入っているか確認するには：

```bash
docker compose exec api pip show editor-common
```

## トラブルシューティング

| 症状 | 想定される原因 |
|---|---|
| `docker compose up`が`ADMIN_PASSWORD`エラーで即失敗する | `.env.example`から`.env`を作成していない、または`ADMIN_PASSWORD`が未設定 |
| ダッシュボードが「確認中...」「起動中...」のまま固まる | `NEXT_PUBLIC_API_URL`にAPIが到達できていない、またはログインできていない（ブラウザのネットワークタブで401か接続エラーかを確認） |
| ログインが「APIに接続できませんでした」で失敗する／`OPTIONS`リクエストが`400`を返す | `CORS_ORIGINS`がページの実際のアドレスと一致していません。上記の[CORS_ORIGINSの設定方法](#cors_originsの設定方法)を参照してください |
| 自動執筆ジョブがすぐに`error`になり接続エラーが表示される | Ollamaが起動していない、または`OLLAMA_URL`/`CONTROLLER_OLLAMA_URL`が誤っている（`http://host.docker.internal:11434`はWindows/macOSのDocker内からのみ解決可能。Linuxではホストのアドレスを別途指定するか、Ollamaを同じComposeネットワークで動かしてください） |
| `api`コンテナ起動時に`relation "projects" already exists`エラー | このプロジェクトがAlembic導入前に作られた古いPostgresボリュームが残っています。`docker compose down -v`でリセット（**全データ削除**）するか、データを残したい場合はそのDBに対して手動で`alembic stamp head`を実行してください |
| 検索が常に「全文一致 (PostgreSQL フォールバック)」になる | `QDRANT_URL`にQdrantが到達できていません。セマンティック検索は失敗時に単純な`ILIKE`一致検索へ自動的に切り替わります |
| 新しいコードをpullした後に`TypeError: ... got an unexpected keyword argument '...'` | `api`コンテナの`editor_common`が古いままビルドされています。上記の[アップグレード方法](#アップグレード方法)、`docker compose build --no-cache api`を参照してください |
