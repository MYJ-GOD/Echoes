Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

$convBase = Get-EnvValue -Name "ECHOES_CONV_BASE" -Default "http://localhost:18082"
$userId = Get-EnvValue -Name "TEST_USER_ID" -Required

Write-Step "Create session with default voice"
$sessionId = New-ConversationSession -ConversationBase $convBase -UserId $userId
Write-Host "sessionId=$sessionId"

Write-Step "Call /conversation/chat-stream with default voice"
$content = Invoke-ChatStreamRequest -ConversationBase $convBase -SessionId $sessionId -UserId $userId -Message "Hello, default voice smoke test."

Assert-Contains -Text $content -Needle '"type":"message.delta"' -Message "Expected message.delta not found in SSE response"
Assert-Contains -Text $content -Needle '"type":"audio_chunk"' -Message "Expected audio_chunk not found in SSE response"
Assert-Contains -Text $content -Needle '"type":"end"' -Message "Expected end event not found in SSE response"

Write-Host "response_preview:"
Write-Host ($content.Substring(0, [Math]::Min(600, $content.Length)))
Write-Pass "Default voice stream smoke passed."
