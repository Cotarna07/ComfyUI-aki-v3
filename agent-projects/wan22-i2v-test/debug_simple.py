"""
简化测试：单模型 + 不使用 ModelSamplingSD3，排查 cascade 是否是问题根源
"""
import requests, json, random, uuid

SERVER = "http://127.0.0.1:8188"
IMAGE_PATH = r"D:\文件快传\1713279344578.jpg"
RUN_ID = uuid.uuid4().hex[:8]
CLIENT_ID = f"agent:claude|workflow:wan22_i2v_debug|run:{RUN_ID}"
PROMPT_TEXT = "镜头缓慢推进，自然流畅的运动"
SEED = random.randint(0, 2**31)

# Upload image
with open(IMAGE_PATH, "rb") as f:
    r = requests.post(f"{SERVER}/upload/image",
                      files={"image": ("1713279344578.jpg", f, "image/jpeg")})
    r.raise_for_status()
    filename = r.json()["name"]
    print(f"[1] 图片上传: {filename}")

# 简化 prompt：只用 low_noise 模型，单 KSampler，不用 LoRA，不用 ModelSamplingSD3
prompt = {
    "200": {"class_type": "LoadImage",
            "inputs": {"image": filename, "upload": "image"}},
    "84":  {"class_type": "CLIPLoader",
            "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                       "type": "wan", "device": "default"}},
    "90":  {"class_type": "VAELoader",
            "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
    # 只用 low_noise 模型，单个 UNETLoader
    "95":  {"class_type": "UNETLoader",
            "inputs": {"unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
                       "weight_dtype": "default"}},
    "93":  {"class_type": "CLIPTextEncode",
            "inputs": {"clip": ["84", 0], "text": PROMPT_TEXT}},
    "89":  {"class_type": "CLIPTextEncode",
            "inputs": {"clip": ["84", 0],
                       "text": "色调艳丽，过曝，静态，细节模糊不清，字幕，最差质量，低质量，静止不动的画面"}},
    "98":  {"class_type": "WanImageToVideo",
            "inputs": {"positive": ["93", 0], "negative": ["89", 0],
                       "vae": ["90", 0], "start_image": ["200", 0],
                       "width": 640, "height": 640, "length": 81, "batch_size": 1}},
    # 单个 KSampler，20 步，不用 cascade，不用 ModelSamplingSD3
    "86":  {"class_type": "KSamplerAdvanced",
            "inputs": {"model": ["95", 0],
                       "positive": ["98", 0], "negative": ["98", 1],
                       "latent_image": ["98", 2],
                       "add_noise": "enable", "noise_seed": SEED,
                       "steps": 20, "cfg": 1.0,
                       "sampler_name": "euler", "scheduler": "simple",
                       "start_at_step": 0, "end_at_step": 20,
                       "return_with_leftover_noise": "disable"}},
    "87":  {"class_type": "VAEDecode",
            "inputs": {"samples": ["86", 0], "vae": ["90", 0]}},
    "117": {"class_type": "CreateVideo",
            "inputs": {"images": ["87", 0], "fps": 16}},
    "120": {"class_type": "SaveVideo",
            "inputs": {"video": ["117", 0],
                       "filename_prefix": "debug_simple",
                       "format": "auto", "codec": "auto"}},
}

payload = {
    "client_id": CLIENT_ID,
    "prompt": prompt,
    "extra_data": {
        "agent": "claude",
        "workflow_name": "wan22_i2v_debug_simple",
        "source": "agent-projects/wan22-i2v-test",
        "notes": f"debug: single model, no cascade, no LoRA, seed={SEED}"
    }
}

r = requests.post(f"{SERVER}/prompt", json=payload)
result = r.json()
print(f"[2] 提交: {r.status_code}, node_errors={result.get('node_errors')}")
if "prompt_id" in result:
    print(f"[OK] prompt_id={result['prompt_id']}, seed={SEED}")
    print("     输出文件前缀: debug_simple")
