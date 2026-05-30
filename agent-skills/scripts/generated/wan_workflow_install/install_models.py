from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

from huggingface_hub import hf_hub_download


ROOT = Path("D:/ComfyUI-aki-v3")
COMFY = ROOT / "ComfyUI"
MODELS = COMFY / "models"
REPORT = ROOT / "agent-skills/comfyui/runtime/wan_workflow_install/model_install_report.json"


def log(message: str) -> None:
    print(time.strftime("%H:%M:%S"), message, flush=True)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def is_within(path: Path, base: Path) -> bool:
    resolved = path.resolve()
    base_resolved = base.resolve()
    return resolved == base_resolved or base_resolved in resolved.parents


def link_or_copy(source: Path, dest: Path, note: str) -> dict[str, str]:
    ensure_parent(dest)
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if not is_within(dest, MODELS):
        raise ValueError(f"Refusing to write outside model directory: {dest}")
    if dest.exists():
        return {"target": str(dest), "source": str(source), "status": "exists", "note": note}
    try:
        os.link(source, dest)
        status = "hardlinked"
    except OSError:
        shutil.copy2(source, dest)
        status = "copied"
    return {"target": str(dest), "source": str(source), "status": status, "note": note}


def download(repo: str, filename: str, local_dir: Path, dest: Path | None = None, note: str = "") -> dict[str, str]:
    if dest is None:
        dest = local_dir / filename
    ensure_parent(dest)
    if dest.exists() and dest.stat().st_size > 0:
        log(f"skip existing {dest.relative_to(MODELS)}")
        return {"target": str(dest), "repo": repo, "filename": filename, "status": "exists", "note": note}

    log(f"download {repo} :: {filename}")
    path = Path(
        hf_hub_download(
            repo_id=repo,
            filename=filename,
            repo_type="model",
            local_dir=str(local_dir),
        )
    )
    if path.resolve() == dest.resolve():
        return {"target": str(dest), "repo": repo, "filename": filename, "status": "downloaded", "note": note}
    record = link_or_copy(path, dest, note)
    record.update({"repo": repo, "filename": filename})
    return record


