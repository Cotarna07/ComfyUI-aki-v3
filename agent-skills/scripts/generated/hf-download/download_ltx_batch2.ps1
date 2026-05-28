# LTX Batch 2: Upscale + LoRAs + BiRefNet
$aria2 = "D:\ComfyUI-aki-v3\agent-projects\civitai-downloader\runtime\tools\aria2\aria2c.exe"
$M = "D:\ComfyUI-aki-v3\ComfyUI\models"

function One($repo, $srcPath, $dstDir, $dstName) {
    $url = "https://hf-mirror.com/$repo/resolve/main/$srcPath"
    $dir = "$M\$dstDir"
    $target = "$dir\$dstName"
    New-Item -Force -Type Directory $dir | Out-Null
    if (Test-Path $target) { Write-Host "SKIP: $dstDir/$dstName"; return }
    Write-Host "DL: $dstDir/$dstName"
    & $aria2 -x 1 -s 1 -c --retry-wait 10 -m 10 --timeout 180 --file-allocation=none --out "$dstName" -d "$dir" "$url" 2>&1 | Select-String -Pattern 'complete|FAIL|ERR' | ForEach-Object { Write-Host "    $_" }
}

# ===== Upscale =====
One "Lightricks/LTX-2.3" "ltx-2.3-spatial-upscaler-x2-1.1.safetensors" "latent_upscale_models" "ltx-2.3-spatial-upscaler-x2-1.1.safetensors"

# ===== LoRAs (from Kijai/LTX2.3_comfy) =====
One "Kijai/LTX2.3_comfy" "loras/LTX-2.3-OmniNFT-RL-Lora_bf16.safetensors" "loras" "LTX-2.3-OmniNFT-RL-Lora_bf16.safetensors"
One "Kijai/LTX2.3_comfy" "loras/ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors" "loras" "ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors"
One "Kijai/LTX2.3_comfy" "loras/ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors" "loras" "ltx-2.3-22b-distilled-1.1_lora-dynamic_fro09_avg_rank_111_bf16.safetensors"

# ===== LoRA (from Lightricks) =====
One "Lightricks/LTX-2.3" "ltx-2.3-22b-distilled-lora-384-1.1.safetensors" "loras" "ltx-2.3-22b-distilled-lora-384-1.1.safetensors"

# ===== BiRefNet =====
$birefDir = "$M\BiRefNet\pth"; New-Item -Force -Type Directory $birefDir | Out-Null
# Download BiRefNet model.safetensors to BiRefNet/pth/ location
One "ZhengPeng7/BiRefNet" "model.safetensors" "BiRefNet\pth" "BiRefNet-general-epoch_244.safetensors"

# ===== RMBG-2.0 =====
$rmbgDir = "$M\BiRefNet\RMBG-2.0"; New-Item -Force -Type Directory $rmbgDir | Out-Null
One "briaai/RMBG-2.0" "model.safetensors" "BiRefNet\RMBG-2.0" "model.safetensors"
One "briaai/RMBG-2.0" "BiRefNet_config.py" "BiRefNet\RMBG-2.0" "BiRefNet_config.py"
One "briaai/RMBG-2.0" "birefnet.py" "BiRefNet\RMBG-2.0" "birefnet.py"

Write-Host "`n===== BATCH 2 DONE ====="
