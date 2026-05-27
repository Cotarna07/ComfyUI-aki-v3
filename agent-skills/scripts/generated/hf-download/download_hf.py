"""
HF 模型通用下载器 — 直连 hf-mirror.com，支持断点续传
用法:
  python download_hf.py <repo_id> --files <file1> <file2> ... [-o <output_dir>]
  python download_hf.py <repo_id> --all   # 下载全部文件
  python download_hf.py <repo_id> --pattern "*.gguf"  # 按 glob 模式匹配
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import time
from pathlib import Path

import requests

MIRROR = "https://hf-mirror.com"
CHUNK_SIZE = 8 * 1024 * 1024
MAX_RETRIES = 10
RETRY_WAIT = 15
TIMEOUT = 120


def get_file_list(repo_id: str) -> list[str]:
    """从 hf-mirror API 获取文件列表。"""
    url = f"{MIRROR}/api/models/{repo_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    siblings = data.get("siblings", [])
    return [s["rfilename"] for s in siblings if s.get("rfilename")]


def download_file(repo_id: str, filename: str, output_dir: Path) -> bool:
    """下载单个文件，支持断点续传。"""
    target = output_dir / filename
    part = output_dir / (filename + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        size_mb = target.stat().st_size / 1024 / 1024
        print(f"  [SKIP] {filename} ({size_mb:.0f} MB, already exists)")
        return True

    existing = part.stat().st_size if part.exists() else 0
    url = f"{MIRROR}/{repo_id}/resolve/main/{filename}"
    headers = {"User-Agent": "ComfyUI-Agent/1.0"}
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=TIMEOUT)
            if resp.status_code not in (200, 206):
                print(f"  [ERR] HTTP {resp.status_code} (attempt {attempt})")
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
                        print(f"\r  [{bar}] {pct:5.1f}%  {written/1024/1024:.0f}/{total/1024/1024:.0f} MB", end="", flush=True)

            print()
            part.rename(target)
            return True

        except (requests.RequestException, OSError) as e:
            print(f"\n  [ERR] {e} (attempt {attempt}/{MAX_RETRIES})")
            if attempt < MAX_RETRIES:
                wait = RETRY_WAIT * attempt
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)

    return False


def main():
    parser = argparse.ArgumentParser(description="HF 模型通用下载器（直连 hf-mirror.com，支持续传）")
    parser.add_argument("repo_id", help="HF 仓库 ID，如 HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive")
    parser.add_argument("--files", "-f", nargs="+", help="要下载的文件名列表")
    parser.add_argument("--pattern", "-p", help="glob 模式匹配，如 *.gguf")
    parser.add_argument("--all", "-a", action="store_true", help="下载仓库全部文件")
    parser.add_argument("--output", "-o", default=None, help="输出目录")
    parser.add_argument("--list", "-l", action="store_true", help="仅列出文件，不下载")
    args = parser.parse_args()

    repo_id = args.repo_id
    output_dir = Path(args.output) if args.output else Path("models") / repo_id.split("/")[-1]

    print(f"Repo:   {repo_id}")
    print(f"Mirror: {MIRROR}")
    print(f"Output: {output_dir}")
    print()

    # Get file list
    print("Fetching file list...")
    try:
        all_files = get_file_list(repo_id)
    except Exception as e:
        print(f"FATAL: Cannot fetch file list: {e}")
        print("Tip: Check repo_id or try --files to specify filenames directly.")
        return 1

    # Filter files
    if args.files:
        files = [f for f in all_files if f in args.files]
        missing = set(args.files) - set(files)
        if missing:
            print(f"Warning: these files not found in repo: {missing}")
    elif args.pattern:
        files = [f for f in all_files if fnmatch.fnmatch(f, args.pattern)]
    elif args.all:
        files = all_files
    else:
        print("Specify --files, --pattern, or --all.")
        print("\nAvailable files:")
        for f in all_files:
            print(f"  {f}")
        return 1

    if not files:
        print("No files matched. Available files:")
        for f in all_files:
            print(f"  {f}")
        return 1

    # Show files
    gguf_files = [f for f in files if f.endswith(".gguf")]
    other_files = [f for f in files if not f.endswith(".gguf")]
    print(f"Files to download: {len(files)}")
    for f in gguf_files:
        print(f"  [GGUF] {f}")
    for f in other_files:
        print(f"  [CFG]  {f}")
    print()

    if args.list:
        return 0

    # Download small files first
    ok = fail = 0
    for i, name in enumerate(other_files + gguf_files, 1):
        print(f"[{i}/{len(files)}] {name}")
        if download_file(repo_id, name, output_dir):
            ok += 1
        else:
            fail += 1

    print(f"\nDone: {ok} ok, {fail} failed out of {len(files)} files")
    if fail == 0:
        print(f"Ready at: {output_dir}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
