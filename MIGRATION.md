# データベースマイグレーション（Alembic）

このアプリのスキーマは[Alembic](https://alembic.sqlalchemy.org/)で管理しています。マイグレーションファイルは`apps/api/alembic/versions/`にあり、コマンドは全て`apps/api`ディレクトリで実行してください。

```bash
cd apps/api
```

## 自動適用される場面

- **Docker Compose**：`api`コンテナは起動時に必ず`alembic upgrade head`を実行してから`uvicorn`を起動します（`apps/api/Dockerfile`の`CMD`参照）。新しいイメージに切り替えて`docker compose up -d --build`すれば、未適用のマイグレーションは自動的に反映されます。
- **CI**：`pytest`実行後に、SQLiteに対して`upgrade head`→`downgrade base`の往復を検証します（`.github/workflows/ci.yml`）。理由は下記「SQLite互換性」を参照してください。

上記以外（ネイティブ実行、手元での確認作業など）では、以下のコマンドを手動で実行してください。

## よく使うコマンド

| 用途 | コマンド |
|---|---|
| 現在のDBのリビジョンを確認 | `alembic current` |
| 未適用のマイグレーションを全て適用 | `alembic upgrade head` |
| 1つ前のリビジョンに戻す | `alembic downgrade -1` |
| 特定のリビジョンまで戻す | `alembic downgrade <revision>` |
| 特定のリビジョンまで進める | `alembic upgrade <revision>` |
| 全マイグレーションの履歴を表示 | `alembic history` |
| 現在のheadリビジョンを表示 | `alembic heads` |
| 実際にDBへ適用せず、生成されるSQLだけ確認 | `alembic upgrade head --sql` |

Docker Composeで動いている`api`コンテナに対して直接実行する場合：

```bash
docker compose exec api alembic upgrade head
```

## 新規マイグレーションの作成

1. `apps/api/app/models.py`でモデルを変更する。
2. 雛形を生成する：
   ```bash
   alembic revision --autogenerate -m "add xxx column to yyy"
   ```
   `env.py`が`target_metadata = Base.metadata`を設定しているため、autogenerateはモデルとDBの差分から`op.*`呼び出しを生成しようとしますが、**必ず生成結果を目視で確認・修正してください**——特にこのリポジトリのモデル定義は1行に詰め込む独特のスタイルのため、意図しないインデックス名の変更やカラムの誤検出が起きることがあります。差分が期待通りでない場合は、雛形の`upgrade()`/`downgrade()`を手動で書き直すか、空の`alembic revision -m "..."`から手動で組み立ててください（既存の`versions/`配下のファイルの大半はこの手動スタイルです）。
3. `revision`変数はランダムな12桁16進数のままで構いません（他のマイグレーションと衝突さえしなければ問題ありません）。`down_revision`が現在のhead（`alembic heads`で確認）を指していることを確認してください。
4. **`downgrade()`も必ず実装する**——「戻せないマイグレーション」は原則作らないでください。データを完全には復元できない操作（`drop_column`で失われたデータなど）でも、スキーマ的に一つ前の状態に戻せることが重要です（CIの往復チェックがこれを機械的に検証します）。
5. 手元で往復を確認してから提出する：
   ```bash
   alembic upgrade head
   alembic downgrade -1   # 直前の状態に戻せるか
   alembic upgrade head   # 再度進められるか
   ```

## SQLite互換性（重要）

本番・開発ともにDBは常にPostgreSQLですが、**CIのマイグレーション往復チェックはSQLiteに対して実行されます**（`.github/workflows/ci.yml`の`DATABASE_URL=sqlite:///...`）。PostgreSQLでは問題なく動くDDLが、SQLiteでは構文エラーになることがあるため注意してください。

代表的な非互換操作と対処：

| 操作 | SQLiteでの扱い | 対処 |
|---|---|---|
| `op.add_column(...)` | ネイティブ対応 | そのままでOK |
| `op.create_table(...)` / `op.drop_table(...)` | ネイティブ対応 | そのままでOK |
| `op.create_index(...)` / `op.drop_index(...)` | ネイティブ対応 | そのままでOK |
| `op.alter_column(...)`（型変更、NULL許容の変更など） | **非対応**（`ALTER TABLE ... ALTER COLUMN`という構文自体が無い） | `op.batch_alter_table(...)`で囲む |
| カラム名の変更・制約の追加/削除 | 同上 | 同上 |

`op.batch_alter_table`を使うと、SQLite上ではAlembicが自動的に「新しいテーブルを作成→データをコピー→古いテーブルを削除→リネーム」という手順に展開してくれます。PostgreSQL上では（ネイティブに`ALTER COLUMN`できるため）通常通りの1行の`ALTER TABLE`のままです（`alembic upgrade head --sql`で確認できます）。書き方：

```python
def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('password_hash', existing_type=sa.String(length=255), nullable=True)
```

**迷ったら、単純な`alter_column`を書く前に一度`op.batch_alter_table`で囲んでおくのが安全です**——手元で以下を実行して両方のバックエンドで問題ないか確認してください：

```bash
# SQLiteでの往復確認（CIと同じ条件）
rm -f _ci_migration_check.db
DATABASE_URL=sqlite:///./_ci_migration_check.db alembic upgrade head
DATABASE_URL=sqlite:///./_ci_migration_check.db alembic downgrade base
rm -f _ci_migration_check.db

# PostgreSQL向けに生成されるSQLの目視確認
alembic upgrade head --sql
```

## ロールバックに関する注意

- `alembic downgrade`はスキーマを元に戻しますが、`drop_column`や`drop_table`で失われたデータは**復元されません**。本番DBに対してロールバックする前に、必ずバックアップ（`scripts/backup.sh`）を取ってください。
- 一度ユーザーが操作した本番環境で`downgrade`する機会はほぼ無いはずです（前方にしか進まない運用が基本）。開発中の手戻り・CI上の往復チェック用途がほとんどです。
