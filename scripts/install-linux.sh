#!/usr/bin/env bash
# Guided installer for Linux: checks for Docker and Ollama, offers to install
# whichever is missing (with an explicit confirmation before running anything
# that needs sudo), runs scripts/setup.sh to write .env, then optionally
# starts the stack. Safe to re-run.
#
#   ./scripts/install-linux.sh
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

ask_yn() {
  local prompt="$1" default="$2" reply
  local hint="y/N"; [ "$default" = "Y" ] && hint="Y/n"
  read -r -p "$prompt [$hint]: " reply || true
  reply="${reply:-$default}"
  case "$reply" in
    [Yy]*) echo "y" ;;
    *) echo "n" ;;
  esac
}

echo "=== Integrated Novel Editor (INE) — Linux セットアップ / Linux setup ==="
echo ""

# --- Docker ---------------------------------------------------------------
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "Docker（Compose v2プラグイン込み）は既にインストールされています。 / Docker (with the Compose v2 plugin) is already installed."
else
  echo "Dockerが見つからないか、Compose v2プラグインがありません。"
  echo "Docker was not found, or is missing the Compose v2 plugin."
  install_docker=$(ask_yn "公式インストールスクリプト（sudoが必要）でDockerをインストールしますか？ / Install Docker now using the official convenience script (requires sudo)?" "Y")
  if [ "$install_docker" = "y" ]; then
    curl -fsSL https://get.docker.com | sh
    if ! groups "$USER" | grep -q '\bdocker\b'; then
      sudo usermod -aG docker "$USER" || true
      echo "ユーザーをdockerグループに追加しました。反映にはログアウト・再ログイン（またはこのシェルの再起動）が必要です。"
      echo "Added your user to the docker group — log out and back in (or start a new shell) for this to take effect."
    fi
  else
    echo "Dockerのインストールをスキップしました。https://docs.docker.com/engine/install/ を参照して手動でインストールしてください。"
    echo "Skipped Docker installation. Install it manually from https://docs.docker.com/engine/install/ and re-run this script."
    exit 1
  fi
fi

# --- Ollama -----------------------------------------------------------------
if command -v ollama >/dev/null 2>&1; then
  echo "Ollamaは既にインストールされています。 / Ollama is already installed."
else
  echo ""
  echo "Ollamaが見つかりません。 / Ollama was not found."
  install_ollama=$(ask_yn "公式インストールスクリプトでOllamaをインストールしますか？ / Install Ollama now using the official install script?" "Y")
  if [ "$install_ollama" = "y" ]; then
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "Ollamaのインストールをスキップしました。https://ollama.com からご自身でインストールしてください。"
    echo "Skipped Ollama installation. Install it yourself from https://ollama.com."
  fi
fi

# --- .env setup --------------------------------------------------------------
echo ""
echo "続けて .env の設定を行います。 / Now configuring .env."
./scripts/setup.sh

# --- Start --------------------------------------------------------------------
echo ""
start_now=$(ask_yn "docker compose up --build で今すぐ起動しますか？ / Start now with docker compose up --build?" "Y")
if [ "$start_now" = "y" ]; then
  docker compose up --build -d
  echo "起動処理を開始しました。ログは docker compose logs -f で確認できます。"
  echo "Startup triggered — follow logs with docker compose logs -f."
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:3000" >/dev/null 2>&1 || true
  else
    echo "ブラウザで http://localhost:3000 を開いてください。 / Open http://localhost:3000 in your browser."
  fi
else
  echo "準備ができたら次のコマンドで起動できます / When ready, start with:"
  echo ""
  echo "    docker compose up --build"
fi
