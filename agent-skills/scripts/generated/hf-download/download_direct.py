"""
直连 hf-mirror.com 下载 InternVL3_5-8B
使用 requests + Range 续传，绕过 huggingface_hub 库的镜像兼容问题。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

MIRROR = "https://hf-mirror.com"
REPO_ID = "OpenGVLab/InternVL3_5-8B"
OUTPUT_DIR = Path(r"D:\ComfyUI-aki-v3\models\InternVL3_5-8B")
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB
MAX_RETRIES = 10
RETRY_WAIT = 15
TIMEOUT = 120


def get_file_list() -> list[dict]:
    """从 hf-mirror API 获取文件列表。"""
    url = f"{MIRROR}/api/models/{REPO_ID}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    siblings = data.get("siblings", [])
    return [s for s in siblings if s.get("rfilename")]


def download_file(filename: str) -> bool:
    """下载单个文件，支持断点续传。"""
    target = OUTPUT_DIR / filename
    part = OUTPUT_DIR / (filename + ".part")

    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        print(f"  [SKIP] {filename} (already exists)")
        return True

    existing = part.stat().st_size if part.exists() else 0

    url = f"{MIRROR}/{REPO_ID}/resolve/main/{filename}"
    headers = {"User-Agent": "ComfyUI-Agent/1.0"}
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=TIMEOUT)
            if resp.status_code not in (200, 206):
                print(f"  [ERR] {filename} HTTP {resp.status_code} (attempt {attempt})")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_WAIT)
                continue

            total = int(resp.headers.get("Content-Length", "0"))
            if resp.status_code == 206:
                total += existing

            mode = "ab" if resp.status_code == 206 else "wb"
            written = existing if resp.status_code == 206 else 0

            with part.open(mode) as f:
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    written += len(chunk)
                    if total:
                        pct = min(100, written / total * 100)
                        bar = "=" * int(pct / 4) + ">" + " " * (25 - int(pct / 4))
                        print(f"\r  [{bar}] {pct:5.1f}%  {written / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB", end="", flush=True)

            print()
            part.rename(target)
            return True

        except (requests.RequestException, OSError) as e:
            print(f"\n  [ERR] {filename}: {e} (attempt {attempt}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES:
                wait = RETRY_WAIT * attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)

    return False


def main():
    print(f"Repo:  {REPO_ID}")
    print(f"Mirror: {MIRROR}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    # 1. Get file list
    print("Fetching file list...")
    try:
        files = get_file_list()
    except Exception as e:
        print(f"FATAL: Cannot fetch file list: {e}")
        return 1

    filenames = [f["rfilename"] for f in files]
    safetensors = [n for n in filenames if n.endswith(".safetensors")]
    others = [n for n in filenames if not n.endswith(".safetensors")]

    print(f"Total: {len(filenames)} files")
    print(f"  Model weights: {len(safetensors)} safetensors")
    print(f"  Config/code:   {len(others)} files")
    print()

    # 2. Download small files first, then big ones
    ok = 0
    fail = 0

    for name in others:
        print(f"[{ok + fail + 1}/{len(filenames)}] {name}")
        if download_file(name):
            ok += 1
        else:
            fail += 1
            print(f"  [FAIL] {name}")

    for name in safetensors:
        print(f"[{ok + fail + 1}/{len(filenames)}] {name}")
        if download_file(name):
            ok += 1
        else:
            fail += 1
            print(f"  [FAIL] {name}")

    print()
    print(f"Done: {ok} ok, {fail} failed out of {len(filenames)} files")
    if fail == 0:
        print(f"Model ready at: {OUTPUT_DIR}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
