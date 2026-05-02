import requests

API_KEY = "91f1ef1523fc016493bcf23f86cbd00a"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "User-Agent": "test"}
TEST_ID = 2557755

for label, base_url in [("官方 civitai.com", "https://civitai.com"), ("镜像 civitai.red", "https://civitai.red")]:
    print(f"\n=== {label} ===")
    try:
        r = requests.get(f"{base_url}/api/v1/models/{TEST_ID}", headers=HEADERS, timeout=15)
        print(f"  status: {r.status_code}")
        if r.status_code == 200:
            d = r.json()
            v = d["modelVersions"][0]
            fn = v["files"][0]
            dl = fn.get("downloadUrl", "N/A")
            sz = fn.get("sizeKB", 0) / 1024
            print(f"  file: {fn['name']}, size: {sz:.0f}MB")
            print(f"  dl: {dl[:100]}...")

            # 测速 - 只下载 1MB
            import time
            start = time.time()
            dr = requests.get(dl, headers=HEADERS, stream=True, timeout=30)
            chunk = dr.iter_content(1024*1024).__next__()
            elapsed = time.time() - start
            speed = len(chunk) / elapsed / 1024 / 1024 if elapsed > 0 else 0
            print(f"  速度测试 (1MB): {speed:.2f} MB/s ({elapsed:.1f}s)")
            dr.close()
        else:
            print(f"  body: {r.text[:200]}")
    except Exception as e:
        print(f"  ERROR: {e}")