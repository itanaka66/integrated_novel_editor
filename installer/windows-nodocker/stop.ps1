# Stops INE's three processes (qdrant.exe, ine-api.exe, node.exe). No data
# is deleted — .\data\ (SQLite database, Qdrant storage, episode text
# mirror) is left untouched for next launch.

$ErrorActionPreference = "Continue"
Add-Type -AssemblyName System.Windows.Forms
Set-Location $PSScriptRoot

if (Test-Path ".pids") {
    Get-Content ".pids" | ForEach-Object {
        try { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } catch {}
    }
    Remove-Item ".pids" -Force -ErrorAction SilentlyContinue
} else {
    # Fallback if .pids is missing for some reason — stop by name instead.
    Get-Process qdrant, ine-api -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

[System.Windows.Forms.MessageBox]::Show("INE を停止しました。データは保持されています。`n`nINE has been stopped. Your data is preserved.", "Integrated Novel Editor (INE)") | Out-Null
