Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scripts = @(
    "01_health_check.ps1",
    "02_stream_default_voice.ps1",
    "03_stream_custom_voice.ps1",
    "04_missing_user_id.ps1",
    "05_invalid_voice_strict.ps1"
)

foreach ($s in $scripts) {
    Write-Host ""
    Write-Host "==================== $s ===================="
    & "$PSScriptRoot\$s"
}

Write-Host ""
Write-Host "All smoke scripts passed." -ForegroundColor Green
