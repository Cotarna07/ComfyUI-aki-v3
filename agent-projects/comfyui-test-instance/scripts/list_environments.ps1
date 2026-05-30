[CmdletBinding()]
param(
    [string]$ConfigPath
)

$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$projectRoot = Get-ProjectRoot
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $projectRoot "config\environments.json"
}

if (-not (Test-Path $ConfigPath)) {
    throw "Environment config not found: $ConfigPath"
}

$config = Get-Content -Path $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json

@($config.environments) |
    Select-Object name, managed, port, python_mode, status, runtime_root, purpose |
    Format-Table -AutoSize
