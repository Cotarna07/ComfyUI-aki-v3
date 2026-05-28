"""LTX 模型批量下载 — requests 流式 + 激进 flush，确保数据即时落盘"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests

MIRROR = "https://hf-mirror.com"
CHUNK_SIZE = 1 * 1024 * 1024  # 1MB — 小 chunk 避免缓冲堆积
MAX_RETRIES = 10
RETRY_WAIT = 15
TIMEOUT = 180

MODEL_ROOT = Path(r"D:\ComfyUI-aki-v3\ComfyUI\models")

# 下载清单: (repo, src_path, dst_dir, dst_name)
TASKS = [
    # === VAE (3) ===
    ("Kijai/LTX2.3_comfy", "vae/LTX23_video_vae_bf16.safetensors", "vae", "LTX23_video_vae_bf16.safetensors"),
    ("Kijai/LTX2.3_comfy", "vae/LTX23_audio_vae_bf16.safetensors", "vae", "LTX23_audio_vae_bf16.safetensors"),
    ("Kijai/LTX2.3_comfy", "vae/taeltx2_3.safetensors", "vae", "taeltx2_3.safetensors"),
    # === Text Encoder (1) ===
    ("Kijai/LTX2.3_comfy", "text_encoders/ltx-2.3_text_projection_bf16.safetensors", "text_encoders", "ltx-2.3_text_projection_bf16.safetensors"),
    # === MelBandRoformer (1) ===
    ("Kijai/MelBandRoformer_comfy", "MelBandRoformer_fp32.safetensors", "audio_encoders", "MelBandRoformer_fp32.safetensors"),
]


def download(repo: str, src: str, dst_dir: str, dst_name: str) -> bool:
    target = MODEL_ROOT / dst_dir / dst_name
    part = target.with_suffix(target.suffix + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        print(f"  SKIP (exists): {target}")
        return True

    url = f"{MIRROR}/{repo}/resolve/main/{src}"
    headers = {"User-Agent": "ComfyUI-Agent/1.0"}

    for attempt in range(1, MAX_RETRIES + 1):
        # 每次重试时重新检查 .part 大小，动态构造 Range
        existing = part.stat().st_size if part.exists() else 0
        if existing > 0:
            headers["Range"] = f"bytes={existing}-"
        else:
            headers.pop("Range", None)

        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=TIMEOUT)
            if resp.status_code not in (200, 206):
                print(f"  HTTP {resp.status_code} (attempt {attempt})")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_WAIT)
                continue

            total = int(resp.headers.get("Content-Length", "0"))

            if resp.status_code == 206:
                # 服务器支持 Range，续传模式
                total += existing
                mode = "ab"
                written = existing
            elif existing > 0:
                # 服务器不支持 Range（返回 200），丢弃残片从头下载
                print(f"  Server ignored Range, restarting from 0...")
                part.unlink(missing_ok=True)
                existing = 0
                mode = "wb"
                written = 0
            else:
                mode = "wb"
                written = 0

            with part.open(mode) as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())
                    written += len(chunk)
                    if total and total > 0:
                        pct = min(100, written / total * 100)
                        bar = "=" * int(pct / 4) + ">" + " " * (25 - int(pct / 4))
                        print(f"\r  [{bar}] {pct:5.1f}%  {written/1024/1024:.0f}/{total/1024/1024:.0f} MB", end="", flush=True)

            print()
            part.rename(target)
            return True

        except (requests.RequestException, OSError) as e:
            print(f"\n  ERR: {e} (attempt {attempt}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES:
                wait = RETRY_WAIT * attempt
                print(f"  Retry in {wait}s...")
                time.sleep(wait)

    return False


def main():
    ok = fail = 0
    total = len(TASKS)
    for i, (repo, src, dst_dir, dst_name) in enumerate(TASKS, 1):
        print(f"\n[{i}/{total}] {dst_dir}/{dst_name}")
        print(f"       <- {repo}/{src}")
        if download(repo, src, dst_dir, dst_name):
            ok += 1
        else:
            fail += 1
            print(f"  FAILED: {dst_name}")

    print(f"\n{'='*60}")
    print(f"Done: {ok} ok, {fail} failed / {total} files")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
