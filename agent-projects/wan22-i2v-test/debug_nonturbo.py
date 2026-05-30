"""
测试 A：fp8 双模型，官方"非蒸馏"标准配置
- ModelSamplingSD3(shift=5) + cfg=3.5 + euler/simple + 20步
- high: 0->10, low: 10->20, 不使用 LoRA
- length 降到 33 帧加速
这是 ComfyUI 官方模板 enable_4steps_lora=false 的精确配置。
"""
import requests, random, uuid

SERVER = "http://127.0.0.1:8188"
IMAGE_PATH = r"D:\文件快传\1713279344578.jpg"
RUN_ID = uuid.uuid4().hex[:8]
CLIENT_ID = f"agent:claude|workflow:wan22_i2v_nonturbo|run:{RUN_ID}"
PROMPT_TEXT = "镜头缓慢推进，自然流畅的运动"
SEED = random.randint(0, 2**31)

with open(IMAGE_PATH, "rb") as f:
    r = requests.post(f"{SERVER}/upload/image",
                      files={"image": ("1713279344578.jpg", f, "image/jpeg")})
    r.raise_for_status()
    filename = r.json()["name"]
    print(f"[1] 图片上传: {filename}")

prompt = {
    "200": {"class_type": "LoadImage", "inputs": {"image": filename, "upload": "image"}},
    "84":  {"class_type": "CLIPLoader",
            "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
    "90":  {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
    "95":  {"class_type": "UNETLoader",
            "inputs": {"unet_name": "wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
    "96":  {"class_type": "UNETLoader",
            "inputs": {"unet_name": "wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "weight_dtype": "default"}},
    # 直接 ModelSamplingSD3，不接 LoRA
    "104": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["95", 0], "shift": 5.0}},
    "103": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["96", 0], "shift": 5.0}},
    "93":  {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": PROMPT_TEXT}},
    "89":  {"class_type": "CLIPTextEncode",
            "inputs": {"clip": ["84", 0],
                       "text": "色调艳丽，过曝，静态，细节模糊不清，最差质量，低质量，静止不动的画面"}},
    "98":  {"class_type": "WanImageToVideo",
            "inputs": {"positive": ["93", 0], "negative": ["89", 0], "vae": ["90", 0],
                       "start_image": ["200", 0], "width": 640, "height": 640, "length": 33, "batch_size": 1}},
    # high noise: step 0->10
    "86":  {"class_type": "KSamplerAdvanced",
            "inputs": {"model": ["104", 0], "positive": ["98", 0], "negative": ["98", 1], "latent_image": ["98", 2],
                       "add_noise": "enable", "noise_seed": SEED, "steps": 20, "cfg": 3.5,
                       "sampler_name": "euler", "scheduler": "simple",
                       "start_at_step": 0, "end_at_step": 10, "return_with_leftover_noise": "enable"}},
    # low noise: step 10->20
    "85":  {"class_type": "KSamplerAdvanced",
            "inputs": {"model": ["103", 0], "positive": ["98", 0], "negative": ["98", 1], "latent_image": ["86", 0],
                       "add_noise": "disable", "noise_seed": SEED, "steps": 20, "cfg": 3.5,
                       "sampler_name": "euler", "scheduler": "simple",
                       "start_at_step": 10, "end_at_step": 20, "return_with_leftover_noise": "disable"}},
    "87":  {"class_type": "VAEDecode", "inputs": {"samples": ["85", 0], "vae": ["90", 0]}},
    "117": {"class_type": "CreateVideo", "inputs": {"images": ["87", 0], "fps": 16}},
    "120": {"class_type": "SaveVideo",
            "inputs": {"video": ["117", 0], "filename_prefix": "debug_nonturbo", "format": "auto", "codec": "auto"}},
}

payload = {"client_id": CLIENT_ID, "prompt": prompt,
           "extra_data": {"agent": "claude", "workflow_name": "wan22_i2v_nonturbo",
                          "source": "agent-projects/wan22-i2v-test",
                          "notes": f"fp8 non-turbo, cfg3.5, 20steps, ModelSamplingSD3, no LoRA, 33frames, seed={SEED}"}}

r = requests.post(f"{SERVER}/prompt", json=payload)
result = r.json()
print(f"[2] 提交: {r.status_code}, node_errors={result.get('node_errors')}")
if "prompt_id" in result:
    print(f"[OK] prompt_id={result['prompt_id']}, seed={SEED}, 前缀=debug_nonturbo")
