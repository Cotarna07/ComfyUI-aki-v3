"""单独下载 NexBlend_Ivory (CivitAI) — 带断点续传和重试"""
import requests
import time
from pathlib import Path
from tqdm import tqdm

URL = "https://civitai.com/api/download/models/2924689"
TOKEN = "91f1ef1523fc016493bcf23f86cbd00a"
TARGET = Path(r"d:\ComfyUI-aki-v3\ComfyUI\models\checkpoints")
FILENAME = "nexblendIvory_v10.safetensors"
MAX_RETRIES = 10

TARGET.mkdir(parents=True, exist_ok=True)
out = TARGET / FILENAME

for attempt in range(1, MAX_RETRIES + 1):
    resume = out.stat().st_size if out.exists() else 0
    headers = {}
    if resume > 0:
        headers["Range"] = f"bytes={resume}-"

    print(f"\n[NexBlend] 第 {attempt}/{MAX_RETRIES} 次尝试 (已下载: {resume/1024**3:.2f} GB)...")
    try:
        r = requests.get(URL, params={"token": TOKEN}, headers=headers,
                         stream=True, timeout=120, allow_redirects=True)
        if r.status_code == 416:
            print("[OK] 文件已完整下载 (HTTP 416)")
            break
        if r.status_code not in (200, 206):
            print(f"[FAIL] HTTP {r.status_code}: {r.text[:300]}")
            break

        total = int(r.headers.get("Content-Length", 0))
        mode = "ab" if resume > 0 else "wb"
        with open(out, mode) as f:
            with tqdm(total=total, initial=resume, unit="B", unit_scale=True, desc=FILENAME) as pbar:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        print(f"[OK] 完成: {out} ({out.stat().st_size/1024**3:.2f} GB)")
        break
    except (requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout) as e:
        print(f"[WARN] 连接中断: {e}")
        if attempt < MAX_RETRIES:
            wait = min(30, attempt * 5)
            print(f"[INFO] {wait}s 后重试...")
            time.sleep(wait)
    except Exception as e:
        print(f"[FAIL] 未预期错误: {e}")
        break
else:
    print(f"[FAIL] 已达最大重试次数 ({MAX_RETRIES})")

