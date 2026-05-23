#!/usr/bin/env python3
"""
ComfyUI 模型下载脚本
按队列顺序下载 6 个模型到 ComfyUI/models/ 对应子目录。
支持断点续传、进度显示、失败重试。

用法：
    d:/ComfyUI-aki-v3/.venv/Scripts/python.exe download_models.py
"""

import os
import sys
import time
import json
import shutil
from pathlib import Path
from datetime import datetime

import requests
from tqdm import tqdm
from huggingface_hub import snapshot_download, hf_hub_download, list_repo_files

# ── 配置 ──────────────────────────────────────────────
COMFYUI_ROOT = Path(r"d:\ComfyUI-aki-v3\ComfyUI")
MODELS_ROOT = COMFYUI_ROOT / "models"
LOG_DIR = Path(__file__).resolve().parent / "runtime"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 下载记录文件（用于断点续传）
STATE_FILE = LOG_DIR / "download_state.json"

# CivitAI API Key（如果有的话从环境变量读取）
CIVITAI_API_KEY = os.environ.get("CIVITAI_API_KEY", "91f1ef1523fc016493bcf23f86cbd00a")

# ── 模型下载列表 ──────────────────────────────────────
MODELS = [
    {
        "id": "cogvideox-5b-i2v",
        "name": "CogVideoX-5b-I2V",
        "source": "huggingface",
        "repo": "THUDM/CogVideoX-5b-I2V",
        "target_dir": MODELS_ROOT / "diffusion_models" / "CogVideoX-5b-I2V",
        "size_gb": 10.5,
    },
    {
        "id": "hunyuan-video-1.5",
        "name": "Hunyuan Video 1.5 (T2V + I2V 720p fp16)",
        "source": "huggingface",
        "repo": "tencent/HunyuanVideo-1.5",
        "target_dir": MODELS_ROOT / "diffusion_models" / "HunyuanVideo-1.5",
        "size_gb": 31.0,
        "note": "同一仓库包含 T2V（根目录）和 I2V（image_to_video 子目录）",
    },
    {
        "id": "nexblend-ivory",
        "name": "NexBlend_Ivory Illustrious",
        "source": "civitai",
        "version_id": "2924689",
        "target_dir": MODELS_ROOT / "checkpoints",
        "filename": "nexblendIvory_v10.safetensors",
        "size_gb": 6.5,
    },
    # Liquid Glamour Illustrious — 未找到，跳过
    {
        "id": "wan21-i2v-14b-720p",
        "name": "Wan2.1 I2V 14B 720P (LightX2V base)",
        "source": "huggingface",
        "repo": "Wan-AI/Wan2.1-I2V-14B-720P",
        "target_dir": MODELS_ROOT / "diffusion_models" / "Wan2.1-I2V-14B-720P",
        "size_gb": 10.1,
    },
]


def load_state() -> dict:
    """加载下载状态"""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict):
    """保存下载状态"""
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def download_hf_model(model: dict, state: dict) -> bool:
    """使用 huggingface_hub Python API 下载模型（支持断点续传）"""
    model_id = model["id"]
    repo = model["repo"]
    target = Path(model["target_dir"])

    if state.get(model_id) == "done":
        print(f"[SKIP] {model['name']} — 已完成")
        return True

    target.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"[DOWNLOAD] {model['name']} (~{model['size_gb']} GB)")
    print(f"  源: https://huggingface.co/{repo}")
    print(f"  目标: {target}")
    print(f"{'='*60}")

    try:
        # 先列出仓库文件以估算大小
        print("[INFO] 正在获取文件列表...")
        try:
            files = list_repo_files(repo)
            print(f"[INFO] 仓库包含 {len(files)} 个文件")
        except Exception:
            files = []
            print("[INFO] 无法获取文件列表，将直接下载")

        # 下载整个仓库快照（自动跳过已存在且校验通过的文件）
        downloaded_path = snapshot_download(
            repo_id=repo,
            local_dir=str(target),
            resume_download=True,
            max_workers=4,
            local_files_only=False,
        )
        print(f"[INFO] 下载路径: {downloaded_path}")
        state[model_id] = "done"
        save_state(state)
        print(f"[OK] {model['name']} 下载完成")
        return True
    except Exception as e:
        print(f"[FAIL] {model['name']} 下载失败: {e}")
        state[model_id] = "failed"
        save_state(state)
        return False


