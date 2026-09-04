[CmdletBinding()]
param(
    [ValidateSet("doctor", "start", "stop", "status", "health", "reset", "smoke")]
    [string]$Command = "start",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArguments
)

$demoRoot = $PSScriptRoot
$repositoryRoot = Split-Path -Parent $demoRoot
$demoExitCode = 1

Push-Location -LiteralPath $repositoryRoot
try {
    & uv run python "$demoRoot/scripts/democtl.py" $Command @CommandArguments
    $demoExitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

exit $demoExitCode
