Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

$voiceBase = Get-EnvValue -Name "ECHOES_VOICE_BASE" -Default "http://localhost:18083"
$userId = Get-EnvValue -Name "TEST_USER_ID" -Required
$invalidVoice = "qa-missing-" + ([Guid]::NewGuid().ToString("N"))

$url = "$voiceBase/internal/voice/inference/synthesize-stream?voiceName=$([uri]::EscapeDataString($invalidVoice))"
$body = "data: hello invalid voice`n`n"

Write-Step "Call voice stream with invalid voiceName=$invalidVoice"

$tmpBody = [System.IO.Path]::GetTempFileName()
try {
    [System.IO.File]::WriteAllText($tmpBody, $body, [System.Text.Encoding]::UTF8)
    $raw = & curl.exe -sS -N -i --max-time 45 `
        -X POST $url `
        -H "X-INTERNAL: 1" `
        -H "X-USER-ID: $userId" `
        -H "X-TRACE-ID: $([Guid]::NewGuid().ToString())" `
        -H "X-SESSION-ID: $([Guid]::NewGuid().ToString())" `
        -H "X-TURN-ID: $([Guid]::NewGuid().ToString())" `
        -H "Content-Type: text/event-stream" `
        --data-binary "@$tmpBody" 2>&1

    $text = [string]($raw -join [Environment]::NewLine)
    $status = -1
    if ($text -match "HTTP/\d\.\d\s+(\d{3})") {
        $status = [int]$Matches[1]
    }

    Assert-True -Condition ($status -ge 200 -and $status -lt 600) -Message "Unexpected HTTP status: $status raw=$text"
    $looksLikeExpectedError = ($text -like '*voice_not_available*') -or ($text -like '*VOICE_NOT_AVAILABLE*') -or ($text -like '*"type":"error"*')
    Assert-True -Condition $looksLikeExpectedError -Message "Expected strict voice error not found. status=$status body=$text"

    Write-Host "status=$status"
    Write-Host "response_preview:"
    Write-Host ($text.Substring(0, [Math]::Min(600, $text.Length)))
    Write-Pass "Invalid voice strict smoke passed."
} finally {
    if (Test-Path $tmpBody) {
        Remove-Item -Force $tmpBody -ErrorAction SilentlyContinue
    }
}
