Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\_common.ps1"

$convBase = Get-EnvValue -Name "ECHOES_CONV_BASE" -Default "http://localhost:18082"
$voiceBase = Get-EnvValue -Name "ECHOES_VOICE_BASE" -Default "http://localhost:18083"
$aiBase = Get-EnvValue -Name "ECHOES_AI_BASE" -Default "http://localhost:18085"

Write-Step "Conversation ping check"
$pingOk = $false
try {
    $ping = Invoke-RestMethod -Method Get -Uri "$convBase/conversation-session/ping" -TimeoutSec 10
    $pingOk = ($ping.code -eq 1)
} catch {
    $pingOk = $false
}

Write-Step "TCP port checks"
$targets = @(
    @{ Name = "conversation"; Url = $convBase },
    @{ Name = "voice"; Url = $voiceBase },
    @{ Name = "echoes-ai"; Url = $aiBase }
)

$results = @()
foreach ($t in $targets) {
    $uri = [Uri]$t.Url
    $ok = Test-TcpPort -HostName $uri.Host -Port $uri.Port
    $results += [PSCustomObject]@{
        service = $t.Name
        host    = $uri.Host
        port    = $uri.Port
        tcp_ok  = $ok
    }
}

$results | Format-Table -AutoSize

Assert-True -Condition $pingOk -Message "Conversation ping failed: $convBase/conversation-session/ping"
foreach ($r in $results) {
    Assert-True -Condition ([bool]$r.tcp_ok) -Message "TCP check failed: $($r.service) $($r.host):$($r.port)"
}

Write-Pass "Health check passed."
