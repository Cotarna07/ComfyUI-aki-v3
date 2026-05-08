[CmdletBinding()]
param(
    [string[]]$Name,
    [switch]$KeepTemp
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$CommandName)

    if (-not (Get-Command -Name $CommandName -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $CommandName"
    }
}

function Invoke-RobocopyMirror {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Destination)) {
        New-Item -ItemType Directory -Path $Destination | Out-Null
    }

    robocopy $Source $Destination /MIR /XD .git | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed for '$Source' -> '$Destination' with exit code $LASTEXITCODE"
    }
}

Require-Command -CommandName git
Require-Command -CommandName robocopy

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptRoot '..'))
$referenceRoot = Join-Path $projectRoot 'resources\reference-projects'
$manifestPath = Join-Path $referenceRoot 'manifest.json'

if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Manifest not found: $manifestPath"
}

$rawManifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8
$originalEntries = @(foreach ($item in (ConvertFrom-Json -InputObject $rawManifest)) { $item })
$manifestEntries = @($originalEntries)

if ($Name -and $Name.Count -gt 0) {
    $selectedNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($item in $Name) {
        [void]$selectedNames.Add($item)
    }
    $manifestEntries = @($manifestEntries | Where-Object { $selectedNames.Contains($_.name) })
    if ($manifestEntries.Count -eq 0) {
        throw 'No manifest entries matched the provided -Name values.'
    }
}

$tempRoot = Join-Path $projectRoot 'runtime\refresh-reference-projects\tmp'
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

$refreshTimestamp = (Get-Date).ToString('s')
$updatedEntries = New-Object System.Collections.Generic.List[object]

try {
    foreach ($entry in $manifestEntries) {
        $repoName = [string]$entry.name
        $sourceUrl = [string]$entry.source_url
        $category = [string]$entry.category
        $targetPath = Join-Path $referenceRoot $repoName
        $clonePath = Join-Path $tempRoot $repoName

        if (Test-Path -LiteralPath $clonePath) {
            Remove-Item -LiteralPath $clonePath -Recurse -Force
        }

        Write-Host "[refresh] cloning $repoName"
        git clone --depth 1 $sourceUrl $clonePath | Out-Host

        $commit = ((git -C $clonePath rev-parse HEAD) | Out-String).Trim()
        Invoke-RobocopyMirror -Source $clonePath -Destination $targetPath

        $nestedGitPath = Join-Path $targetPath '.git'
        if (Test-Path -LiteralPath $nestedGitPath) {
            Remove-Item -LiteralPath $nestedGitPath -Recurse -Force
        }

        $updatedEntries.Add([pscustomobject]@{
            name = $repoName
            source_url = $sourceUrl
            category = $category
            cloned_commit = $commit
            local_path = $targetPath
            git_removed = $true
            refreshed_at = $refreshTimestamp
        }) | Out-Null
    }

    if (-not $Name -or $Name.Count -eq 0) {
        $entriesToWrite = $updatedEntries
    }
    else {
        $updatedByName = @{}
        foreach ($entry in $updatedEntries) {
            $updatedByName[$entry.name] = $entry
        }

        $entriesToWrite = foreach ($entry in $originalEntries) {
            if ($updatedByName.ContainsKey([string]$entry.name)) {
                $updatedByName[[string]$entry.name]
            }
            else {
                $entry
            }
        }
    }

    $entriesToWrite | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
    Write-Host "[refresh] updated manifest: $manifestPath"
}
finally {
    if (-not $KeepTemp -and (Test-Path -LiteralPath $tempRoot)) {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force
    }
}

Write-Host "[refresh] done"