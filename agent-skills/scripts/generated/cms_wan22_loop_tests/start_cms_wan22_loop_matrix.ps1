param(
    [string]$RunId = "",
    [string[]]$Only = @(),
    [string[]]$ModelProfiles = @(),
    [int]$Length = 120,
    [double]$Fps = 16.0,
    [int64]$Seed = 260531120,
    [string]$Server = "http://127.0.0.1:8188",
    [int]$TimeoutSeconds = 14400,
    [switch]$DryRun,
    [switch]$RandomSeeds,
    [switch]$RerunCompleted,
    [switch]$KeepDisabledPostprocess,
    [switch]$EnablePostprocess,
    [switch]$EnableFrameSkipPreview,
    [switch]$FullArtifacts,
    [switch]$SkipFreeMemory,
    [switch]$AllModelProfiles,
    [switch]$ListModelProfiles,
    [switch]$NoOpenReport
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path (Join-Path $scriptDir "..\..\..\..")
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$matrixScript = Join-Path $scriptDir "run_cms_wan22_loop_matrix.py"

if ($ListModelProfiles) {
    & $python $matrixScript "--list-model-profiles"
    exit $LASTEXITCODE
}

if ([string]::IsNullOrWhiteSpace($RunId)) {
    if ($AllModelProfiles -or $ModelProfiles.Count -gt 0) {
        $RunId = "wan120-model-lora-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    } else {
        $RunId = "wan120-matrix-" + (Get-Date -Format "yyyyMMdd-HHmmss")
    }
}

$runtimeRoot = Join-Path $root "agent-skills\comfyui\runtime\cms_wan22_loop_matrix"
$runDir = Join-Path $runtimeRoot $RunId
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$stdoutLog = Join-Path $runDir "run.stdout.log"
$stderrLog = Join-Path $runDir "run.stderr.log"

Write-Host "CMS Wan2.2 Loop matrix"
Write-Host "RunId: $RunId"
Write-Host "RunDir: $runDir"
Write-Host "Server: $Server"

if ((-not $SkipFreeMemory) -and (-not $ListModelProfiles)) {
    try {
        $body = @{ unload_models = $true; free_memory = $true } | ConvertTo-Json
        Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$Server/free" -Body $body -ContentType "application/json" -TimeoutSec 10 | Out-Null
        Start-Sleep -Seconds 2
        Write-Host "Pre-run cache cleanup requested."
    } catch {
        Write-Warning "Could not call /free before run: $($_.Exception.Message)"
    }
}

$artifactMode = if ($FullArtifacts) { "full" } else { "minimal" }

$argsList = @(
    $matrixScript,
    "--run-id", $RunId,
    "--length", "$Length",
    "--fps", "$Fps",
    "--seed", "$Seed",
    "--server", $Server,
    "--timeout", "$TimeoutSeconds",
    "--poll", "10",
    "--artifact-mode", $artifactMode
)

if (-not $DryRun) {
    $argsList += @("--submit", "--allow-ui-convert")
}
if ($RandomSeeds) {
    $argsList += "--random-seeds"
}
if ($RerunCompleted) {
    $argsList += "--rerun-completed"
}
if ($KeepDisabledPostprocess) {
    $argsList += "--keep-disabled-postprocess"
}
if ($EnablePostprocess) {
    $argsList += "--enable-postprocess"
}
if ($EnableFrameSkipPreview) {
    $argsList += "--enable-frame-skip-preview"
}
if ($FullArtifacts) {
    $argsList += "--write-api"
}
if ($SkipFreeMemory) {
    $argsList += "--skip-free-memory"
}

if ($AllModelProfiles) {
    $argsList += "--all-model-profiles"
}
if ($ListModelProfiles) {
    $argsList += "--list-model-profiles"
}

$normalizedOnly = @()
foreach ($item in $Only) {
    foreach ($part in ($item -split ",")) {
        $trimmed = $part.Trim()
        if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
            $normalizedOnly += $trimmed
        }
    }
}

if ($normalizedOnly.Count -gt 0) {
    $argsList += "--only"
    $argsList += $normalizedOnly
}

$normalizedModelProfiles = @()
foreach ($item in $ModelProfiles) {
    foreach ($part in ($item -split ",")) {
        $trimmed = $part.Trim()
        if (-not [string]::IsNullOrWhiteSpace($trimmed)) {
            $normalizedModelProfiles += $trimmed
        }
    }
}

if ($normalizedModelProfiles.Count -gt 0) {
    $argsList += "--model-profiles"
    $argsList += $normalizedModelProfiles
}

Write-Host "Starting matrix run..."
Write-Host "Stdout: $stdoutLog"
Write-Host "Stderr: $stderrLog"

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $python @argsList 1> $stdoutLog 2> $stderrLog
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference

$report = Join-Path $runDir "report.html"
if ($exitCode -eq 0) {
    Write-Host "Matrix run completed."
    Write-Host "HTML report: $report"
    if ((-not $NoOpenReport) -and (Test-Path $report)) {
        Start-Process $report
    }
} else {
    Write-Error "Matrix run failed with exit code $exitCode. Check logs in $runDir"
}

exit $exitCode
