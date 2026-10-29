# anna-app apps publish wrapper: restores dev tool ID after publish overwrites it
Set-Location $PSScriptRoot
anna-app apps publish @args
Write-Host "`n[publish.ps1] Restoring dev tool ID..."
git -C "$PSScriptRoot\.." checkout -- anna/bundle/anna-tool-ids.js
Write-Host "[publish.ps1] Done. anna-tool-ids.js restored to dev ID."
