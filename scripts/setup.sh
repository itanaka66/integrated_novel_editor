#!/usr/bin/env bash
# Interactive setup: asks whether to use the bundled PostgreSQL/Qdrant
# containers or your own external instances, and where Ollama runs, then
# writes .env accordingly. Run once before `docker compose up --build`.
#
#   ./scripts/setup.sh
#
# Everything it asks can also be set by hand in .env (see .env.example for
# every variable) — this just walks through the ones that matter most for
# a first run, and keeps COMPOSE_PROFILES in sync with DATABASE_URL/
# QDRANT_URL so `docker compose up` does the right thing without extra
# flags. Re-run any time to change your answers; it starts from your
# existing .env (or .env.example, on a first run) and only overwrites the
# lines this script controls, leaving everything else untouched.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -f .env ]; then
  cp .env.example .env
fi

ask() {
  # ask PROMPT DEFAULT -> echoes the answer (default if the user hits Enter)
  local prompt="$1" default="$2" reply
  read -r -p "$prompt [$default]: " reply || true
  echo "${reply:-$default}"
}

ask_yn() {
  # ask_yn PROMPT DEFAULT(Y|N) -> echoes "y" or "n"
  local prompt="$1" default="$2" reply
  local hint="y/N"; [ "$default" = "Y" ] && hint="Y/n"
  read -r -p "$prompt [$hint]: " reply || true
  reply="${reply:-$default}"
  case "$reply" in
    [Yy]*) echo "y" ;;
    *) echo "n" ;;
  esac
}

set_var() {
  # set_var NAME VALUE -> replaces "NAME=..." in .env, or appends it
  local name="$1" value="$2"
  # Escape characters that are special to sed's replacement text.
  local escaped
  escaped=$(printf '%s' "$value" | sed -e 's/[\/&]/\\&/g')
  if grep -q "^${name}=" .env; then
    sed -i.bak "s/^${name}=.*/${name}=${escaped}/" .env && rm -f .env.bak
  else
    printf '%s=%s\n' "$name" "$value" >> .env
  fi
}

echo "=== Integrated Novel Editor (INE) — セットアップ / setup ==="
echo ""

# --- PostgreSQL -------------------------------------------------------
use_bundled_db=$(ask_yn "PostgreSQLを内蔵コンテナで使いますか？ / Use the bundled PostgreSQL container?" "Y")
if [ "$use_bundled_db" = "y" ]; then
  db_profile="db"
  set_var DATABASE_URL "postgresql+psycopg2://novel:novel@db:5432/novel"
else
  db_profile=""
  database_url=$(ask "外部PostgreSQLの接続文字列 / External PostgreSQL connection string" "postgresql+psycopg2://user:pass@host:5432/dbname")
  set_var DATABASE_URL "$database_url"
fi

# --- Qdrant -------------------------------------------------------------
use_bundled_qdrant=$(ask_yn "Qdrantを内蔵コンテナで使いますか？ / Use the bundled Qdrant container?" "Y")
if [ "$use_bundled_qdrant" = "y" ]; then
  qdrant_profile="qdrant"
  set_var QDRANT_URL "http://qdrant:6333"
else
  qdrant_profile=""
  qdrant_url=$(ask "外部QdrantのURL / External Qdrant URL" "http://192.168.1.10:6333")
  set_var QDRANT_URL "$qdrant_url"
fi

profiles="$db_profile"
if [ -n "$qdrant_profile" ]; then
  profiles="${profiles:+$profiles,}$qdrant_profile"
fi
set_var COMPOSE_PROFILES "$profiles"

# --- Ollama (always external — Docker Compose never starts it) ---------
echo ""
echo "Ollamaは常にホスト側（または別マシン）で動かします。Compose自体はOllamaを起動しません。"
echo "Ollama always runs on the host (or another machine) — Compose never starts it."
ollama_url=$(ask "Writer用OllamaのURL / Writer Ollama URL" "http://host.docker.internal:11434")
set_var OLLAMA_URL "$ollama_url"

same_ollama=$(ask_yn "ControllerもWriterと同じOllamaサーバーを使いますか？ / Use the same Ollama server for Controller?" "Y")
if [ "$same_ollama" = "y" ]; then
  set_var CONTROLLER_OLLAMA_URL "$ollama_url"
else
  controller_url=$(ask "Controller用OllamaのURL / Controller Ollama URL" "http://host.docker.internal:11434")
  set_var CONTROLLER_OLLAMA_URL "$controller_url"
fi

# --- Admin password ------------------------------------------------------
echo ""
current_password=$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2- || true)
if [ -z "$current_password" ] || [ "$current_password" = "novel" ]; then
  # `head -c 20` closing its stdin partway through `tr`'s output makes `tr`
  # exit on SIGPIPE — with `pipefail` that reads as this whole line
  # failing (exit 141) even though $generated came out fine, so swallow it.
  generated=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 20) || true
  admin_password=$(ask "管理者パスワード（空欄でランダム生成） / Admin password (blank = random)" "$generated")
  set_var ADMIN_PASSWORD "$admin_password"
fi

echo ""
echo "=== 完了 / Done ==="
echo ".env を書き込みました / .env written. 次のコマンドで起動できます / start with:"
echo ""
echo "    docker compose up --build"
echo ""
if [ -z "$profiles" ]; then
  echo "（PostgreSQL・Qdrantとも外部接続のため、追加コンテナは起動しません）"
  echo "(Both PostgreSQL and Qdrant are external, so no extra containers will start)"
fi
