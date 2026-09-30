# Starts (or restarts) INE without Docker — plain Windows processes:
# qdrant.exe, ine-api.exe (bundles its own Python + runs migrations
# against a local SQLite file on startup), and node.exe running the
# Next.js standalone server — then opens it in the default browser.
#
# Run from the installed app folder (the Start Menu / desktop shortcut
# the installer creates does this for you).

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms

$root = $PSScriptRoot
Set-Location $root

function Show-Message([string]$text, [string]$title = "Integrated Novel Editor (INE)") {
    [System.Windows.Forms.MessageBox]::Show($text, $title) | Out-Null
}

# --- First run: generate .env with a random admin password -----------------
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    $chars = (48..57) + (65..90) + (97..122)
    $password = -join ((1..20) | ForEach-Object { [char]($chars | Get-Random) })
    (Get-Content ".env") -replace '^ADMIN_PASSWORD=.*$', "ADMIN_PASSWORD=$password" | Set-Content ".env"
    Show-Message "初回起動です。管理者パスワードを生成しました:`n`n$password`n`nこのパスワードは $root\.env に保存されています。後で変更できます。`n`nFirst run: generated an admin password:`n`n$password`n`nSaved to $root\.env — you can change it later."
}

New-Item -ItemType Directory -Force -Path ".\data\qdrant" | Out-Null
New-Item -ItemType Directory -Force -Path ".\data\novel_storage" | Out-Null
New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null

# --- Stop anything left over from a previous, uncleanly-ended session ------
if (Test-Path ".pids") {
    Get-Content ".pids" | ForEach-Object {
        try { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } catch {}
    }
    Remove-Item ".pids" -Force -ErrorAction SilentlyContinue
}

# Named $processIds, not $pids — PowerShell variable names are
# case-insensitive, so $pids silently aliases the built-in $PID (this
# script's own process ID), and every += below would have been fighting
# a read-only automatic variable instead of building a real list.
$processIds = @()

Write-Host "Qdrant を起動しています... / Starting Qdrant..."
$env:QDRANT__STORAGE__STORAGE_PATH = "$root\data\qdrant"
$env:QDRANT__SERVICE__HTTP_PORT = "6333"
$qdrant = Start-Process -FilePath ".\qdrant.exe" -WorkingDirectory $root `
    -RedirectStandardOutput ".\logs\qdrant.log" -RedirectStandardError ".\logs\qdrant.err.log" `
    -WindowStyle Hidden -PassThru
$processIds += $qdrant.Id

Write-Host "API を起動しています... / Starting the API..."
$api = Start-Process -FilePath ".\ine-api.exe" -WorkingDirectory $root `
    -RedirectStandardOutput ".\logs\api.log" -RedirectStandardError ".\logs\api.err.log" `
    -WindowStyle Hidden -PassThru
$processIds += $api.Id

Write-Host "API の起動を待っています... / Waiting for the API..."
$deadline = (Get-Date).AddMinutes(2)
$apiUp = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $apiUp = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}
if (-not $apiUp) {
    Show-Message "API の起動を確認できませんでした。$root\logs\api.err.log を確認してください。`n`nCould not confirm the API started. Check $root\logs\api.err.log for details."
}

Write-Host "Web を起動しています... / Starting the web app..."
$env:PORT = "3000"
$env:HOSTNAME = "127.0.0.1"
$web = Start-Process -FilePath ".\node.exe" -ArgumentList "web\server.js" -WorkingDirectory $root `
    -RedirectStandardOutput ".\logs\web.log" -RedirectStandardError ".\logs\web.err.log" `
    -WindowStyle Hidden -PassThru
$processIds += $web.Id

$processIds | Set-Content ".pids"

Write-Host "Web の起動を待っています... / Waiting for the web app..."
$deadline = (Get-Date).AddMinutes(2)
$webUp = $false
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $webUp = $true; break }
    } catch { Start-Sleep -Seconds 2 }
}

Start-Process "http://127.0.0.1:3000"
if (-not $webUp) {
    Show-Message "起動処理は開始しましたが、まだ応答がありません。数分後にブラウザを再読み込みしてください。`n`nStartup was triggered but the app isn't responding yet. Reload the browser tab in a few minutes."
}
