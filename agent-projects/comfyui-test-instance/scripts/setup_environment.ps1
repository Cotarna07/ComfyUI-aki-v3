[CmdletBinding()]
param(
    [string[]]$Name,
    [switch]$All,
    [switch]$CreateVenvs,
    [switch]$Force,
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

$projectRoot = Get-ProjectRoot
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $projectRoot "config\environments.json"
}

if (-not (Test-Path $ConfigPath)) {
    throw "Environment config not found: $ConfigPath"
}

$config = Get-Content -Path $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$mainComfyRoot = Resolve-ConfiguredPath -Path $config.main_comfy_root -ProjectRoot $projectRoot
$embeddedPython = Resolve-ConfiguredPath -Path $config.embedded_python -ProjectRoot $projectRoot
$sharedModelRoot = Resolve-ConfiguredPath -Path $config.shared_model_root -ProjectRoot $projectRoot
$mainCustomNodes = Join-Path $mainComfyRoot "custom_nodes"

if (-not (Test-Path $mainComfyRoot)) {
    throw "Main ComfyUI root not found: $mainComfyRoot"
}
if (-not (Test-Path $mainCustomNodes)) {
    throw "Main custom_nodes path not found: $mainCustomNodes"
}
if (-not (Test-Path $sharedModelRoot)) {
    throw "Shared model root not found: $sharedModelRoot"
}
if ($CreateVenvs -and (-not (Test-Path $embeddedPython))) {
    throw "Embedded Python not found: $embeddedPython"
}

$targets = @()
if ($All) {
    $targets = @($config.environments | Where-Object { $_.managed -eq $true })
} elseif ($Name -and $Name.Count -gt 0) {
    foreach ($environmentName in $Name) {
        $targets += Get-NamedEnvironment -Config $config -EnvironmentName $environmentName
    }
} else {
    throw "Specify -All or -Name <environment-name>."
}

foreach ($environment in $targets) {
    if ($environment.managed -ne $true) {
        Write-Host "Skip unmanaged environment: $($environment.name)"
        continue
    }

    $runtimeRoot = Resolve-ConfiguredPath -Path $environment.runtime_root -ProjectRoot $projectRoot
    $customNodesRoot = Join-Path $runtimeRoot "custom_nodes"

    Ensure-Directory $runtimeRoot
    Ensure-Directory $customNodesRoot
    Ensure-Directory (Join-Path $runtimeRoot "input")
    Ensure-Directory (Join-Path $runtimeRoot "output")
    Ensure-Directory (Join-Path $runtimeRoot "temp")
    Ensure-Directory (Join-Path $runtimeRoot "user")
    Ensure-Directory (Join-Path $runtimeRoot "logs")

    Ensure-Junction -Path (Join-Path $runtimeRoot "models") -Target $sharedModelRoot -Replace:$Force

    $missingPlugins = @()
    foreach ($pluginName in @($environment.plugins)) {
        $source = Join-Path $mainCustomNodes $pluginName
        $target = Join-Path $customNodesRoot $pluginName
        if (-not (Test-Path $source)) {
            $missingPlugins += $pluginName
            Write-Warning "Plugin not found, skipped: $pluginName"
            continue
        }
        Ensure-Junction -Path $target -Target $source -Replace:$Force
    }

    if ($CreateVenvs) {
        if ($environment.python_mode -eq "external-python") {
            Write-Warning "Skip venv creation for external-python environment: $($environment.name)"
        } else {
            $venvPath = Resolve-ConfiguredPath -Path $environment.venv_path -ProjectRoot $projectRoot
            if (-not $venvPath) {
                $venvPath = Join-Path $runtimeRoot ".venv"
            }

            if ((-not (Test-Path $venvPath)) -or $Force) {
                if ((Test-Path $venvPath) -and $Force) {
                    Remove-Item -Path $venvPath -Force -Recurse
                }
                & $embeddedPython -m venv --system-site-packages $venvPath
                if ($LASTEXITCODE -ne 0) {
                    throw "Failed to create venv for $($environment.name), exit code: $LASTEXITCODE"
                }
            }
        }
    }

    Write-Host "Environment ready: $($environment.name)" -ForegroundColor Green
    Write-Host "  root: $runtimeRoot"
    Write-Host "  port: $($environment.port)"
    if ($missingPlugins.Count -gt 0) {
        Write-Warning ("  missing plugins: " + ($missingPlugins -join ", "))
    }
}
