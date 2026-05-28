# LTX 全部模型分批下载 — 每文件单独 aria2c 调用，正确命名
$aria2 = "D:\ComfyUI-aki-v3\agent-projects\civitai-downloader\runtime\tools\aria2\aria2c.exe"
$M = "D:\ComfyUI-aki-v3\ComfyUI\models"

function One($repo, $srcPath, $dstDir, $dstName) {
    $url = "https://hf-mirror.com/$repo/resolve/main/$srcPath"
    $dir = "$M\$dstDir"
    $target = "$dir\$dstName"
    New-Item -Force -Type Directory $dir | Out-Null
    if (Test-Path $target) {
        $sz = [math]::Round((Get-Item $target).Length / 1MB, 0)
        Write-Host "SKIP (exists, ${sz}MB): $dstDir/$dstName"
        return
    }
    Write-Host "DL: $dstDir/$dstName"
    Write-Host "    <- $repo/$srcPath"
    & $aria2 -x 1 -s 1 -c --retry-wait 10 -m 10 --timeout 180 --file-allocation=none --out "$dstName" -d "$dir" "$url" 2>&1 | Select-String -Pattern 'DL:|ERR|complete|FAIL' | ForEach-Object { Write-Host "    $_" }
    if ($LASTEXITCODE -ne 0) { Write-Host "  ** FAILED **" -ForegroundColor Red }
}

# ========== BATCH 1: VAE + TextEncoder + Audio (5 files, ~3.8GB) ==========
Write-Host "`n===== BATCH 1: VAE/TextEncoder/Audio ====="
One "Kijai/LTX2.3_comfy" "vae/LTX23_video_vae_bf16.safetensors" "vae" "LTX23_video_vae_bf16.safetensors"
One "Kijai/LTX2.3_comfy" "vae/LTX23_audio_vae_bf16.safetensors" "vae" "LTX23_audio_vae_bf16.safetensors"
One "Kijai/LTX2.3_comfy" "vae/taeltx2_3.safetensors" "vae" "taeltx2_3.safetensors"
One "Kijai/LTX2.3_comfy" "text_encoders/ltx-2.3_text_projection_bf16.safetensors" "text_encoders" "ltx-2.3_text_projection_bf16.safetensors"
One "Kijai/MelBandRoformer_comfy" "MelBandRoformer_fp32.safetensors" "audio_encoders" "MelBandRoformer_fp32.safetensors"

Write-Host "`n===== BATCH 1 DONE ====="
