[CmdletBinding()]
param(
    [switch]$AutoLaunch,
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"

$script = Join-Path $PSScriptRoot "start_environment.ps1"
& $script -Name "flux-kontext-py313-cu130" -AutoLaunch:$AutoLaunch -ExtraArgs $ExtraArgs
