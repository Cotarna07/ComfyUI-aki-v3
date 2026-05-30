import json, struct, os

base = r"F:\ComfyUI-aki-v3\ComfyUI\models"
files = [
    base + r"\diffusion_models\wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    base + r"\diffusion_models\wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
    base + r"\diffusion_models\wan2.2_i2v_high_noise_14B_fp16.safetensors",
    base + r"\diffusion_models\wan2.2_i2v_low_noise_14B_fp16.safetensors",
    base + r"\loras\wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
    base + r"\loras\wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
    base + r"\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    base + r"\vae\wan_2.1_vae.safetensors",
]

for f in files:
    name = os.path.basename(f)
    if not os.path.exists(f):
        print(f"[MISS] {name}")
        continue
    fsize = os.path.getsize(f)
    with open(f, "rb") as fh:
        header_len = struct.unpack("<Q", fh.read(8))[0]
        header_bytes = fh.read(header_len)
    try:
        header = json.loads(header_bytes)
    except Exception as e:
        print(f"[BAD HEADER] {name}: {e}")
        continue
    # 计算 header 声明的最大数据偏移
    max_end = 0
    n_tensors = 0
    for k, v in header.items():
        if k == "__metadata__":
            continue
        n_tensors += 1
        if "data_offsets" in v:
            max_end = max(max_end, v["data_offsets"][1])
    expected = 8 + header_len + max_end
    status = "OK" if expected == fsize else "TRUNCATED/MISMATCH"
    print(f"[{status}] {name}")
    print(f"    实际大小={fsize:,}  期望大小={expected:,}  差={fsize-expected:,}  张量数={n_tensors}")
