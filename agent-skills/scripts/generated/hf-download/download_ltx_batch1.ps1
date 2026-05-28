# LTX 模型批量下载脚本 — 逐个文件下载，正确命名，放到对应 ComfyUI 目录
$aria2 = "D:\ComfyUI-aki-v3\agent-projects\civitai-downloader\runtime\tools\aria2\aria2c.exe"
$M = "D:\ComfyUI-aki-v3\ComfyUI\models"

# 下载函数：repo, filePath(含repo内子目录), targetDir, targetName
function Dl($repo, $srcPath, $dstDir, $dstName) {
    $url = "https://hf-mirror.com/$repo/resolve/main/$srcPath"
    $dir = "$M\$dstDir"
    New-Item -Force -Type Directory $dir | Out-Null
    Write-Host "DL: $dstDir/$dstName  <-  $repo/$srcPath"
    & $aria2 -x 1 -s 1 -c --retry-wait 10 -m 5 --timeout 120 --out "$dstName" -d "$dir" "$url"
    if ($LASTEXITCODE -ne 0) { Write-Host "  FAILED!" -ForegroundColor Red }
}

# ===== VAE (3 files) =====
Dl "Kijai/LTX2.3_comfy" "vae/LTX23_video_vae_bf16.safetensors" "vae" "LTX23_video_vae_bf16.safetensors"
Dl "Kijai/LTX2.3_comfy" "vae/LTX23_audio_vae_bf16.safetensors" "vae" "LTX23_audio_vae_bf16.safetensors"
Dl "Kijai/LTX2.3_comfy" "vae/taeltx2_3.safetensors" "vae" "taeltx2_3.safetensors"

# ===== Text Encoder (1 file) =====
Dl "Kijai/LTX2.3_comfy" "text_encoders/ltx-2.3_text_projection_bf16.safetensors" "text_encoders" "ltx-2.3_text_projection_bf16.safetensors"

# ===== MelBandRoformer (1 file) =====
Dl "Kijai/MelBandRoformer_comfy" "MelBandRoformer_fp32.safetensors" "audio_encoders" "MelBandRoformer_fp32.safetensors"

Write-Host "`n=== Small files batch complete ==="
