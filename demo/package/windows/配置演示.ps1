[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$configPath = Join-Path $PSScriptRoot 'config\demo-settings.json'
$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json

Write-Host 'PlantNexus 精密机加工排产演示配置' -ForegroundColor Cyan
$portText = Read-Host "访问端口（当前 $($config.access_port)，直接回车保持）"
if ($portText) {
    $port = 0
    if (-not [int]::TryParse($portText, [ref]$port) -or $port -lt 1 -or $port -gt 65535) {
        throw '端口必须是 1～65535 的整数。'
    }
    $config.access_port = $port
}

$mode = Read-Host '访问模式：输入 1 仅本机，输入 2 可信局域网（直接回车保持）'
if ($mode -eq '1') {
    $config.lan_mode = $false
    $config.listen_host = '127.0.0.1'
    $config.allowed_networks = @()
}
elseif ($mode -eq '2') {
    $config.lan_mode = $true
    $config.listen_host = '0.0.0.0'
    $networks = Read-Host '允许网段（逗号分隔；回车采用 10/8、172.16/12、192.168/16）'
    if ($networks) {
        $config.allowed_networks = @($networks.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
    else {
        $config.allowed_networks = @('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')
    }
}
elseif ($mode) {
    throw '访问模式只能输入 1 或 2。'
}

$json = $config | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText($configPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
Write-Host "配置已保存：$configPath" -ForegroundColor Green
Write-Host '请先停止再启动演示，使新配置生效。'
