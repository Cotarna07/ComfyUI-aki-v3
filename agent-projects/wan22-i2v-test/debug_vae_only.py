"""
VAE 隔离测试：完全跳过 KSampler 采样
LoadImage -> WanImageToVideo -> (latent 直接) VAEDecode -> Video
WanImageToVideo 的 latent 第一帧是 start_image 的 VAE 编码。
若 decode 后第一帧=原图 -> VAE 正常，问题在 fp8 采样
若 decode 后噪点      -> VAE 本身坏
"""
import requests, uuid

SERVER = "http://127.0.0.1:8188"
IMAGE_PATH = r"D:\文件快传\1713279344578.jpg"
CLIENT_ID = f"agent:claude|workflow:wan22_vae_only|run:{uuid.uuid4().hex[:8]}"

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
    "93":  {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": "test"}},
    "89":  {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": ""}},
    "98":  {"class_type": "WanImageToVideo",
            "inputs": {"positive": ["93", 0], "negative": ["89", 0], "vae": ["90", 0],
                       "start_image": ["200", 0], "width": 640, "height": 640, "length": 33, "batch_size": 1}},
    # 直接 decode WanImageToVideo 的 latent 输出（slot 2），不经过 KSampler
    "87":  {"class_type": "VAEDecode", "inputs": {"samples": ["98", 2], "vae": ["90", 0]}},
    "117": {"class_type": "CreateVideo", "inputs": {"images": ["87", 0], "fps": 16}},
    "120": {"class_type": "SaveVideo",
            "inputs": {"video": ["117", 0], "filename_prefix": "debug_vae_only", "format": "auto", "codec": "auto"}},
}

payload = {"client_id": CLIENT_ID, "prompt": prompt,
           "extra_data": {"agent": "claude", "workflow_name": "wan22_vae_only",
                          "source": "agent-projects/wan22-i2v-test",
                          "notes": "VAE isolation: decode WanImageToVideo latent without sampling"}}

r = requests.post(f"{SERVER}/prompt", json=payload)
result = r.json()
print(f"[2] 提交: {r.status_code}, node_errors={result.get('node_errors')}")
if "prompt_id" in result:
    print(f"[OK] prompt_id={result['prompt_id']}, 前缀=debug_vae_only")
