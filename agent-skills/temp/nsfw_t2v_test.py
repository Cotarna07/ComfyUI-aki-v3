# -*- coding: utf-8 -*-
"""
NSFW 视频测试 - Wan 2.2 T2V + NSFW LoRA
使用 CLIPLoader + CLIPTextEncode + WanVideoTextEmbedBridge
"""
import json, uuid, time, sys, os, urllib.request, urllib.error

URL = "http://127.0.0.1:8188"

W, H = 832, 480
FRAMES = 81
STEPS = 20
CFG = 5.0
SHIFT = 8.0
SEED = 777

MODEL = "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors"
T5 = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VAE = "Wan2_1_VAE_bf16.safetensors"
LORA = "NSFW-22-H-e8.safetensors"
LORA_S = 0.8

POS = (
    "A beautiful woman with long flowing hair, elegantly posing in soft cinematic lighting, "
    "slow sensual movement, high quality photorealistic 4K video, smooth motion, "
    "detailed skin texture, professional cinematography, shallow depth of field, "
    "warm color grading, intimate atmosphere"
)
NEG = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，"
    "整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，"
    "画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，"
    "静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走, "
    "distorted, deformed, blurry, low quality, worst quality, jpeg artifacts, "
    "ugly, bad anatomy, extra limbs, fused fingers, text, watermark"
)


def build():
    p = {}

    # 1: WanVideoModelLoader
    p["1"] = {
        "class_type": "WanVideoModelLoader",
        "inputs": {
            "model": MODEL,
            "base_precision": "bf16",
            "quantization": "fp8_e4m3fn_scaled",
            "load_device": "offload_device",
            "attention_mode": "sdpa",
        }
    }

    # 2: WanVideoLoraSelectMulti (merge_loras=false for SetLoRAs)
    p["2"] = {
        "class_type": "WanVideoLoraSelectMulti",
        "inputs": {
            "lora_0": LORA,       "strength_0": LORA_S,
            "lora_1": "none",     "strength_1": 1.0,
            "lora_2": "none",     "strength_2": 1.0,
            "lora_3": "none",     "strength_3": 1.0,
            "lora_4": "none",     "strength_4": 1.0,
            "merge_loras": False,
        }
    }

    # 3: WanVideoSetLoRAs
    p["3"] = {
        "class_type": "WanVideoSetLoRAs",
        "inputs": {
            "model": ["1", 0],
            "lora": ["2", 0],
        }
    }

    # 4: CLIPLoader (ComfyUI core) - load T5 as CLIP type "wan"
    p["4"] = {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": T5,
            "type": "wan",
        }
    }

    # 5: CLIPTextEncode (positive)
    p["5"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": POS,
            "clip": ["4", 0],
        }
    }

    # 6: CLIPTextEncode (negative)
    p["6"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": NEG,
            "clip": ["4", 0],
        }
    }

    # 7: WanVideoTextEmbedBridge (bridges CLIP conditioning to Wan format)
    p["7"] = {
        "class_type": "WanVideoTextEmbedBridge",
        "inputs": {
            "positive": ["5", 0],
            "negative": ["6", 0],
        }
    }

    # 8: WanVideoVAELoader
    p["8"] = {
        "class_type": "WanVideoVAELoader",
        "inputs": {
            "model_name": VAE,
            "precision": "bf16",
        }
    }

    # 9: WanVideoEmptyEmbeds
    p["9"] = {
        "class_type": "WanVideoEmptyEmbeds",
        "inputs": {
            "width": W,
            "height": H,
            "num_frames": FRAMES,
        }
    }

    # 10: WanVideoSampler
    p["10"] = {
        "class_type": "WanVideoSampler",
        "inputs": {
            "model": ["3", 0],
            "image_embeds": ["9", 0],
            "text_embeds": ["7", 0],
            "steps": STEPS,
            "cfg": CFG,
            "shift": SHIFT,
            "seed": SEED,
            "force_offload": True,
            "scheduler": "unipc",
            "riflex_freq_index": 0,
        }
    }

    # 11: WanVideoDecode
    p["11"] = {
        "class_type": "WanVideoDecode",
        "inputs": {
            "vae": ["8", 0],
            "samples": ["10", 0],
            "enable_vae_tiling": False,
            "tile_x": 272,
            "tile_y": 272,
            "tile_stride_x": 144,
            "tile_stride_y": 128,
        }
    }

    # 12: VHS_VideoCombine
    p["12"] = {
        "class_type": "VHS_VideoCombine",
        "inputs": {
            "images": ["11", 0],
            "frame_rate": 16,
            "loop_count": 0,
            "filename_prefix": "NSFW_TEST_Wan22_T2V",
            "format": "video/h264-mp4",
            "pix_fmt": "yuv420p",
            "crf": 19,
            "save_metadata": True,
            "trim_to_audio": False,
            "pingpong": False,
            "save_output": True,
        }
    }

    return p


def api(endpoint, data=None, method="POST", timeout=30):
    url = f"{URL}{endpoint}"
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"Content-Type": "application/json"} if body else {})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")[:1500]
        print(f"  ❌ HTTP {e.code}: {msg}")
        return None
    except Exception as e:
        print(f"  ❌ {e}")
        return None


def wait_for(pid, timeout=900):
    print(f"\n⏳ 等待 (ID: {pid})...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        h = api(f"/history/{pid}", method="GET")
        if h and pid in h:
            s = h[pid].get("status", {})
            if s.get("completed"):
                print(f"\n✅ 完成! {time.time()-t0:.1f}s")
                return h[pid]
            if s.get("status_str") == "error":
                print(f"\n❌ 出错: {json.dumps(s, ensure_ascii=False)[:2000]}")
                return h[pid]
        q = api("/queue", method="GET")
        if q:
            for it in q.get("queue_running", []):
                if it[1] == pid:
                    print(f"  ⏳ 运行中 ({time.time()-t0:.0f}s)", end="\r")
        time.sleep(3)
    print(f"\n⏰ 超时")
    return None


def main():
    print("=" * 60)
    print("🎬 NSFW视频测试 - Wan2.2 T2V + NSFW LoRA")
    print("=" * 60)
    print(f"  {W}x{H} {FRAMES}f {STEPS}st CFG={CFG}")

    prompt = build()
    pp = os.path.join(os.path.dirname(__file__), "nsfw_api_prompt.json")
    with open(pp, "w", encoding="utf-8") as f:
        json.dump(prompt, f, ensure_ascii=False, indent=2)

    print("🚀 提交...")
    r = api("/prompt", data={"prompt": prompt, "client_id": f"n{uuid.uuid4().hex[:6]}"})
    if not r:
        return 1

    errs = r.get("node_errors", {})
    if errs:
        print(f"⚠️ 节点错误:\n{json.dumps(errs, ensure_ascii=False, indent=2)[:2500]}")

    pid = r.get("prompt_id")
    if not pid:
        return 1
    print(f"  ✅ prompt_id: {pid}")

    history = wait_for(pid)
    if not history:
        return 1

    print("\n📦 输出:")
    for nid, out in history.get("outputs", {}).items():
        for g in out.get("gifs", []):
            print(f"  📹 {g['filename']}")
        for img in out.get("images", []):
            print(f"  🖼️ {img['filename']}")

    print("✅ 完成!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
