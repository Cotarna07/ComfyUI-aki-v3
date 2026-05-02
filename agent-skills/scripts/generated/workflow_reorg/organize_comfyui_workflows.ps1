param(
    [string]$Root = 'D:\ComfyUI-aki-v3\ComfyUI\user\default\workflows\comfyui_workflow',
    [switch]$Execute,
    [int]$PreviewCount = 40
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$legacyFolders = @(
    '10款神级工作流',
    '4.工作流',
    'FLUX工作流合集',
    '电商，换脸，转绘，老照片修复等等工作流'
)

$archiveRootName = '90_旧结构归档_2026-05-02'

function Ensure-Directory {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Get-NormalizedText {
    param([System.IO.FileInfo]$File)

    return ($File.FullName + ' ' + $File.DirectoryName + ' ' + $File.BaseName).ToLowerInvariant()
}

function Get-FormatCategory {
    param(
        [string]$Text,
        [string]$Path
    )

    if ($Path -match '1\.反推提示词|9\.依赖三方类' -or $Text -match '反推|提示词|caption|ollama|gemini|词云|janus') {
        return '08_分析与辅助'
    }

    if ($Path -match '8\.高清放大类' -or $Text -match '高清放大|upscale|supir|老照片修复|高\s*清|图像高清|视频高清') {
        return '07_增强与修复'
    }

    if ($Path -match '7\.音生视频类' -or $Text -match '音生视频|说话|唱歌|rap|口型|数字人') {
        return '06_音频到视频'
    }

    if ($Path -match '6\.视频生视频' -or $Text -match '视频转绘|视频编辑|vace|去水印|去字幕|补全|修补|video edit|video editing|续帧|视频修补') {
        return '05_视频到视频'
    }

    if ($Path -match '5\.图生视频类' -or $Text -match '图生视频|image-to-video|image to video|i2v|首尾帧|照片转跳舞|motion control|animate|跳舞视频|照片转视频|图片转视频|mimicmotion|动作迁移') {
        return '04_图像到视频'
    }

    if ($Path -match '4\.文生视频类' -or $Text -match '文生视频|text-to-video|text to video|t2v|视频生成|首尾帧无限循环|视频用的的工作流集合') {
        return '03_文本到视频'
    }

    if ($Text -match '物体去除|抠图|去背|修手|产品精修|万物迁移|换脸|换头|换装|换衣|转绘|风格迁移|局部重绘|扩图|上色|背景替换|试衣|产品图') {
        return '02_图像到图像'
    }

    if ($Path -match '3\.图生图片类' -or $Text -match '图生图|换脸|换头|换装|换衣|转绘|风格迁移|局部重绘|扩图|inpaint|faceid|ip-adapter|试衣|catvton|edit anything|背景替换|产品图') {
        return '02_图像到图像'
    }

    if ($Text -match '参考生图|写真|海报|室内|建筑|景观|渲染|人像|肖像|产品生成|美女|固定角色|一致性人物|小红书') {
        return '01_文本到图像'
    }

    if ($Path -match '2\.文生图片类' -or $Text -match '文生图|海报|室内|建筑|景观|渲染|人像|肖像|flux1|sd3|lumina|混元模型|生成lora') {
        return '01_文本到图像'
    }

    return '99_未识别'
}

function Get-UseCategory {
    param(
        [string]$Text,
        [string]$Format
    )

    if ($Text -match '反推|提示词|caption|ollama|gemini|词云|janus') {
        return '01_提示词分析'
    }

    if ($Text -match '高清放大|upscale|supir|老照片|修复|清晰|放大') {
        return '02_高清放大修复'
    }

    if ($Text -match '物体去除|抠图|去背|移除对象|自动抠图') {
        return '13_局部编辑去背'
    }

    if ($Text -match 'controlnet|控图') {
        return '14_控图与条件引导'
    }

    if ($Text -match '换脸|换头|face|换装|换衣|试衣|catvton|虚拟试穿') {
        return '03_换脸换装'
    }

    if ($Text -match '转绘|风格迁移|风格|上色|动漫|redux|iclight|icedit|kontext') {
        return '04_转绘风格迁移'
    }

    if ($Text -match '电商|产品|模特|首饰|商品') {
        return '05_电商产品'
    }

    if ($Text -match '室内|建筑|景观|渲染|白模') {
        return '06_室内建筑景观'
    }

    if ($Text -match '一致性|固定角色|多角度|多副本|姿势|角色|persona') {
        return '07_人物一致性'
    }

    if ($Text -match 'vace|outpaint|去水印|去字幕|去除|编辑|补全|修补|转绘稳定|视频转绘') {
        return '08_视频编辑修补'
    }

    if ($Text -match 'animate|motion|跳舞|动作|首尾帧|照片转视频|mimicmotion|sonic|说话|唱歌|rap') {
        return '09_动作驱动动画'
    }

    if ($Text -match '多图|融合|拼合') {
        return '10_多图融合编辑'
    }

    if ($Text -match 'fooocus|photoshop|第三方|janus-pro|sdppp') {
        return '11_第三方集成'
    }

    switch ($Format) {
        '01_文本到图像' { return '12_基础生成' }
        '02_图像到图像' { return '12_基础生成' }
        '03_文本到视频' { return '12_基础生成' }
        '04_图像到视频' { return '12_基础生成' }
        '05_视频到视频' { return '08_视频编辑修补' }
        '06_音频到视频' { return '09_动作驱动动画' }
        '07_增强与修复' { return '02_高清放大修复' }
        '08_分析与辅助' { return '01_提示词分析' }
        '09_第三方集成' { return '11_第三方集成' }
        default { return '99_其他用途' }
    }
}

function Resolve-FallbackFormat {
    param(
        [string]$Text,
        [string]$Use,
        [string]$Model
    )

    switch ($Use) {
        '01_提示词分析' { return '08_分析与辅助' }
        '02_高清放大修复' { return '07_增强与修复' }
        '03_换脸换装' { return '02_图像到图像' }
        '04_转绘风格迁移' { return '02_图像到图像' }
        '06_室内建筑景观' { return '01_文本到图像' }
        '10_多图融合编辑' { return '02_图像到图像' }
        '11_第三方集成' { return '09_第三方集成' }
        '13_局部编辑去背' { return '02_图像到图像' }
        '14_控图与条件引导' { return '02_图像到图像' }
    }

    if ($Use -eq '05_电商产品') {
        if ($Text -match '精修|换背景|抠图|试衣|换装|修图') {
            return '02_图像到图像'
        }

        return '01_文本到图像'
    }

    if ($Use -eq '07_人物一致性') {
        if ($Text -match '视频|姿势|动作|跳舞|animate') {
            return '04_图像到视频'
        }

        return '01_文本到图像'
    }

    if ($Use -eq '08_视频编辑修补') {
        if ($Text -match '视频|vace|续帧') {
            return '05_视频到视频'
        }

        return '02_图像到图像'
    }

    if ($Use -eq '09_动作驱动动画') {
        if ($Text -match '说话|唱歌|rap|口型|音频|数字人|sonic') {
            return '06_音频到视频'
        }

        return '04_图像到视频'
    }

    if ($Use -eq '12_基础生成') {
        if ($Text -match '视频|t2v|i2v|animate') {
            if ($Text -match '图生视频|i2v|首尾帧|照片转视频') {
                return '04_图像到视频'
            }

            return '03_文本到视频'
        }

        if ($Model -in @('Qwen Image', 'Kontext', 'BrushNet', 'CatVTON', 'FLUX_Redux')) {
            return '02_图像到图像'
        }

        if ($Model -in @('Wan2.1', 'Wan2.2', 'LTX', 'LTX 2.3', 'MimicMotion', 'Sonic', 'VACE')) {
            return '04_图像到视频'
        }

        return '01_文本到图像'
    }

    return '99_未识别'
}

function Get-ModelCategory {
    param([string]$Text)

    if ($Text -match 'vace') { return 'VACE' }
    if ($Text -match 'wan2\.2|wan22|wan 2\.2|wanapp') { return 'Wan2.2' }
    if ($Text -match 'wan2\.1|wan21|wan 2\.1|wan2\(1\)\.1') { return 'Wan2.1' }
    if ($Text -match 'ltx23|ltx 2\.3|ltx-2\.3') { return 'LTX 2.3' }
    if ($Text -match 'ltx') { return 'LTX' }
    if ($Text -match 'kontext') { return 'Kontext' }
    if ($Text -match 'qwen') { return 'Qwen Image' }
    if ($Text -match 'sd3\.5') { return 'SD3.5' }
    if ($Text -match 'sd3') { return 'SD3' }
    if ($Text -match 'sdxl|illustrious') { return 'SDXL_Illustrious' }
    if ($Text -match 'mimicmotion') { return 'MimicMotion' }
    if ($Text -match 'gemini') { return 'Gemini' }
    if ($Text -match 'janus') { return 'Janus' }
    if ($Text -match 'sonic') { return 'Sonic' }
    if ($Text -match 'fooocus') { return 'Fooocus' }
    if ($Text -match 'ace\+\+|ace') { return 'ACE++' }
    if ($Text -match 'nunchaku') { return 'Nunchaku' }
    if ($Text -match 'hunyuan|混元') { return '混元' }
    if ($Text -match 'lumina') { return 'Lumina' }
    if ($Text -match 'brushnet') { return 'BrushNet' }
    if ($Text -match 'catvton') { return 'CatVTON' }
    if ($Text -match 'redux') { return 'FLUX_Redux' }
    if ($Text -match 'flux') { return 'FLUX' }

    return '通用_混合'
}

function Get-UniqueDestination {
    param(
        [string]$DestinationDirectory,
        [System.IO.FileInfo]$File
    )

    $baseName = $File.BaseName
    $extension = $File.Extension
    $candidate = Join-Path $DestinationDirectory ($baseName + $extension)

    if (-not (Test-Path -LiteralPath $candidate)) {
        return $candidate
    }

    $parentLeaf = Split-Path -Leaf $File.DirectoryName
    $safeLeaf = ($parentLeaf -replace '[\\/:*?"<>|]', '_') -replace '\s+', '_'
    $candidate = Join-Path $DestinationDirectory ($baseName + '__' + $safeLeaf + $extension)

    if (-not (Test-Path -LiteralPath $candidate)) {
        return $candidate
    }

    $hash = [Math]::Abs($File.FullName.GetHashCode())
    return (Join-Path $DestinationDirectory ($baseName + '__' + $hash + $extension))
}

$sourceFiles = foreach ($folder in $legacyFolders) {
    $sourcePath = Join-Path $Root $folder
    if (Test-Path -LiteralPath $sourcePath) {
        Get-ChildItem -LiteralPath $sourcePath -Recurse -File -Filter *.json -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -ne '.index.json' }
    }
}

if (-not $sourceFiles) {
    throw '未找到可整理的 JSON 工作流文件。'
}

$plan = foreach ($file in $sourceFiles) {
    $text = Get-NormalizedText -File $file
    $format = Get-FormatCategory -Text $text -Path $file.FullName
    $model = Get-ModelCategory -Text $text
    $use = Get-UseCategory -Text $text -Format $format
    if ($format -eq '99_未识别') {
        $format = Resolve-FallbackFormat -Text $text -Use $use -Model $model
    }
    $destinationDirectory = Join-Path $Root (Join-Path $format (Join-Path $use $model))
    $destinationFile = Get-UniqueDestination -DestinationDirectory $destinationDirectory -File $file

    [pscustomobject]@{
        Source = $file.FullName
        RelativeSource = $file.FullName.Substring($Root.Length + 1)
        Format = $format
        Use = $use
        Model = $model
        Destination = $destinationFile
    }
}

if (-not $Execute) {
    Write-Output '=== PREVIEW ==='
    $plan | Select-Object -First $PreviewCount RelativeSource, Format, Use, Model, Destination | Format-Table -Wrap -AutoSize
    Write-Output '=== SUMMARY ==='
    $plan | Group-Object Format, Use, Model | Sort-Object Count -Descending | Select-Object -First 30 Count, Name | Format-Table -Wrap -AutoSize
    return
}

$createdDirectories = New-Object System.Collections.Generic.HashSet[string]
$moved = 0

foreach ($item in $plan) {
    $destinationDirectory = Split-Path -Parent $item.Destination
    if ($createdDirectories.Add($destinationDirectory)) {
        Ensure-Directory -Path $destinationDirectory
    }

    Move-Item -LiteralPath $item.Source -Destination $item.Destination -Force
    $moved++
}

$archiveRoot = Join-Path $Root $archiveRootName
Ensure-Directory -Path $archiveRoot

foreach ($folder in $legacyFolders) {
    $sourcePath = Join-Path $Root $folder
    $destinationPath = Join-Path $archiveRoot $folder

    if (-not (Test-Path -LiteralPath $sourcePath)) {
        continue
    }

    if (Test-Path -LiteralPath $destinationPath) {
        Remove-Item -LiteralPath $destinationPath -Recurse -Force
    }

    Move-Item -LiteralPath $sourcePath -Destination $destinationPath
}

Write-Output '=== EXECUTED ==='
Write-Output ('MOVED_JSON=' + $moved)
Write-Output ('ARCHIVE_ROOT=' + $archiveRoot)
Write-Output '=== FORMAT COUNTS ==='
$plan | Group-Object Format | Sort-Object Name | Select-Object Name, Count | Format-Table -AutoSize