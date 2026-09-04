$ErrorActionPreference = 'Stop'

$zipPath = 'C:\Users\Himmler\PlantNexus-CNC-Demo-Windows-x64-0.2.3.zip'
$deployRoot = 'W:\PlantNexus-CNC-Demo'
$stageRoot = 'W:\PlantNexus-CNC-Demo-0.2.3-stage'
$expandedRoot = Join-Path $stageRoot 'PlantNexus-CNC-Demo-Windows-x64-0.2.3'
$backupRoot = 'W:\PlantNexus-CNC-Demo-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$expectedSha = '93c564f5361d45dc927604ed45fa12fb72dbbe5f257366f4892cf32b455cd318'

$actualSha = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha -ne $expectedSha) {
    throw '上传包 SHA-256 不匹配。'
}
if (Test-Path -LiteralPath $stageRoot) {
    throw "暂存目录已存在：$stageRoot"
}
if (-not (Test-Path -LiteralPath $deployRoot -PathType Container)) {
    throw "部署目录不存在：$deployRoot"
}

$oldExe = Join-Path $deployRoot 'PlantNexusCncDemo.exe'
if (Test-Path -LiteralPath $oldExe -PathType Leaf) {
    & $oldExe stop | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw '无法安全停止旧演示服务。'
    }
}

New-Item -ItemType Directory -Path $stageRoot | Out-Null
Expand-Archive -LiteralPath $zipPath -DestinationPath $stageRoot
foreach ($required in @(
    'PlantNexusCncDemo.exe',
    '启动演示.cmd',
    '停止演示.cmd',
    '查看状态.cmd',
    '_internal'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $expandedRoot $required))) {
        throw "新包缺少：$required"
    }
}

Move-Item -LiteralPath $deployRoot -Destination $backupRoot
try {
    Move-Item -LiteralPath $expandedRoot -Destination $deployRoot
    $oldRuntime = Join-Path $backupRoot 'runtime'
    $newRuntime = Join-Path $deployRoot 'runtime'
    if (
        (Test-Path -LiteralPath $oldRuntime -PathType Container) -and
        -not (Test-Path -LiteralPath $newRuntime)
    ) {
        Move-Item -LiteralPath $oldRuntime -Destination $newRuntime
    }

    $config = [ordered]@{
        access_port = 4174
        allowed_networks = @('0.0.0.0/0')
        lan_mode = $true
        listen_host = '0.0.0.0'
        open_browser = $false
        settings_version = 'cnc-demo-windows-settings.v1'
    }
    $configPath = Join-Path $deployRoot 'config\demo-settings.json'
    $configJson = ($config | ConvertTo-Json -Depth 4) + [Environment]::NewLine
    [System.IO.File]::WriteAllText(
        $configPath,
        $configJson,
        [System.Text.UTF8Encoding]::new($false)
    )
}
catch {
    if (
        -not (Test-Path -LiteralPath $deployRoot) -and
        (Test-Path -LiteralPath $backupRoot)
    ) {
        Move-Item -LiteralPath $backupRoot -Destination $deployRoot
    }
    throw
}

if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot
}

$ruleName = 'PlantNexus CNC Demo 4174 - External Access'
$rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($rule) {
    $rule | Set-NetFirewallRule -Enabled True -Profile Any -RemoteAddress Any
}
else {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort 4174 `
        -RemoteAddress Any `
        -Profile Any | Out-Null
}

$env:PLANTNEXUS_DEMO_NO_PAUSE = '1'
try {
    & $env:ComSpec /d /c call (Join-Path $deployRoot '启动演示.cmd')
    if ($LASTEXITCODE -ne 0) {
        throw '新版本 CMD 启动入口执行失败。'
    }
}
finally {
    Remove-Item Env:PLANTNEXUS_DEMO_NO_PAUSE -ErrorAction SilentlyContinue
}

[pscustomobject]@{
    status = 'DEPLOYED'
    version = '0.2.3'
    deploy_root = $deployRoot
    backup_root = $backupRoot
    port = 4174
    allowed_network = '0.0.0.0/0'
    firewall_profiles = 'Any'
    firewall_remote_address = 'Any'
    package_sha256 = $actualSha
} | ConvertTo-Json -Depth 3
