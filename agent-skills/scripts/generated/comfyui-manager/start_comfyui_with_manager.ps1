param(
    [int]$Port = 8188,
    [int]$WaitSeconds = 45,
    [switch]$KeepLauncher,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$pythonExe = Join-Path $workspaceRoot 'python\python.exe'
$comfyMain = Join-Path $workspaceRoot 'ComfyUI\main.py'
$launcherExe = Join-Path $workspaceRoot '.launcher\StableDiffusionWebUILauncher.exe'

if (-not (Test-Path $pythonExe)) {
    throw "python runtime not found: $pythonExe"
}

if (-not (Test-Path $comfyMain)) {
    throw "ComfyUI main.py not found: $comfyMain"
}

function Get-ComfyPythonProcess {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$comfyMain*" }
}

function Get-LauncherProcess {
    Get-CimInstance Win32_Process -Filter "Name='StableDiffusionWebUILauncher.exe'" |
        Where-Object { $_.ExecutablePath -eq $launcherExe }
}

if (-not $KeepLauncher) {
    $launcherProcesses = @(Get-LauncherProcess)
    foreach ($launcherProcess in $launcherProcesses) {
        Stop-Process -Id $launcherProcess.ProcessId -Force
    }
}

$existingComfy = @(Get-ComfyPythonProcess)
foreach ($process in $existingComfy) {
    Stop-Process -Id $process.ProcessId -Force
}

$argumentList = @($comfyMain)
if (-not $NoBrowser) {
    $argumentList += '--auto-launch'
}
$argumentList += @('--preview-method', 'auto', '--disable-cuda-malloc', '--enable-manager', '--port', $Port)

$startedProcess = Start-Process -FilePath $pythonExe -ArgumentList $argumentList -WorkingDirectory (Join-Path $workspaceRoot 'ComfyUI') -PassThru

Write-Host "Started ComfyUI PID $($startedProcess.Id)"
Write-Host ("Command: " + $pythonExe + " " + ($argumentList -join ' '))

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$promptRelayUrl = "http://127.0.0.1:$Port/object_info/PromptRelayEncodeTimeline"

do {
    try {
        $response = Invoke-WebRequest -UseBasicParsing $promptRelayUrl -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            Write-Host "ComfyUI is ready and PromptRelayEncodeTimeline is registered."
            exit 0
        }
    }
    catch {
    }
} while ((Get-Date) -lt $deadline)

Write-Warning "ComfyUI did not become ready within $WaitSeconds seconds."
Write-Host "If the console window is still opening nodes, wait a little longer and re-run:"
Write-Host "Invoke-WebRequest -UseBasicParsing $promptRelayUrl -TimeoutSec 15 | Select-Object StatusCode"
exit 1