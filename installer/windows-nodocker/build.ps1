# Build the Docker-free Windows .exe installer.
#
#   installer\windows-nodocker\build.ps1
#
# Output: dist\INE-NoDocker-Setup-<version>.exe
#
# Unlike installer\windows (which just bundles docker-compose.release.yml
# and pulls prebuilt images at first launch), this one actually builds
# everything that ships: freezes apps/api into a single ine-api.exe with
# PyInstaller (SQLite instead of PostgreSQL — see apps/api/desktop_main.py),
# builds apps/web's Next.js standalone output, and downloads portable
# qdrant.exe / node.exe binaries to bundle so the end machine needs
# nothing but this installer and Ollama.
#
# Requires:
#   - Windows, PowerShell
#   - Python 3.12+ with apps/api/requirements.txt (+ pyinstaller) installed
#     in a venv at apps\api\.venv (same one docs/installation.md's native
#     setup uses)
#   - Node.js (for `npm install` / `next build` — only needed at build
#     time; the portable node.exe below is what the *installed app* runs)
#   - Inno Setup 6 (iscc.exe on PATH)
#   - Internet access (downloads qdrant.exe / node.exe from their
#     official GitHub/nodejs.org releases on first build; cached under
#     installer\windows-nodocker\.cache\ after that)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")
$payload = Join-Path $scriptDir "payload"
$cache = Join-Path $scriptDir ".cache"

$nodeVersion = "v24.21.0"
$qdrantVersion = "v1.19.1"

New-Item -ItemType Directory -Force -Path $cache | Out-Null
if (Test-Path $payload) { Remove-Item -Recurse -Force $payload }
New-Item -ItemType Directory -Force -Path $payload | Out-Null

# --- 1. Backend: PyInstaller onefile -----------------------------------
Write-Host "==> Backend (PyInstaller) をビルドしています / Building the backend" -ForegroundColor Cyan
Push-Location (Join-Path $repoRoot "apps\api")
try {
    # PyInstaller is build-time only — deliberately not in
    # requirements-dev.txt, which CI installs on every test run and
    # shouldn't pay for a package unrelated to testing. Installed here
    # instead, straight into this venv, only when actually building.
    & ".venv\Scripts\python.exe" -m pip install --quiet pyinstaller
    if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

    # PyInstaller (like many native tools) writes its normal INFO log to
    # stderr — with $ErrorActionPreference = "Stop" that trips PowerShell
    # 5.1's NativeCommandError on the first such line even though the
    # build itself is fine. Relax it for this one call and go by
    # $LASTEXITCODE instead, as the top-of-file comment on Bash's own
    # tool description warns about.
    $ErrorActionPreference = "Continue"
    & ".venv\Scripts\python.exe" -m PyInstaller --noconfirm --onefile --name ine-api `
        --add-data "alembic.ini;." `
        --add-data "alembic;alembic" `
        --collect-submodules app `
        --hidden-import qdrant_client `
        --hidden-import psycopg2 `
        --hidden-import editor_common `
        desktop_main.py 2>&1 | Out-String | Write-Host
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
    Copy-Item "dist\ine-api.exe" (Join-Path $payload "ine-api.exe")
} finally {
    Pop-Location
}

# --- 2. Frontend: Next.js standalone build ------------------------------
Write-Host "==> Frontend (next build) をビルドしています / Building the frontend" -ForegroundColor Cyan
Push-Location (Join-Path $repoRoot "apps\web")
try {
    $env:NEXT_PUBLIC_API_URL = "http://localhost:8000/api/v1"
    $ErrorActionPreference = "Continue"
    npx next build 2>&1 | Out-String | Write-Host
    $ErrorActionPreference = "Stop"
    if ($LASTEXITCODE -ne 0) { throw "next build failed" }
    $webDest = Join-Path $payload "web"
    Copy-Item ".next\standalone" $webDest -Recurse
    Copy-Item ".next\static" (Join-Path $webDest ".next\static") -Recurse
    if (Test-Path "public") { Copy-Item "public" (Join-Path $webDest "public") -Recurse }
} finally {
    Pop-Location
    Remove-Item Env:\NEXT_PUBLIC_API_URL -ErrorAction SilentlyContinue
}

# --- 3. Portable node.exe (downloaded once, cached) ---------------------
$nodeZip = Join-Path $cache "node-$nodeVersion-win-x64.zip"
if (-not (Test-Path $nodeZip)) {
    Write-Host "==> node.exe をダウンロードしています / Downloading node.exe" -ForegroundColor Cyan
    Invoke-WebRequest -Uri "https://nodejs.org/dist/$nodeVersion/node-$nodeVersion-win-x64.zip" -OutFile $nodeZip
}
$nodeExtract = Join-Path $cache "node-$nodeVersion-win-x64"
if (-not (Test-Path $nodeExtract)) {
    Expand-Archive -Path $nodeZip -DestinationPath $cache -Force
}
Copy-Item (Join-Path $nodeExtract "node.exe") (Join-Path $payload "node.exe")

# --- 4. Portable qdrant.exe (downloaded once, cached) --------------------
$qdrantZip = Join-Path $cache "qdrant-$qdrantVersion-win-x64.zip"
if (-not (Test-Path $qdrantZip)) {
    Write-Host "==> qdrant.exe をダウンロードしています / Downloading qdrant.exe" -ForegroundColor Cyan
    Invoke-WebRequest -Uri "https://github.com/qdrant/qdrant/releases/download/$qdrantVersion/qdrant-x86_64-pc-windows-msvc.zip" -OutFile $qdrantZip
}
$qdrantExtract = Join-Path $cache "qdrant-$qdrantVersion-win-x64"
if (-not (Test-Path $qdrantExtract)) {
    New-Item -ItemType Directory -Force -Path $qdrantExtract | Out-Null
    Expand-Archive -Path $qdrantZip -DestinationPath $qdrantExtract -Force
}
Copy-Item (Join-Path $qdrantExtract "qdrant.exe") (Join-Path $payload "qdrant.exe")

# --- 5. Scripts + env template -------------------------------------------
Copy-Item (Join-Path $scriptDir "launch.ps1") $payload
Copy-Item (Join-Path $scriptDir "stop.ps1") $payload
Copy-Item (Join-Path $scriptDir "api.env.example") (Join-Path $payload ".env.example")
Copy-Item (Join-Path $repoRoot "README.md") $payload

# --- 6. Inno Setup ---------------------------------------------------------
Write-Host "==> インストーラを作成しています / Building the installer" -ForegroundColor Cyan
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    throw "iscc.exe が見つかりません。Inno Setup 6 を導入してください / install Inno Setup 6 (https://jrsoftware.org/isinfo.php)"
}
Push-Location $scriptDir
try {
    & $iscc.Source "ine-nodocker.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "完了 / Done: dist\" -ForegroundColor Green
Get-ChildItem (Join-Path $repoRoot "dist\*.exe") | ForEach-Object { Write-Host "  $($_.Name)" }
