# ComfyUI 测试框架
# 离线模式：只做静态校验；在线模式：增加 object_info 与执行冒烟测试
from __future__ import annotations

from pathlib import Path

# ---- 路径常量 ----
PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = PROJECT_ROOT.parents[1]  # d:\ComfyUI-aki-v3

COMFYUI_ROOT = WORKSPACE_ROOT / "ComfyUI"
MODELS_ROOT = COMFYUI_ROOT / "models"
CUSTOM_NODES_ROOT = COMFYUI_ROOT / "custom_nodes"
USER_WORKFLOWS_ROOT = COMFYUI_ROOT / "user" / "default" / "workflows"
SKILL_WORKFLOWS_ROOT = WORKSPACE_ROOT / "agent-skills" / "comfyui" / "workflows"
IMPORTED_WORKFLOWS_ROOT = SKILL_WORKFLOWS_ROOT / "imported"
API_WORKFLOWS_ROOT = SKILL_WORKFLOWS_ROOT / "api"
REGISTRY_PATH = WORKSPACE_ROOT / "agent-skills" / "comfyui" / "registry.json"

RUNTIME_DIR = PROJECT_ROOT / "runtime"
REPORTS_DIR = RUNTIME_DIR / "reports"

SERVER_URL = "http://127.0.0.1:8188"

# ---- 本次测试重点关注 ----
# 2026-05-16 新增/变更的资源
NEW_CHECKPOINTS = [
    "dessertModels_gelato.safetensors",
    "smoothMixWan2214BI2V_i2vV20High.safetensors",
    "excelaxl_20251018b.safetensors",
    "excelaxl_20251018c.safetensors",
    "cogvideox5bI2V_v10.safetensors",
    "hunyuanVideo15_720pI2VFP16.safetensors",
    "hunyuanVideo15_720pT2VFP16.safetensors",
    "nexblendIvory_v10.safetensors",
]

NEW_DIFFUSION_MODELS = [
    "wan21I2VLightx2vStep_v10.safetensors",
]

NEW_LORAS = [
    "BounceHighWan2_2.safetensors",
    "lips-bj_high_noise.safetensors",
    "WAN-2.2-I2V-POV-Body-Cumshot-Pullout-HIGH-v1.safetensors",
    "WAN-2.2-I2V-POV-Body-Cumshot-Pullout-LOW-v1.safetensors",
    "Wan22_Cum_high_noise_1.V1.safetensors",
    "Wan22_Cum_low_noise_1.V1.safetensors",
    "Wan22_CumV2_High.safetensors",
    "Wan22_CumV2_Low.safetensors",
    "wan22-f4c3spl4sh-100epoc-high-k3nk.safetensors",
    "wan22-f4c3spl4sh-154epoc-low-k3nk.safetensors",
    "23High noise-Cumshot Aesthetics.safetensors",
    "56Low noise-Cumshot Aesthetics.safetensors",
    "AI Girl Fictional Women Series19 high_noise.safetensors",
]

NEW_WORKFLOWS = [
    IMPORTED_WORKFLOWS_ROOT / "mmaudio-kiss-sfx-autocaption" / "MM Audio AUTO CAPTION 2.5.json",
    IMPORTED_WORKFLOWS_ROOT / "mmaudio-batch" / "MMAudioBatchPSv1.json",
    IMPORTED_WORKFLOWS_ROOT / "nsfw-mmaudio-rife" / "MMAudio.json",
]

# MMAudio 标准 fp16 四件套
MMAUDIO_REQUIRED_MODELS = [
    "mmaudio_large_44k_v2_fp16.safetensors",
    "mmaudio_vae_44k_fp16.safetensors",
    "mmaudio_synchformer_fp16.safetensors",
    "apple_DFN5B-CLIP-ViT-H-14-384_fp16.safetensors",
]

# 两个导入工作流实际引用的 NSFW 特化 MMAudio 主模型；没有它时可以手动切换为标准主模型。
MMAUDIO_OPTIONAL_MODELS = [
    "mmaudio_large_44k_nsfw_gold_8.5k_final_fp16.safetensors",
]

# ComfyUI-VFI 的 RIFEInterpolation 节点实际使用 flownet.pkl，而不是 ComfyUI-Frame-Interpolation 的 rife49.pth。
RIFE_VFI_REQUIRED_MODELS = [
    "flownet.pkl",
]

# 测试用 API 工作流（优先测的）
PRIORITY_API_WORKFLOWS = [
    "wan22_i2v_dasiwa_six_loras_4080_safe.json",
    "wan22_i2v_dasiwa_six_loras_optimized.json",
    "wan22_i2v_dasiwa_six_loras_4080_long_81f.json",
    "sdxl_copax_timeless_t2i_safe_benchmark.json",
    "sdxl_copax_timeless_lora_safe_probe.json",
    "sdxl_animagine_anime_dancer_reference.json",
]

FOCUS_WORKFLOWS = NEW_WORKFLOWS + [API_WORKFLOWS_ROOT / name for name in PRIORITY_API_WORKFLOWS]
