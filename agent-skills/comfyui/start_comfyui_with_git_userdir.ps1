param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$ComfyArgs,
    [string]$PythonExe,
    [string]$ComfyDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

if (-not $PythonExe) {
    $venvPython = Join-Path $workspaceRoot '.venv\Scripts\python.exe'
    $bundledPython = Join-Path $workspaceRoot 'python\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        $PythonExe = $venvPython
    } elseif (Test-Path -LiteralPath $bundledPython) {
        $PythonExe = $bundledPython
    } else {
        $PythonExe = 'python'
    }
}

if (-not $ComfyDir) {
    $ComfyDir = Join-Path $workspaceRoot 'ComfyUI'
}

$userDir = Join-Path $workspaceRoot 'agent-skills\comfyui\userdata'

Push-Location $ComfyDir
try {
    & $PythonExe 'main.py' '--user-directory' $userDir @ComfyArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}