def download_civitai_model(model: dict, state: dict) -> bool:
    """从 CivitAI 下载模型"""
    model_id = model["id"]
    version_id = model["version_id"]
    target = Path(model["target_dir"])
    filename = model.get("filename", f"{model['name']}.safetensors")
    output_path = target / filename

    if state.get(model_id) == "done":
        print(f"[SKIP] {model['name']} — 已完成")
        return True

    target.mkdir(parents=True, exist_ok=True)

    url = f"https://civitai.com/api/download/models/{version_id}"
    params = {}
    if CIVITAI_API_KEY:
        params["token"] = CIVITAI_API_KEY

    print(f"\n{'='*60}")
    print(f"[DOWNLOAD] {model['name']} (~{model['size_gb']} GB)")
    print(f"  URL: {url}")
    print(f"  目标: {output_path}")
    print(f"{'='*60}")

    try:
        # 检查已下载的部分
        resume_pos = 0
        if output_path.exists():
            resume_pos = output_path.stat().st_size
            print(f"[INFO] 发现已有文件 ({resume_pos / (1024**3):.2f} GB)，将续传...")

        headers = {}
        if resume_pos > 0:
            headers["Range"] = f"bytes={resume_pos}-"

        # 先获取文件大小
        with requests.get(url, params=params, stream=True, headers={"Range": "bytes=0-0"}, timeout=30) as r:
            if r.status_code in (200, 206):
                content_range = r.headers.get("Content-Range", "")
                if "/" in content_range:
                    total_size = int(content_range.split("/")[-1])
                else:
                    total_size = int(r.headers.get("Content-Length", 0))
            elif r.status_code == 401 or r.status_code == 403:
                print(f"[FAIL] CivitAI 需要 API Key。请设置环境变量 CIVITAI_API_KEY")
                print(f"       也可以手动从浏览器下载: https://civitai.com/models/{model.get('civitai_model_id', '?')}")
                state[model_id] = "failed"
                save_state(state)
                return False
            else:
                total_size = 0

        # 流式下载
        mode = "ab" if resume_pos > 0 else "wb"
        with requests.get(url, params=params, stream=True, headers=headers, timeout=60) as r:
            if r.status_code not in (200, 206):
                print(f"[FAIL] HTTP {r.status_code}: {r.text[:200]}")
                state[model_id] = "failed"
                save_state(state)
                return False

            total = total_size or int(r.headers.get("Content-Length", 0))
            initial_pos = resume_pos

            with open(output_path, mode) as f:
                chunk_size = 1024 * 1024  # 1 MB
                with tqdm(
                    total=total, initial=initial_pos, unit="B",
                    unit_scale=True, desc=filename[:40],
                ) as pbar:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

        state[model_id] = "done"
        save_state(state)
        print(f"[OK] {model['name']} 下载完成 → {output_path}")
        return True

    except Exception as e:
        print(f"[FAIL] {model['name']} 异常: {e}")
        state[model_id] = "failed"
        save_state(state)
        return False


def main():
    print("=" * 60)
    print("  ComfyUI 模型批量下载")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  磁盘剩余: {shutil.disk_usage(MODELS_ROOT).free / (1024**3):.1f} GB")
    print("=" * 60)

    state = load_state()

    results = {"succeeded": [], "failed": [], "skipped": []}
    total_models = 0
    failed_models = 0

    for i, model in enumerate(MODELS, 1):
        print(f"\n{'─'*50}")
        print(f"  [{i}/{len(MODELS)}] {model['name']}")
        print(f"{'─'*50}")

        total_models += 1

        try:
            if model["source"] == "huggingface":
                ok = download_hf_model(model, state)
            elif model["source"] == "civitai":
                ok = download_civitai_model(model, state)
            else:
                print(f"[SKIP] 未知来源: {model['source']}")
                results["skipped"].append(model["name"])
                continue

            if ok:
                results["succeeded"].append(model["name"])
            else:
                results["failed"].append(model["name"])
                failed_models += 1
        except KeyboardInterrupt:
            print("\n[INFO] 用户中断，进度已保存")
            save_state(state)
            break
        except Exception as e:
            print(f"[FAIL] 未预期的错误: {e}")
            results["failed"].append(model["name"])
            failed_models += 1

    # ── 总结 ─────────────────────────────────────────
    print("\n\n" + "=" * 60)
    print("  下载总结")
    print("=" * 60)
    print(f"  总计: {total_models}")
    print(f"  成功: {len(results['succeeded'])}")
    print(f"  失败: {len(results['failed'])}")
    print(f"  跳过: {len(results['skipped'])}")

    if results["succeeded"]:
        print("\n  ✅ 已下载:")
        for name in results["succeeded"]:
            print(f"     - {name}")

    if results["failed"]:
        print("\n  ❌ 下载失败:")
        for name in results["failed"]:
            print(f"     - {name}")
        print("\n  可重新运行本脚本继续未完成的下载。")

    # 关于 Liquid Glamour
    print("\n  ⚠️  Liquid Glamour Illustrious:")
    print("     在 CivitAI 和 HuggingFace 均未找到该模型。")
    print("     请确认模型名称是否正确，或提供具体下载链接。")

    save_state(state)


if __name__ == "__main__":
    main()
