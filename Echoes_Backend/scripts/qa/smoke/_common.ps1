Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "[STEP] $Message"
}

function Write-Pass {
    param([string]$Message)
    Write-Host "[PASS] $Message" -ForegroundColor Green
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[FAIL] $Message" -ForegroundColor Red
}

function Get-EnvValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string]$Default = "",
        [switch]$Required
    )

    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        $value = $Default
    }
    if ($Required -and [string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required env var: $Name"
    }
    return $value
}

function Assert-True {
    param(
        [Parameter(Mandatory = $true)][bool]$Condition,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Contains {
    param(
        [string]$Text,
        [string]$Needle,
        [string]$Message
    )
    if ($Text -notlike "*$Needle*") {
        throw $Message
    }
}

function New-TurnId {
    return [Guid]::NewGuid().ToString()
}

function Get-StatusCodeFromWebException {
    param([Parameter(Mandatory = $true)]$Exception)

    if ($null -eq $Exception) {
        return -1
    }
    if (-not ($Exception.PSObject.Properties.Name -contains "Response")) {
        return -1
    }
    if ($null -eq $Exception.Response) {
        return -1
    }
    try {
        return [int]$Exception.Response.StatusCode
    } catch {
        return -1
    }
}

function Get-ResponseBodyFromWebException {
    param([Parameter(Mandatory = $true)]$Exception)

    if ($null -eq $Exception) {
        return ""
    }
    if (-not ($Exception.PSObject.Properties.Name -contains "Response")) {
        return ""
    }
    if ($null -eq $Exception.Response) {
        return ""
    }
    try {
        $stream = $Exception.Response.GetResponseStream()
        if ($null -eq $stream) {
            return ""
        }
        $reader = New-Object System.IO.StreamReader($stream)
        return $reader.ReadToEnd()
    } catch {
        return ""
    }
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutMs = 3000
    )
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)
        if (-not $ok) {
            return $false
        }
        $client.EndConnect($iar) | Out-Null
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function New-ConversationSession {
    param(
        [Parameter(Mandatory = $true)][string]$ConversationBase,
        [Parameter(Mandatory = $true)][string]$UserId,
        [string]$VoiceId = ""
    )

    $title = "QA-SMOKE-" + (Get-Date -Format "yyyyMMddHHmmss")
    $url = "$ConversationBase/conversation-session?title=$([uri]::EscapeDataString($title))&userId=$([uri]::EscapeDataString($UserId))"
    if (-not [string]::IsNullOrWhiteSpace($VoiceId)) {
        $url += "&voiceId=$([uri]::EscapeDataString($VoiceId))"
    }
    $resp = Invoke-RestMethod -Method Post -Uri $url -TimeoutSec 30
    if ($resp.code -ne 1 -or $null -eq $resp.data -or [string]::IsNullOrWhiteSpace($resp.data.id)) {
        throw "Create session failed. response=$($resp | ConvertTo-Json -Depth 6)"
    }
    return [string]$resp.data.id
}

function Invoke-ChatStreamRequest {
    param(
        [Parameter(Mandatory = $true)][string]$ConversationBase,
        [Parameter(Mandatory = $true)][string]$SessionId,
        [Parameter(Mandatory = $true)][string]$UserId,
        [string]$Message = "Hello, this is an automated smoke test.",
        [int]$TimeoutSec = 90
    )
    $turnId = New-TurnId
    $body = @{
        message        = $Message
        sessionId      = $SessionId
        turnId         = $turnId
        idempotencyKey = $turnId
        stream         = $true
        sysUserId      = $UserId
    } | ConvertTo-Json

    $url = "$ConversationBase/conversation/chat-stream"
    $tmpBody = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($tmpBody, $body, [System.Text.Encoding]::UTF8)
        $output = & curl.exe -sS -N --max-time $TimeoutSec `
            -X POST $url `
            -H "Content-Type: application/json" `
            -H "Accept: text/event-stream" `
            --data-binary "@$tmpBody" 2>&1
        $text = [string]($output -join [Environment]::NewLine)
        if ([string]::IsNullOrWhiteSpace($text)) {
            throw "Empty SSE response from $url"
        }
        return $text
    } finally {
        if (Test-Path $tmpBody) {
            Remove-Item -Force $tmpBody -ErrorAction SilentlyContinue
        }
    }
}

