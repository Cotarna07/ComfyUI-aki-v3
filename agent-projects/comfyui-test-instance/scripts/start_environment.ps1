[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [string]$Listen,
    [int]$Port,
    [switch]$AutoLaunch,
    [switch]$UseEmbeddedPython,
    [string[]]$ExtraArgs,
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

$projectRoot = Get-ProjectRoot
if (-not $ConfigPath) {
    $ConfigPath = Join-Path $projectRoot "config\environments.json"
}

if (-not (Test-Path $ConfigPath)) {
    throw "Environment config not found: $ConfigPath"
}

$config = Get-Content -Path $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$environment = Get-NamedEnvironment -Config $config -EnvironmentName $Name

if (-not $Listen) {
    $Listen = $config.default_listen
}
if (-not $Port) {
    $Port = [int]$environment.port
}

$mainComfyRoot = Resolve-ConfiguredPath -Path $config.main_comfy_root -ProjectRoot $projectRoot
$embeddedPython = Resolve-ConfiguredPath -Path $config.embedded_python -ProjectRoot $projectRoot
$mainPy = Join-Path $mainComfyRoot "main.py"

if (-not (Test-Path $mainPy)) {
    throw "ComfyUI main.py not found: $mainPy"
}

$pythonExe = $embeddedPython
$runtimeRoot = Resolve-ConfiguredPath -Path $environment.runtime_root -ProjectRoot $projectRoot
$arguments = @($mainPy)

if ($environment.managed -eq $true) {
    if (-not (Test-Path $runtimeRoot)) {
        throw "Runtime root not found. Run setup_environment.ps1 first: $runtimeRoot"
    }

    $arguments += @("--base-directory", $runtimeRoot)
    $databasePath = Join-Path $runtimeRoot "user\comfyui.db"
    $databaseUrl = "sqlite:///" + ($databasePath -replace "\\", "/")
    $arguments += @("--database-url", $databaseUrl)

    if ($environment.python_mode -eq "external-python") {
        $externalPython = Resolve-ConfiguredPath -Path $environment.external_python -ProjectRoot $projectRoot
        if (-not $externalPython -or (-not (Test-Path $externalPython))) {
            throw "External Python is not configured for $($environment.name). Fill external_python in config/environments.json."
        }
        $pythonExe = $externalPython
    } elseif (-not $UseEmbeddedPython) {
        $venvPath = Resolve-ConfiguredPath -Path $environment.venv_path -ProjectRoot $projectRoot
        if ($venvPath) {
            $venvPython = Join-Path $venvPath "Scripts\python.exe"
            if (Test-Path $venvPython) {
                $pythonExe = $venvPython
            }
        }
    }
}

$arguments += @("--listen", $Listen, "--port", $Port)

if ($AutoLaunch) {
    $arguments += "--auto-launch"
} else {
    $arguments += "--disable-auto-launch"
}

$arguments += @($config.default_extra_args)

if ($ExtraArgs) {
    $arguments += $ExtraArgs
}

Write-Host "Starting environment: $($environment.name)" -ForegroundColor Cyan
Write-Host "  python: $pythonExe"
Write-Host "  url: http://$Listen`:$Port"
& $pythonExe @arguments
