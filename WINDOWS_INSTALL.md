# Windows インストーラ（INE-Setup.exe）— インストール・設定ガイド

Integrated Novel Editor (INE) をターミナルなしで使うための、Windows用デスクトップインストーラの説明です。開発者向けの`git clone`＋`docker compose`によるセットアップは[インストールマニュアル](docs/installation.ja.md)を参照してください。このインストーラはその薄いラッパーで、中身は同じDocker Composeスタックです。

## 前提条件

- **Windows 10/11（64bit）**
- **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** — 別途インストールが必要です。インストーラ自体はDockerをインストールしません
- **[Ollama](https://ollama.com)** — ホスト（Windows）側で動かします。インストーラはOllamaもインストールしません。先にインストールし、使うモデルを`ollama pull`しておいてください（詳しくは[インストールマニュアルの手順1](docs/installation.ja.md#1-ollamaのインストールとモデルの取得)）

## インストール手順

1. [Releasesページ](https://github.com/itanaka66/integrated_novel_editor/releases)から`INE-Setup-<version>.exe`をダウンロードします。
2. 実行します。**未署名の実行ファイルのため、Windows SmartScreenが警告を表示します。**「詳細情報」→「実行」で進めてください。
3. インストーラは管理者権限を要求しません（`{autopf}\INE` = 通常`C:\Program Files\INE`、または任意の場所にインストール可能）。「デスクトップにショートカットを作成する」を選ぶと、後述の起動ショートカットがデスクトップにも作られます。
4. インストール先には次のファイルが配置されます。
   - `docker-compose.yml`（配布用の`docker-compose.release.yml`がこの名前でコピーされたもの — GHCRの公開済みイメージをpullする方式で、Windows上でのビルドは行いません）
   - `.env.example`
   - `launch.ps1` / `stop.ps1`
   - `README.md`
5. スタートメニューに「INEを起動」「INEを停止」の2つのショートカットが作成されます（「デスクトップにショートカットを作成する」を選んだ場合はデスクトップにも「INE」が作成されます）。

## 初回起動

「INEを起動」を実行すると、`launch.ps1`が次の順で処理します。

1. **Docker Desktopの確認**。インストールされていなければメッセージを表示して終了します。インストール済みだが起動していなければ自動的に起動を試み、最大3分待ちます。
2. **初回のみ、`.env`を`.env.example`から生成**し、20文字のランダムな管理者パスワードを`ADMIN_PASSWORD`に設定します。このパスワードは**ダイアログに一度だけ表示される**ので、必ず控えてください（`ADMIN_USERNAME`の既定値は`admin`）。忘れた場合はインストール先の`.env`ファイルを直接開けば確認できます。
3. `docker compose up -d`でコンテナ（`db`・`qdrant`・`api`・`web`）を起動します。初回はGHCRからのイメージダウンロードで数分かかることがあります。
4. `http://localhost:3000`が応答するまで最大3分待ってから、既定のブラウザで自動的に開きます。応答がまだの場合はその旨のメッセージが出るので、数分待ってからブラウザを再読み込みしてください。

ログイン画面が開いたら、ユーザー名`admin`と上記で控えたパスワードでログインしてください。

## 設定方法（`.env`の編集）

インストール先の`.env`ファイルをテキストエディタで直接編集します。主な設定項目は次の通りです（詳細は同梱の`.env.example`のコメント、または[動作要件](docs/requirements.ja.md)を参照）。

| 変数 | 用途 |
|---|---|
| `ADMIN_PASSWORD` | 管理者パスワード（初回起動時に自動生成されたもの。変更可） |
| `OLLAMA_URL` / `OLLAMA_MODEL` | Writer用Ollama（既定は同じPC上の`host.docker.internal:11434`） |
| `CONTROLLER_OLLAMA_URL` / `CONTROLLER_OLLAMA_MODEL` | Controller用Ollama。Writerと別サーバー／GPUに分ける場合はここを変更 |
| `OLLAMA_API_KEY` / `CONTROLLER_OLLAMA_API_KEY` | Ollamaが認証を要求する場合のAPIキー（`Authorization: Bearer`） |
| `CORS_ORIGINS` | `http://localhost:3000`以外（LAN内の別PCなど）からアクセスする場合に必須 |
| `NEXT_PUBLIC_API_URL` | ブラウザから見たAPIアドレス。`localhost`以外からアクセスする場合は変更が必要（変更後は後述のイメージ再pullが必要） |
| `SMTP_HOST`等 | パスワード再発行メールを実際に送信したい場合（未設定でも動作はします） |
| `GOOGLE_CLIENT_ID`等 | Google/GitHubログインを使う場合 |

`.env`を編集したら、「INEを起動」をもう一度実行してください。`docker compose up -d`は変更を検知して該当コンテナを再作成します。

**`NEXT_PUBLIC_API_URL`を変更した場合は、`web`コンテナを作り直しても反映されません**（ビルド時に焼き込まれる値のため）。この設定は配布用イメージには対応していません（イメージの再ビルドが必要）。LAN内の別PCなどからアクセスしたい場合は、`git clone`しての[通常のDocker Composeセットアップ](docs/installation.ja.md#2-方式a--docker-compose)を利用してください。

## 停止方法

「INEを停止」ショートカットを実行します。コンテナが停止するだけで、Postgres/Qdrant/エピソードデータなどのボリュームは削除されません。次回「INEを起動」で同じ状態から再開します。

## アップデート方法

**注意：「INEを起動」を実行するだけでは、既にローカルにあるイメージと同じタグ（`latest`）は再ダウンロードされません。** 新しいバージョンに更新するには、インストール先フォルダでコマンドプロンプト／PowerShellを開き、次を実行してからもう一度「INEを起動」してください。

```powershell
docker compose pull
```

新しい`INE-Setup-<version>.exe`が公開されている場合は、それを実行して上書きインストールしても構いません（`.env`はアンインストール時に保持される設定になっていますが、上書きインストールでは既存の`.env`はそのまま残ります）。

## アンインストール

コントロールパネルの「プログラムのアンインストール」、またはスタートメニューの「INE」グループから通常通りアンインストールできます。

- `.env`（生成された管理者パスワードや接続設定の上書き）は、再インストール時にそのまま使えるよう**削除されません**。
- Postgres・Qdrant・エピソードデータなどはDockerのボリュームとして管理されており、このインストーラのアンインストールでは**削除されません**。完全にデータごと消したい場合は、アンインストール前にインストール先フォルダで`docker compose down -v`を実行してください。

## トラブルシューティング

- **SmartScreenで「Windows によって PC が保護されました」と表示される**：未署名の実行ファイルのため。「詳細情報」→「実行」で進めます。
- **「INEを起動」がDocker Desktopを見つけられない**：Docker Desktopをインストールし、一度手動で起動してから再度お試しください。
- **起動してもブラウザが応答しない**：初回はイメージのダウンロードに時間がかかります。数分待ってブラウザを再読み込みしてください。改善しない場合はインストール先フォルダで`docker compose logs`を確認してください。
- **その他の症状**（ログインできない、CORSエラー、自動執筆でOllamaに繋がらない等）：[インストールマニュアルのトラブルシューティング](docs/installation.ja.md#トラブルシューティング)を参照してください。内容はこのインストーラでも共通です。

## 参考

- [インストールマニュアル（詳細版）](docs/installation.ja.md)
- [動作要件](docs/requirements.ja.md)
- [操作マニュアル](docs/user-guide.ja.md)
- インストーラのビルド方法：[installer/windows/build.ps1](installer/windows/build.ps1)（Inno Setup 6が必要）
