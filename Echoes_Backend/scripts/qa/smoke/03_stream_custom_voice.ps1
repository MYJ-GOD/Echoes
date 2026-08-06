Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

$convBase = Get-EnvValue -Name "ECHOES_CONV_BASE" -Default "http://localhost:18082"
$userId = Get-EnvValue -Name "TEST_USER_ID" -Required
$voiceAssetId = Get-EnvValue -Name "TEST_VOICE_ASSET_ID" -Required

Write-Step "Create session with custom voiceAssetId"
$sessionId = New-ConversationSession -ConversationBase $convBase -UserId $userId -VoiceId $voiceAssetId
Write-Host "sessionId=$sessionId voiceAssetId=$voiceAssetId"

Write-Step "Call /conversation/chat-stream with custom voice"
$content = Invoke-ChatStreamRequest -ConversationBase $convBase -SessionId $sessionId -UserId $userId -Message "Hello, custom voice smoke test."

Assert-Contains -Text $content -Needle '"type":"message.delta"' -Message "Expected message.delta not found in SSE response"
Assert-Contains -Text $content -Needle '"type":"audio_chunk"' -Message "Expected audio_chunk not found in SSE response"
Assert-Contains -Text $content -Needle '"type":"end"' -Message "Expected end event not found in SSE response"
Assert-True -Condition ($content -notlike '*VOICE_STREAM_FAILED*') -Message "Custom voice stream failed with VOICE_STREAM_FAILED"
Assert-True -Condition ($content -notlike '*voice_not_available*') -Message "Custom voice is not available"

Write-Host "response_preview:"
Write-Host ($content.Substring(0, [Math]::Min(600, $content.Length)))
Write-Pass "Custom voice stream smoke passed."
