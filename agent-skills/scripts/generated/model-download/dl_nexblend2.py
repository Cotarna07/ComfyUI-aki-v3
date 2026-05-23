"""下载 NexBlend - 使用浏览器 UA 模拟"""
import requests
from pathlib import Path
from tqdm import tqdm

URL = "https://civitai.com/api/download/models/2924689"
TOKEN = "91f1ef1523fc016493bcf23f86cbd00a"
OUT = Path(r"d:\ComfyUI-aki-v3\ComfyUI\models\checkpoints\nexblendIvory_v10.safetensors")
OUT.parent.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://civitai.com/",
    "Accept": "*/*",
})

print("[INFO] 正在请求下载链接...")
r = session.get(URL, params={"token": TOKEN}, stream=True, timeout=120)
print(f"[INFO] HTTP {r.status_code}, Content-Type: {r.headers.get('Content-Type', '?')[:60]}")

if r.status_code == 200:
    total = int(r.headers.get("Content-Length", 0))
    print(f"[INFO] 文件大小: {total / 2**30:.2f} GB")
    with open(OUT, "wb") as f:
        with tqdm(total=total, unit="B", unit_scale=True, desc="nexblendIvory") as pbar:
            for chunk in r.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))
    actual = OUT.stat().st_size
    if actual == total:
        print(f"[OK] 下载完成: {OUT} ({actual / 2**30:.2f} GB)")
    else:
        print(f"[WARN] 大小不匹配: {actual} vs {total}")
else:
    print(f"[FAIL] {r.text[:600]}")
