[CmdletBinding()]
param(
    [string]$EmbeddedPython = "D:\ComfyUI-aki-v3\python\python.exe",
    [switch]$ContinueOnError
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$instanceRoot = Join-Path $projectRoot "runtime\instance"
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$setupScript = Join-Path $PSScriptRoot "setup_instance.ps1"
$configPath = Join-Path $projectRoot "config\plugins.json"

if (-not (Test-Path $venvPython)) {
    & $setupScript -EmbeddedPython $EmbeddedPython -CreateOverlayVenv
    if ($LASTEXITCODE -ne 0) {
        throw "创建 overlay .venv 失败，无法继续安装插件依赖。"
    }
}

if (-not (Test-Path $instanceRoot)) {
    & $setupScript -EmbeddedPython $EmbeddedPython
    if ($LASTEXITCODE -ne 0) {
        throw "初始化实例目录失败。"
    }
}

$pluginConfig = Get-Content -Path $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$pluginNames = @($pluginConfig.plugins)
$failed = @()

foreach ($pluginName in $pluginNames) {
    $requirementsPath = Join-Path $instanceRoot "custom_nodes\$pluginName\requirements.txt"
    if (-not (Test-Path $requirementsPath)) {
        continue
    }

    Write-Host "安装插件依赖: $pluginName" -ForegroundColor Cyan
    & $venvPython -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        $failed += $pluginName
        Write-Warning "插件依赖安装失败: $pluginName"
        if (-not $ContinueOnError) {
            throw "插件依赖安装失败: $pluginName"
        }
    }
}

if ($failed.Count -gt 0) {
    Write-Warning ("以下插件依赖未完全安装: " + ($failed -join ", "))
} else {
    Write-Host "插件依赖安装完成。" -ForegroundColor Green
}