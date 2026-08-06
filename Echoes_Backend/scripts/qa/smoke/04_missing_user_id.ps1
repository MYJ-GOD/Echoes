Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

$voiceBase = Get-EnvValue -Name "ECHOES_VOICE_BASE" -Default "http://localhost:18083"
$url = "$voiceBase/internal/voice/inference/synthesize-stream?voiceName=default"
$headers = @{
    "X-INTERNAL" = "1"
    "X-TRACE-ID" = [Guid]::NewGuid().ToString()
    "X-SESSION-ID" = [Guid]::NewGuid().ToString()
    "X-TURN-ID" = [Guid]::NewGuid().ToString()
}
$body = "data: hello`n`n"

Write-Step "Call voice stream without X-USER-ID"
try {
    $resp = Invoke-WebRequest -Method Post -Uri $url -Headers $headers -ContentType "text/plain; charset=utf-8" -Body $body -TimeoutSec 30
    throw "Expected request to fail with 400, but succeeded. status=$($resp.StatusCode) body=$($resp.Content)"
} catch {
    $status = Get-StatusCodeFromWebException -Exception $_.Exception
    $errBody = Get-ResponseBodyFromWebException -Exception $_.Exception
    Assert-True -Condition ($status -eq 400) -Message "Expected HTTP 400, got $status. body=$errBody"
    if (-not [string]::IsNullOrWhiteSpace($errBody)) {
        Assert-Contains -Text $errBody -Needle "MISSING_USER_ID" -Message "Expected MISSING_USER_ID in response body"
    }
}

Write-Pass "Missing X-USER-ID smoke passed."
