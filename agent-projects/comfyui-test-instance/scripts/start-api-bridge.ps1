[CmdletBinding()]
param(
    [switch]$AutoLaunch,
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"

$script = Join-Path $PSScriptRoot "start_environment.ps1"
& $script -Name "api-bridge-py313" -AutoLaunch:$AutoLaunch -ExtraArgs $ExtraArgs
