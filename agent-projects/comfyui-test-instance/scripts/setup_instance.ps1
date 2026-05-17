[CmdletBinding()]
param(
    [string]$MainComfyRoot = "D:\ComfyUI-aki-v3\ComfyUI",
    [string]$EmbeddedPython = "D:\ComfyUI-aki-v3\python\python.exe",
    [switch]$CreateOverlayVenv,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Ensure-Junction {
    param(
        [string]$Path,
        [string]$Target,
        [switch]$Replace
    )

    if (-not (Test-Path $Target)) {
        throw "Target path does not exist: $Target"
    }

    if (Test-Path $Path) {
        if (-not $Replace) {
            return
        }
        Remove-Item -Path $Path -Force -Recurse
    }

    New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
}

$projectRoot = Get-ProjectRoot
$configPath = Join-Path $projectRoot "config\plugins.json"
$instanceRoot = Join-Path $projectRoot "runtime\instance"
$instanceCustomNodes = Join-Path $instanceRoot "custom_nodes"
$mainCustomNodes = Join-Path $MainComfyRoot "custom_nodes"
$mainModels = Join-Path $MainComfyRoot "models"
$venvPath = Join-Path $projectRoot ".venv"

if (-not (Test-Path $configPath)) {
    throw "Plugin config not found: $configPath"
}

if (-not (Test-Path $MainComfyRoot)) {
    throw "ComfyUI root not found: $MainComfyRoot"
}

$pluginConfig = Get-Content -Path $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$pluginNames = @($pluginConfig.plugins)

Ensure-Directory $instanceRoot
Ensure-Directory $instanceCustomNodes
Ensure-Directory (Join-Path $instanceRoot "input")
Ensure-Directory (Join-Path $instanceRoot "output")
Ensure-Directory (Join-Path $instanceRoot "temp")
Ensure-Directory (Join-Path $instanceRoot "user")

Ensure-Junction -Path (Join-Path $instanceRoot "models") -Target $mainModels -Replace:$Force

foreach ($pluginName in $pluginNames) {
    $source = Join-Path $mainCustomNodes $pluginName
    $target = Join-Path $instanceCustomNodes $pluginName
    if (-not (Test-Path $source)) {
        Write-Warning "Plugin not found, skipped: $pluginName"
        continue
    }
    Ensure-Junction -Path $target -Target $source -Replace:$Force
}

if ($CreateOverlayVenv) {
    if (-not (Test-Path $EmbeddedPython)) {
        throw "Embedded Python not found: $EmbeddedPython"
    }

    if ((-not (Test-Path $venvPath)) -or $Force) {
        if ((Test-Path $venvPath) -and $Force) {
            Remove-Item -Path $venvPath -Force -Recurse
        }
        & $EmbeddedPython -m venv --system-site-packages $venvPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create overlay .venv, exit code: $LASTEXITCODE"
        }
    }
}

Write-Host "Second instance initialized." -ForegroundColor Green
Write-Host "Instance root: $instanceRoot"
Write-Host "Custom nodes: $instanceCustomNodes"
Write-Host "Shared models: $(Join-Path $instanceRoot 'models') -> $mainModels"
if ($CreateOverlayVenv -or (Test-Path $venvPath)) {
    Write-Host ('overlay .venv: ' + $venvPath)
}