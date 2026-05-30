"""
直接读取模型权重检查 NaN/Inf（CPU，不占显存，不停 ComfyUI）
若权重含 NaN/Inf -> 文件数值损坏（需重下）
若权重正常       -> 运行时 torch/ops 的 fp8 计算问题
"""
import sys, io
sys.stdout = io.TextIOWrapper(open(r"D:\ComfyUI-aki-v3\agent-projects\wan22-i2v-test\nan_result.txt", "wb"), encoding="utf-8")
import torch
from safetensors import safe_open

files = {
    "high_unet_fp8": r"F:\ComfyUI-aki-v3\ComfyUI\models\diffusion_models\wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    "low_unet_fp8":  r"F:\ComfyUI-aki-v3\ComfyUI\models\diffusion_models\wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
    "umt5_fp8":      r"F:\ComfyUI-aki-v3\ComfyUI\models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    "vae":           r"F:\ComfyUI-aki-v3\ComfyUI\models\vae\wan_2.1_vae.safetensors",
}

for tag, path in files.items():
    print(f"\n===== {tag} =====")
    try:
        with safe_open(path, framework="pt", device="cpu") as f:
            keys = list(f.keys())
            print(f"张量总数: {len(keys)}")
            # 采样检查：前若干个 + 含 scale 的 + 均匀抽样
            sample_keys = keys[:5]
            scale_keys = [k for k in keys if "scale" in k.lower()][:5]
            step = max(1, len(keys)//15)
            spread_keys = keys[::step][:15]
            check = list(dict.fromkeys(sample_keys + scale_keys + spread_keys))

            bad = 0
            for k in check:
                t = f.get_tensor(k)
                tf = t.float()
                n_nan = torch.isnan(tf).sum().item()
                n_inf = torch.isinf(tf).sum().item()
                mn = tf.min().item() if tf.numel() else 0
                mx = tf.max().item() if tf.numel() else 0
                flag = ""
                if n_nan or n_inf:
                    flag = f"  <<< NaN={n_nan} Inf={n_inf}"
                    bad += 1
                # 只打印有问题的 + 少量正常样本
                if flag or k in sample_keys[:2] or k in scale_keys[:1]:
                    print(f"  {k[:55]:55s} dtype={str(t.dtype):18s} min={mn:.4g} max={mx:.4g}{flag}")
            print(f"  >>> 抽查 {len(check)} 个张量, 含 NaN/Inf 的: {bad}")
    except Exception as e:
        print(f"  读取失败: {e}")
