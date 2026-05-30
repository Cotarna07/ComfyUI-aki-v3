"""
GGUF Q8 对照测试：用 Q8 量化模型替代 fp8（走 ComfyUI-GGUF 代码路径，绕过 fp8 原生运算）
turbo 配置：lightx2v 4steps LoRA + ModelSamplingSD3 + cfg=1 + 4步
若正常 -> 确认 fp8 问题；若噪点 -> 更深环境问题
"""
import requests, random, uuid

SERVER = "http://127.0.0.1:8188"
IMAGE_PATH = r"D:\文件快传\1713279344578.jpg"
RUN_ID = uuid.uuid4().hex[:8]
CLIENT_ID = f"agent:claude|workflow:wan22_i2v_gguf|run:{RUN_ID}"
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
    # GGUF loader 替代 UNETLoader
    "95":  {"class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": "WAN2.2\\Wan2.2-I2V-HighNoise-14B-Q8_0.gguf"}},
    "96":  {"class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": "WAN2.2\\Wan2.2-I2V-LowNoise-14B-Q8_0.gguf"}},
    "101": {"class_type": "LoraLoaderModelOnly",
            "inputs": {"model": ["95", 0],
                       "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
                       "strength_model": 1.0}},
    "102": {"class_type": "LoraLoaderModelOnly",
            "inputs": {"model": ["96", 0],
                       "lora_name": "wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
                       "strength_model": 1.0}},
    "104": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["101", 0], "shift": 5.0}},
    "103": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["102", 0], "shift": 5.0}},
    "93":  {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": PROMPT_TEXT}},
    "89":  {"class_type": "CLIPTextEncode",
            "inputs": {"clip": ["84", 0], "text": "色调艳丽，过曝，静态，最差质量，低质量，静止不动的画面"}},
    "98":  {"class_type": "WanImageToVideo",
            "inputs": {"positive": ["93", 0], "negative": ["89", 0], "vae": ["90", 0],
                       "start_image": ["200", 0], "width": 640, "height": 640, "length": 33, "batch_size": 1}},
    "86":  {"class_type": "KSamplerAdvanced",
            "inputs": {"model": ["104", 0], "positive": ["98", 0], "negative": ["98", 1], "latent_image": ["98", 2],
                       "add_noise": "enable", "noise_seed": SEED, "steps": 4, "cfg": 1.0,
                       "sampler_name": "euler", "scheduler": "simple",
                       "start_at_step": 0, "end_at_step": 2, "return_with_leftover_noise": "enable"}},
    "85":  {"class_type": "KSamplerAdvanced",
            "inputs": {"model": ["103", 0], "positive": ["98", 0], "negative": ["98", 1], "latent_image": ["86", 0],
                       "add_noise": "disable", "noise_seed": SEED, "steps": 4, "cfg": 1.0,
                       "sampler_name": "euler", "scheduler": "simple",
                       "start_at_step": 2, "end_at_step": 4, "return_with_leftover_noise": "disable"}},
    "87":  {"class_type": "VAEDecode", "inputs": {"samples": ["85", 0], "vae": ["90", 0]}},
    "117": {"class_type": "CreateVideo", "inputs": {"images": ["87", 0], "fps": 16}},
    "120": {"class_type": "SaveVideo",
            "inputs": {"video": ["117", 0], "filename_prefix": "debug_gguf", "format": "auto", "codec": "auto"}},
}

payload = {"client_id": CLIENT_ID, "prompt": prompt,
           "extra_data": {"agent": "claude", "workflow_name": "wan22_i2v_gguf",
                          "source": "agent-projects/wan22-i2v-test",
                          "notes": f"GGUF Q8 turbo, lightx2v LoRA, cfg1, 4steps, 33frames, seed={SEED}"}}

r = requests.post(f"{SERVER}/prompt", json=payload)
result = r.json()
print(f"[2] 提交: {r.status_code}, node_errors={result.get('node_errors')}")
if "prompt_id" in result:
    print(f"[OK] prompt_id={result['prompt_id']}, seed={SEED}, 前缀=debug_gguf")
else:
    print(result)
