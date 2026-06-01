param(
    [string]$Video = "",
    [string]$Audio,
    [string]$Output = "",
    [string]$RunId = "",
    [string]$CaseId = "",
    [ValidateSet("OG", "IN", "UP")]
    [string]$Variant = "OG",
    [double]$AudioVolume = 1.0,
    [string]$AudioBitrate = "192k",
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ([string]::IsNullOrWhiteSpace($Audio)) {
    throw "Missing -Audio. Example: -Audio D:\music\bgm.mp3"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Resolve-Path (Join-Path $scriptDir "..\..\..\..")
$outputRoot = Join-Path $root "ComfyUI\output\WAN\agent_tests\cms_wan22_loop_120"

if ([string]::IsNullOrWhiteSpace($Video)) {
    if ([string]::IsNullOrWhiteSpace($RunId) -or [string]::IsNullOrWhiteSpace($CaseId)) {
        throw "Specify -Video, or specify both -RunId and -CaseId."
    }
    $caseDir = Join-Path $outputRoot $RunId
    $pattern = "{0}_{1}_*.mp4" -f $CaseId, $Variant
    $match = Get-ChildItem -LiteralPath $caseDir -Filter $pattern -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $match) {
        throw "Video not found: $caseDir\$pattern"
    }
    $Video = $match.FullName
}

$videoPath = Resolve-Path -LiteralPath $Video
$audioPath = Resolve-Path -LiteralPath $Audio

if ([string]::IsNullOrWhiteSpace($Output)) {
    $base = [System.IO.Path]::GetFileNameWithoutExtension($videoPath.Path)
    $dir = Split-Path -Parent $videoPath.Path
    $Output = Join-Path $dir "${base}_AUDIO.mp4"
}

if ((Test-Path -LiteralPath $Output) -and (-not $Overwrite)) {
    throw "Output already exists: $Output. Add -Overwrite to replace it."
}

$ffmpeg = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
if (-not $ffmpeg) {
    throw "ffmpeg was not found. Make sure ffmpeg is available in PATH."
}

$filter = "volume=$AudioVolume"

Write-Host "Video: $($videoPath.Path)"
Write-Host "Audio: $($audioPath.Path)"
Write-Host "Output: $Output"

& $ffmpeg `
    $(if ($Overwrite) { "-y" } else { "-n" }) `
    -i $videoPath.Path `
    -stream_loop -1 -i $audioPath.Path `
    -map 0:v:0 `
    -map 1:a:0 `
    -c:v copy `
    -filter:a $filter `
    -c:a aac `
    -b:a $AudioBitrate `
    -shortest `
    -movflags +faststart `
    $Output

if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg failed with exit code $LASTEXITCODE"
}

Write-Host "Done: $Output"
