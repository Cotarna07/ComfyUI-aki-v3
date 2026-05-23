"""CivitAI 下载 — 绕过代理 + 重试"""
import requests, time
from pathlib import Path
from tqdm import tqdm

URL = "https://civitai.com/api/download/models/2924689"
TOKEN = "91f1ef1523fc016493bcf23f86cbd00a"
OUT = Path(r"d:\ComfyUI-aki-v3\ComfyUI\models\checkpoints\nexblendIvory_v10.safetensors")
OUT.parent.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.trust_env = False  # 绕过系统代理
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://civitai.com/",
})

for attempt in range(1, 11):
    try:
        print(f"\n[尝试 {attempt}/10] 请求下载...")
        r = session.get(URL, params={"token": TOKEN}, stream=True, timeout=(30, 300))
        if r.status_code == 200:
            total = int(r.headers.get("Content-Length", 0))
            print(f"[INFO] 大小: {total/2**30:.2f} GB")
            with open(OUT, "wb") as f:
                with tqdm(total=total, unit="B", unit_scale=True) as pbar:
                    for chunk in r.iter_content(1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            actual = OUT.stat().st_size
            if actual >= total * 0.99:
                print(f"[OK] 完成: {actual/2**30:.2f} GB")
                exit(0)
            else:
                print(f"[WARN] 不完整 ({actual/2**30:.2f}/{total/2**30:.2f} GB)，重试...")
        else:
            print(f"[FAIL] HTTP {r.status_code}: {r.text[:200]}")
            break
    except Exception as e:
        print(f"[WARN] {type(e).__name__}: {e}")
    wait = min(30, attempt * 5)
    print(f"[INFO] {wait}s 后重试...")
    time.sleep(wait)

print("[FAIL] 已达最大重试次数")
