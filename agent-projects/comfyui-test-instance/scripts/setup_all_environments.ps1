[CmdletBinding()]
param(
    [switch]$CreateVenvs,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$setupScript = Join-Path $PSScriptRoot "setup_environment.ps1"
& $setupScript -All -CreateVenvs:$CreateVenvs -Force:$Force
