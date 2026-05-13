[CmdletBinding()]
param(
    [string]$InstallDir = (Join-Path $PSScriptRoot "..\runtime\tools\aria2"),
    [switch]$AddToUserPath
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$installPath = [System.IO.Path]::GetFullPath($InstallDir)
$tempRoot = Join-Path $env:TEMP ("aria2-bootstrap-" + [Guid]::NewGuid().ToString('N'))

New-Item -ItemType Directory -Force -Path $installPath | Out-Null
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    $headers = @{ 'User-Agent' = 'civitai-downloader-bootstrap' }
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/aria2/aria2/releases/latest' -Headers $headers
    $asset = $release.assets | Where-Object { $_.name -match 'win-64bit-build1\.zip$' } | Select-Object -First 1
    if (-not $asset) {
        throw 'Could not find a Windows 64-bit aria2 release asset.'
    }

    $zipPath = Join-Path $tempRoot $asset.name
    $extractPath = Join-Path $tempRoot 'extract'

    Write-Host "Downloading aria2: $($asset.browser_download_url)"
    Invoke-WebRequest -Uri $asset.browser_download_url -Headers $headers -OutFile $zipPath

    Write-Host "Extracting to temporary directory: $extractPath"
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

    $sourceDir = Get-ChildItem -Path $extractPath -Directory | Select-Object -First 1
    if (-not $sourceDir) {
        throw 'Could not find the extracted aria2 directory.'
    }

    Get-ChildItem -Path $installPath -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
    Copy-Item -Path (Join-Path $sourceDir.FullName '*') -Destination $installPath -Recurse -Force

    $aria2Exe = Join-Path $installPath 'aria2c.exe'
    if (-not (Test-Path $aria2Exe)) {
        throw 'aria2c.exe was not found after installation.'
    }

    if (-not (($env:Path -split ';') -contains $installPath)) {
        $env:Path = "$installPath;$env:Path"
    }

    if ($AddToUserPath) {
        $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
        $parts = @()
        if ($userPath) {
            $parts = $userPath -split ';' | Where-Object { $_ }
        }
        if ($parts -notcontains $installPath) {
            $newPath = (@($parts) + $installPath) -join ';'
            [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
            Write-Host 'Added the aria2 directory to the user PATH. Open a new terminal to use it.'
        }
        else {
            Write-Host 'The user PATH already contains this aria2 directory.'
        }
    }

    Write-Host 'aria2 installation completed. Version info:'
    & $aria2Exe --version
    Write-Host 'Install path:' $installPath
    Write-Host 'download.py will now prefer aria2c automatically.'
}
finally {
    Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}