def main() -> int:
    for folder in [
        "diffusion_models",
        "text_encoders",
        "loras",
        "loras/WAN",
        "mmaudio",
        "upscale_models",
        "frame_interpolation",
        "SEEDVR2",
        "interpolation/gimm-vfi",
    ]:
        (MODELS / folder).mkdir(parents=True, exist_ok=True)

    records: list[dict[str, str]] = []
    alias = records.append

    alias(
        link_or_copy(
            MODELS / "diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
            MODELS / "diffusion_models/wan2.2_i2v_high_noise_14B_fp16.safetensors",
            "workflow expects fp16 name; local 16GB test uses existing fp8_scaled weight",
        )
    )
    alias(
        link_or_copy(
            MODELS / "diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
            MODELS / "diffusion_models/wan2.2_i2v_low_noise_14B_fp16.safetensors",
            "workflow expects fp16 name; local 16GB test uses existing fp8_scaled weight",
        )
    )
    alias(
        link_or_copy(
            MODELS / "diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
            MODELS / "diffusion_models/wan2.2_t2v_high_noise_14B_fp16.safetensors",
            "muted T2V branch alias for local testing",
        )
    )
    alias(
        link_or_copy(
            MODELS / "diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
            MODELS / "diffusion_models/wan2.2_t2v_low_noise_14B_fp16.safetensors",
            "muted T2V branch alias for local testing",
        )
    )
    alias(
        link_or_copy(
            MODELS / "text_encoders/umt5-xxl-enc-bf16.safetensors",
            MODELS / "text_encoders/umt5_xxl_fp16.safetensors",
            "workflow expects fp16 name; using existing UMT5 XXL bf16 encoder for local testing",
        )
    )
    alias(
        link_or_copy(
            MODELS / "mmaudio/mmaudio_large_44k_nsfw_gold_8.5k_final_fp16.safetensors",
            MODELS / "mmaudio/mmaudio_nsfw_large_44k_v2_fp16.safetensors",
            "workflow expects nsfw v2 filename; using existing local nsfw fp16 MMAudio model",
        )
    )
    alias(
        link_or_copy(
            MODELS / "loras/SVI_v2_PRO_Wan2.2-I2V-A14B_HIGH_lora_rank_128_fp16.safetensors",
            MODELS / "loras/SVI_Wan2.2-I2V-A14B_high_noise_lora_v2.0_pro.safetensors",
            "muted SVI branch alias",
        )
    )
    alias(
        link_or_copy(
            MODELS / "loras/SVI_v2_PRO_Wan2.2-I2V-A14B_LOW_lora_rank_128_fp16.safetensors",
            MODELS / "loras/SVI_Wan2.2-I2V-A14B_low_noise_lora_v2.0_pro.safetensors",
            "muted SVI branch alias",
        )
    )

    downloads = [
        (
            "Kijai/WanVideo_comfy",
            "Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank256_bf16.safetensors",
            MODELS / "loras",
            MODELS / "loras/lightx2v_I2V_14B_480p_cfg_step_distill_rank256_bf16.safetensors",
            "WanVideo I2V LightX2V LoRA",
        ),
        (
            "Kijai/WanVideo_comfy",
            "Lightx2v/lightx2v_14B_T2V_cfg_step_distill_lora_adaptive_rank_quantile_0.15_bf16.safetensors",
            MODELS / "loras",
            MODELS / "loras/lightx2v_14B_T2V_cfg_step_distill_lora_adaptive_rank_quantile_0.15_bf16.safetensors",
            "WanVideo T2V LightX2V LoRA",
        ),
        (
            "Kijai/WanVideo_comfy",
            "LoRAs/Wan22_Lightx2v/Wan_2_2_I2V_A14B_HIGH_lightx2v_4step_lora_v1030_rank_64_bf16.safetensors",
            MODELS / "loras",
            MODELS / "loras/Wan_2_2_I2V_A14B_HIGH_lightx2v_4step_lora_v1030_rank_64_bf16.safetensors",
            "Wan 2.2 I2V high-noise LightX2V LoRA",
        ),
        (
            "profpeng/gagging",
            "wan22-G4GG1NGv6-11epoc-high-i2v-k3nk.safetensors",
            MODELS / "loras",
            None,
            "K3NK high-noise LoRA used by active I2V workflow",
        ),
        (
            "profpeng/gagging",
            "wan22-G4GG1NGv6-11epoc-low-i2v-k3nk.safetensors",
            MODELS / "loras",
            None,
            "K3NK low-noise LoRA used by active I2V workflow",
        ),
        (
            "Kutches/2BasedV3",
            "wan22-gu4d4lup3-23epoc-low-k3nk.safetensors",
            MODELS / "loras",
            None,
            "K3NK low-noise LoRA used by active T2V workflow",
        ),
        (
            "pp901/b29",
            "go/206145/2I682EUUE6/wan22-5uck1t-v2-2epoc-high-k3nk.safetensors",
            MODELS / "loras",
            MODELS / "loras/wan22-5uck1t-v2-2epoc-high-k3nk.safetensors",
            "K3NK high-noise LoRA used by active T2V workflow",
        ),
        (
            "pp901/b29",
            "go/206146/I2XBAZCLEY/wan22-5uck1t-v2-2epoc-low-k3nk.safetensors",
            MODELS / "loras",
            MODELS / "loras/wan22-5uck1t-v2-1epoc-low-k3nk.safetensors",
            "closest public low-noise file; workflow expects 1epoc filename",
        ),
        (
            "sudolink/diffusion_models",
            "DasiwaWAN22I2V14BLightspeed_synthseductionHighV9.safetensors",
            MODELS / "diffusion_models",
            None,
            "WAN2.2_LOOP high-noise diffusion model",
        ),
        (
            "sudolink/diffusion_models",
            "DasiwaWAN22I2V14BLightspeed_synthseductionLowV9.safetensors",
            MODELS / "diffusion_models",
            None,
            "WAN2.2_LOOP low-noise diffusion model",
        ),
        (
            "darksidewalker/DaSiWa-WAN2.2-I2V",
            "Distilled/GGUF/v08/DasiwaWAN22I2V14BTastysinV8_q4High.gguf",
            MODELS / "diffusion_models",
            MODELS / "diffusion_models/DasiwaWAN22I2V14BTastysinV8_q4High.gguf",
            "native upscaler GGUF high-noise model",
        ),
        (
            "darksidewalker/DaSiWa-WAN2.2-I2V",
            "Distilled/GGUF/v08/DasiwaWAN22I2V14BTastysinV8_q4Low.gguf",
            MODELS / "diffusion_models",
            MODELS / "diffusion_models/DasiwaWAN22I2V14BTastysinV8_q4Low.gguf",
            "native upscaler GGUF low-noise model",
        ),
        (
            "city96/Wan2.1-I2V-14B-720P-gguf",
            "wan2.1-i2v-14b-720p-Q4_K_S.gguf",
            MODELS / "diffusion_models",
            None,
            "Wan 2.1 loop GGUF base model",
        ),
        (
            "city96/umt5-xxl-encoder-gguf",
            "umt5-xxl-encoder-Q4_K_S.gguf",
            MODELS / "text_encoders",
            None,
            "GGUF text encoder for UmeAiRT WAN settings",
        ),
        (
            "QuantStack/Wan2.2-I2V-A14B-GGUF",
            "HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_S.gguf",
            MODELS / "diffusion_models",
            MODELS / "diffusion_models/Wan2.2-I2V-HighNoise-14B-Q4_K_S.gguf",
            "manual Img2Video high-noise GGUF alias",
        ),
        (
            "QuantStack/Wan2.2-I2V-A14B-GGUF",
            "LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_S.gguf",
            MODELS / "diffusion_models",
            MODELS / "diffusion_models/Wan2.2-I2V-LowNoise-14B-Q4_K_S.gguf",
            "manual Img2Video low-noise GGUF alias",
        ),
        (
            "UmeAiRT/ComfyUI-Auto-Installer-Assets",
            "models/frame_interpolation/rife_v4.26.safetensors",
            COMFY,
            MODELS / "frame_interpolation/rife_v4.26.safetensors",
            "UmeAiRT frame interpolation model",
        ),
        (
            "UmeAiRT/ComfyUI-Auto-Installer-Assets",
            "models/upscale_models/4x_NMKD-Siax_200k.pth",
            COMFY,
            MODELS / "upscale_models/4x_NMKD-Siax_200k.pth",
            "UmeAiRT classic upscale model",
        ),
        (
            "UmeAiRT/ComfyUI-Auto-Installer-Assets",
            "models/upscale_models/4x-AnimeSharp.pth",
            COMFY,
            MODELS / "upscale_models/4x-AnimeSharp.pth",
            "native upscaler classic model",
        ),
        (
            "numz/SeedVR2_comfyUI",
            "seedvr2_ema_3b_fp8_e4m3fn.safetensors",
            MODELS / "SEEDVR2",
            None,
            "SeedVR2 3B fp8 model for local 16GB testing",
        ),
        (
            "Kijai/GIMM-VFI_safetensors",
            "gimmvfi_f_arb_lpips_fp32.safetensors",
            MODELS / "interpolation/gimm-vfi",
            None,
            "GIMM-VFI model",
        ),
        (
            "Kijai/GIMM-VFI_safetensors",
            "flowformer_sintel_fp32.safetensors",
            MODELS / "interpolation/gimm-vfi",
            None,
            "GIMM-VFI flow estimator required by f model",
        ),
    ]

    failures = []
    for repo, filename, local_dir, dest, note in downloads:
        try:
            records.append(download(repo, filename, local_dir, dest, note))
        except Exception as exc:  # continue so one gated or moved file does not stop the batch
            log(f"FAILED {repo} :: {filename}: {exc}")
            failures.append({"repo": repo, "filename": filename, "error": repr(exc), "note": note})

    ensure_parent(REPORT)
    REPORT.write_text(
        json.dumps({"records": records, "failures": failures}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    log(f"wrote report {REPORT}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
