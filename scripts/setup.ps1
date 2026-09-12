# Interactive setup: asks whether to use the bundled PostgreSQL/Qdrant
# containers or your own external instances, and where Ollama runs, then
# writes .env accordingly. Run once before `docker compose up --build`.
#
#   .\scripts\setup.ps1
#
# Everything it asks can also be set by hand in .env (see .env.example for
# every variable) — this just walks through the ones that matter most for
# a first run, and keeps COMPOSE_PROFILES in sync with DATABASE_URL/
# QDRANT_URL so `docker compose up` does the right thing without extra
# flags. Re-run any time to change your answers; it starts from your
# existing .env (or .env.example, on a first run) and only overwrites the
# lines this script controls, leaving everything else untouched.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root

function Ask([string]$Prompt, [string]$Default) {
    $reply = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($reply)) { return $Default }
    return $reply
}

function Ask-YesNo([string]$Prompt, [string]$Default) {
    $hint = if ($Default -eq "Y") { "Y/n" } else { "y/N" }
    $reply = Read-Host "$Prompt [$hint]"
    if ([string]::IsNullOrWhiteSpace($reply)) { $reply = $Default }
    return $reply.Substring(0, 1).ToUpper() -eq "Y"
}

function Set-EnvVar([string]$Name, [string]$Value) {
    $line = "$Name=$Value"
    $content = Get-Content .env
    if ($content -match "^$Name=") {
        $content = $content -replace "^$Name=.*", $line
        Set-Content .env $content -Encoding utf8
    } else {
        Add-Content .env $line -Encoding utf8
    }
}

function Get-EnvVar([string]$Name) {
    $line = (Get-Content .env) | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1
    if ($null -eq $line) { return "" }
    return $line.Substring($Name.Length + 1)
}

try {
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
    }

    Write-Host "=== Integrated Novel Editor (INE) — セットアップ / setup ===" -ForegroundColor Cyan
    Write-Host ""

    # --- PostgreSQL ---
    $useBundledDb = Ask-YesNo "PostgreSQLを内蔵コンテナで使いますか？ / Use the bundled PostgreSQL container?" "Y"
    if ($useBundledDb) {
        $dbProfile = "db"
        Set-EnvVar "DATABASE_URL" "postgresql+psycopg2://novel:novel@db:5432/novel"
    } else {
        $dbProfile = ""
        $databaseUrl = Ask "外部PostgreSQLの接続文字列 / External PostgreSQL connection string" "postgresql+psycopg2://user:pass@host:5432/dbname"
        Set-EnvVar "DATABASE_URL" $databaseUrl
    }

    # --- Qdrant ---
    $useBundledQdrant = Ask-YesNo "Qdrantを内蔵コンテナで使いますか？ / Use the bundled Qdrant container?" "Y"
    if ($useBundledQdrant) {
        $qdrantProfile = "qdrant"
        Set-EnvVar "QDRANT_URL" "http://qdrant:6333"
    } else {
        $qdrantProfile = ""
        $qdrantUrl = Ask "外部QdrantのURL / External Qdrant URL" "http://192.168.1.10:6333"
        Set-EnvVar "QDRANT_URL" $qdrantUrl
    }

    $profiles = @($dbProfile, $qdrantProfile) | Where-Object { $_ -ne "" }
    Set-EnvVar "COMPOSE_PROFILES" ($profiles -join ",")

    # --- Ollama (always external — Docker Compose never starts it) ---
    Write-Host ""
    Write-Host "Ollamaは常にホスト側（または別マシン）で動かします。Compose自体はOllamaを起動しません。"
    Write-Host "Ollama always runs on the host (or another machine) — Compose never starts it."
    $ollamaUrl = Ask "Writer用OllamaのURL / Writer Ollama URL" "http://host.docker.internal:11434"
    Set-EnvVar "OLLAMA_URL" $ollamaUrl

    $sameOllama = Ask-YesNo "ControllerもWriterと同じOllamaサーバーを使いますか？ / Use the same Ollama server for Controller?" "Y"
    if ($sameOllama) {
        Set-EnvVar "CONTROLLER_OLLAMA_URL" $ollamaUrl
    } else {
        $controllerUrl = Ask "Controller用OllamaのURL / Controller Ollama URL" "http://host.docker.internal:11434"
        Set-EnvVar "CONTROLLER_OLLAMA_URL" $controllerUrl
    }

    # --- Access address (LAN/cloud) ---
    Write-Host ""
    Write-Host "このWebアプリにブラウザでアクセスするアドレスを入力してください（このマシン上のブラウザだけなら localhost のままで構いません）。"
    Write-Host "Enter the address you'll open the web app from in a browser (leave as localhost if that's always this same machine)."
    $accessHost = Ask "アクセス用ホスト名／IP / Access hostname or IP" "localhost"
    if ($accessHost -eq "localhost") {
        Set-EnvVar "CORS_ORIGINS" "http://localhost:3000"
        Set-EnvVar "NEXT_PUBLIC_API_URL" "http://localhost:8000/api/v1"
    } else {
        Set-EnvVar "CORS_ORIGINS" "http://${accessHost}:3000"
        Set-EnvVar "NEXT_PUBLIC_API_URL" "http://${accessHost}:8000/api/v1"
        Write-Host "→ CORS_ORIGINS / NEXT_PUBLIC_API_URL を http://${accessHost} 用に設定しました。"
        Write-Host "  (HTTPS・独自ドメインを使う場合は .env を直接編集してください)"
    }

    # --- Admin password ---
    Write-Host ""
    $currentPassword = Get-EnvVar "ADMIN_PASSWORD"
    if ([string]::IsNullOrWhiteSpace($currentPassword) -or $currentPassword -eq "novel") {
        $chars = (48..57) + (65..90) + (97..122)
        $generated = -join ((1..20) | ForEach-Object { [char]($chars | Get-Random) })
        $adminPassword = Ask "管理者パスワード（空欄でランダム生成） / Admin password (blank = random)" $generated
        Set-EnvVar "ADMIN_PASSWORD" $adminPassword
    }

    Write-Host ""
    Write-Host "=== 完了 / Done ===" -ForegroundColor Green
    Write-Host ".env を書き込みました / .env written. 次のコマンドで起動できます / start with:"
    Write-Host ""
    Write-Host "    docker compose up --build"
    Write-Host ""
    if ($profiles.Count -eq 0) {
        Write-Host "（PostgreSQL・Qdrantとも外部接続のため、追加コンテナは起動しません）"
        Write-Host "(Both PostgreSQL and Qdrant are external, so no extra containers will start)"
    }
} finally {
    Pop-Location
}
