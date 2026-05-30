[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [string[]]$PluginName,
    [switch]$ContinueOnError,
    [switch]$DryRun,
    [string]$ConfigPath
)

$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Resolve-ConfiguredPath {
    param(
        [string]$Path,
        [string]$ProjectRoot
    )

    if (-not $Path) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return (Join-Path $ProjectRoot $Path)
}

function Get-NamedEnvironment {
    param(
        [object]$Config,
        [string]$EnvironmentName
    )

    foreach ($environment in @($Config.environments)) {
        if ($environment.name -eq $EnvironmentName) {
            return $environment
        }
    }

    throw "Unknown environment: $EnvironmentName"
}

function Get-EnvironmentPython {
    param(
        [object]$Config,
        [object]$Environment,
        [string]$ProjectRoot
    )

    if ($Environment.managed -ne $true) {
        $embeddedPython = Resolve-ConfiguredPath -Path $Config.embedded_python -ProjectRoot $ProjectRoot
        if (Test-Path $embeddedPython) {
            return $embeddedPython
        }
        throw "Embedded Python not found: $embeddedPython"
    }

    if ($Environment.python_mode -eq "external-python") {
        $externalPython = Resolve-ConfiguredPath -Path $Environment.external_python -ProjectRoot $ProjectRoot
        if ($externalPython -and (Test-Path $externalPython)) {
            return $externalPython
        }
        throw "External Python is not configured for $($Environment.name)."
    }

    $venvPath = Resolve-ConfiguredPath -Path $Environment.venv_path -ProjectRoot $ProjectRoot
    if (-not $venvPath) {
        $runtimeRoot = Resolve-ConfiguredPath -Path $Environment.runtime_root -ProjectRoot $ProjectRoot
        $venvPath = Join-Path $runtimeRoot ".venv"
    }

    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }

    throw "Environment venv Python not found: $venvPython. Run setup_environment.ps1 -Name $($Environment.name) -CreateVenvs first."
}

$projectRoot = Get-ProjectRoot
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $projectRoot "config\environments.json"
}

if (-not (Test-Path $ConfigPath)) {
    throw "Environment config not found: $ConfigPath"
}

$config = Get-Content -Path $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$environment = Get-NamedEnvironment -Config $config -EnvironmentName $Name
$pythonExe = Get-EnvironmentPython -Config $config -Environment $environment -ProjectRoot $projectRoot
$runtimeRoot = Resolve-ConfiguredPath -Path $environment.runtime_root -ProjectRoot $projectRoot
$customNodesRoot = Join-Path $runtimeRoot "custom_nodes"

if ($environment.managed -eq $true -and (-not (Test-Path $customNodesRoot))) {
    throw "Custom nodes root not found. Run setup_environment.ps1 first: $customNodesRoot"
}

if ($PluginName -and $PluginName.Count -gt 0) {
    $plugins = @($PluginName)
} else {
    $plugins = @($environment.plugins)
}

$failed = @()
$installed = @()
$skipped = @()

foreach ($plugin in $plugins) {
    $requirementsPath = Join-Path $customNodesRoot "$plugin\requirements.txt"
    if (-not (Test-Path $requirementsPath)) {
        $skipped += $plugin
        continue
    }

    Write-Host "Installing requirements for $plugin into $($environment.name)" -ForegroundColor Cyan
    Write-Host "  python: $pythonExe"
    Write-Host "  requirements: $requirementsPath"

    if ($DryRun) {
        $installed += $plugin
        continue
    }

    & $pythonExe -m pip install -r $requirementsPath
    if ($LASTEXITCODE -ne 0) {
        $failed += $plugin
        Write-Warning "Requirement install failed: $plugin"
        if (-not $ContinueOnError) {
            throw "Requirement install failed: $plugin"
        }
    } else {
        $installed += $plugin
    }
}

Write-Host "Environment requirement install summary: $($environment.name)" -ForegroundColor Green
Write-Host ("  installed/checked: " + ($installed -join ", "))
if ($skipped.Count -gt 0) {
    Write-Host ("  skipped(no requirements.txt): " + ($skipped -join ", "))
}
if ($failed.Count -gt 0) {
    Write-Warning ("  failed: " + ($failed -join ", "))
    exit 1
}
