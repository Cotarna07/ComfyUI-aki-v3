[CmdletBinding()]
param(
    [int]$Port = 8190,
    [string]$Listen = "127.0.0.1",
    [string]$MainComfyRoot = "D:\ComfyUI-aki-v3\ComfyUI",
    [string]$EmbeddedPython = "D:\ComfyUI-aki-v3\python\python.exe",
    [switch]$AutoLaunch,
    [string[]]$ExtraArgs
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$instanceRoot = Join-Path $projectRoot "runtime\instance"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$mainPy = Join-Path $MainComfyRoot "main.py"
$databasePath = Join-Path $instanceRoot "user\comfyui.db"
$databaseUrl = "sqlite:///" + ($databasePath -replace "\\", "/")

if (-not (Test-Path $mainPy)) {
    throw "ComfyUI main.py not found: $mainPy"
}

if (-not (Test-Path $instanceRoot)) {
    throw "Instance root not found, run setup_instance.ps1 first: $instanceRoot"
}

$pythonExe = $EmbeddedPython
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
}

$arguments = @(
    $mainPy,
    "--base-directory", $instanceRoot,
    "--database-url", $databaseUrl,
    "--listen", $Listen,
    "--port", $Port,
    "--preview-method", "auto",
    "--disable-cuda-malloc"
)

if ($AutoLaunch) {
    $arguments += "--auto-launch"
} else {
    $arguments += "--disable-auto-launch"
}

if ($ExtraArgs) {
    $arguments += $ExtraArgs
}

Write-Host "Starting second instance: $pythonExe $($arguments -join ' ')" -ForegroundColor Cyan
& $pythonExe @arguments