#!/usr/bin/env python3
"""
批量从 Civitai API 下载 NSFW 审核清单中本地缺失的模型。
支持多线程并发下载、断点续传、镜像切换。
"""
import os
import sys
import json
import time
import hashlib
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# 配置
# ============================================================
API_KEY = "91f1ef1523fc016493bcf23f86cbd00a"
# 使用镜像 API (下载 URL 仍指向同一 CDN，但并发可提升整体吞吐)
API_MIRRORS = [
    "https://civitai.com/api/v1",
    "https://civitai.red/api/v1",
]
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent.parent.parent  # d:\ComfyUI-aki-v3
LORAS_DIR = DOWNLOAD_DIR / "ComfyUI" / "models" / "loras"
CHECKPOINTS_DIR = DOWNLOAD_DIR / "ComfyUI" / "models" / "checkpoints"
DIFFUSION_DIR = DOWNLOAD_DIR / "ComfyUI" / "models" / "diffusion_models"
LOG_FILE = Path(__file__).resolve().parent.parent / "runtime" / "download_log.json"
PROGRESS_FILE = Path(__file__).resolve().parent.parent / "runtime" / "download_progress.json"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "User-Agent": "ComfyUI-Model-Downloader/2.0"
}

# 并发数
MAX_WORKERS = 4
# 重试
MAX_RETRIES = 3

# ============================================================
# 模型清单
# ============================================================
MODELS_TO_DOWNLOAD = [
    # ===== 来自 NSFW_model_review_2026-05-02.md =====
    # -- 视频 LoRA --
    {"id": 2557755, "file": "anime90s-step00053000.comfy.safetensors", "dir": "loras", "name": "Retro 90's Anime Style Lora LTX-2.3"},
    {"id": 2545236, "file": "AI Girl Fictional Women Series19 high_noise.safetensors", "dir": "loras", "name": "AI Girl Series19 Wan 2.2 T2V"},
    {"id": 2563394, "file": "Post_Apocalyptic.safetensors", "dir": "loras", "name": "LTX 2.3 Cinematic Post-Apocalyptic"},
    {"id": 2562743, "file": "Pop-Art-6000.safetensors", "dir": "loras", "name": "LTX-2.3 Pop-Art"},
    {"id": 2574636, "file": "StarTrek_TNG_Style_LTX23_v1.safetensors", "dir": "loras", "name": "Star Trek TNG Style LTX 2.3"},
    {"id": 2564605, "file": "AI Girl Fictional Women Series20_high_noise.safetensors", "dir": "loras", "name": "AI Girl Series20 Wan 2.2 T2V"},
    {"id": 2548223, "file": "TFM Pocket RPG Wan22.zip", "dir": "loras", "name": "TFM Pocket RPG Style Wan 2.2"},
    # -- Illustrious LoRA --
    {"id": 2591171, "file": "kcnagato-illu-nvwls-v1.safetensors", "dir": "loras", "name": "Nagato (Kantai Collection) Illustrious"},
    {"id": 2591159, "file": "himemiyamakoto-illu-nvwls-v1.safetensors", "dir": "loras", "name": "Makoto Himemiya Illustrious"},
    {"id": 2591168, "file": "kcmusashi-illu-nvwls-v1.safetensors", "dir": "loras", "name": "Musashi (Kantai Collection) Illustrious"},
    {"id": 2591164, "file": "zhezhi-illu-nvwls-v1.safetensors", "dir": "loras", "name": "Zhezhi (Wuthering Waves) Illustrious"},
    {"id": 2591161, "file": "eowarlock-illu-nvwls-v1.safetensors", "dir": "loras", "name": "Warlock (Etrian Odyssey V) Illustrious"},
    {"id": 2591166, "file": "phrolova-illu-nvwls-v1.safetensors", "dir": "loras", "name": "Phrolova (Wuthering Waves) Illustrious"},
    {"id": 2591156, "file": "saigawarareika-illu-nvwls-v1.safetensors", "dir": "loras", "name": "Reika Saigawara Illustrious"},
    {"id": 2591162, "file": "erikawagner-illu-nvwls-v1.safetensors", "dir": "loras", "name": "Erika Wagner Illustrious"},
    {"id": 2590865, "file": "inkstain.safetensors", "dir": "loras", "name": "Inkstain-Style Illustrious"},
    {"id": 2590645, "file": "Okymir.safetensors", "dir": "loras", "name": "Okymir-Style Illustrious"},
    {"id": 2590680, "file": "Tenakostyle.safetensors", "dir": "loras", "name": "Tenako-Style Illustrious"},
    {"id": 2590970, "file": "DryadVoM.safetensors", "dir": "loras", "name": "Dryad (Visions of Mana) Illustrious"},
    {"id": 2591821, "file": "HnA_shinonome_yukijiXLIllustrious001.safetensors", "dir": "loras", "name": "Shinonome Yukiji Illustrious"},
    {"id": 2590404, "file": "IL_Waligner early Style-000045.safetensors", "dir": "loras", "name": "Waligner Style SDXL Illustrious"},
    {"id": 2592033, "file": "Amami_himeko_1.0-000001.safetensors", "dir": "loras", "name": "Amami himeko SDXL"},
    {"id": 2591890, "file": "yuzhi-000009.safetensors", "dir": "loras", "name": "国漫-仙剑奇侠传3-玉枝 Illustrious"},
    {"id": 2591756, "file": "SDAVY2CAMCAEV38W7FRGRSX2H0.safetensors", "dir": "loras", "name": "luna_sdxl"},
    # -- Flux LoRA --
    {"id": 2587002, "file": "MS_BBW_Style_klein_V1.safetensors", "dir": "loras", "name": "MS BBW-Style Flux.2 klein"},
    {"id": 2584543, "file": "MS_Fantasy_Style_klein_V3.safetensors", "dir": "loras", "name": "MS Fantasy Style Flux.2 klein"},
    {"id": 2588084, "file": "MS_LuisRoyo_Style_klein_V1.safetensors", "dir": "loras", "name": "MS LuisRoyo Style Flux.2 klein"},
    {"id": 2586647, "file": "B77HM1Z5X4HE4B6S09ASG1T6K0.safetensors", "dir": "loras", "name": "Norn Greyrat Flux 2 Klein"},
    {"id": 2591423, "file": "CelShaded3dMix_epoch_10(1).safetensors", "dir": "loras", "name": "Flux 2 Klein Styles Pack"},
    # -- Flux.1 D LoRA --
    {"id": 2587590, "file": "Lyza V16.safetensors", "dir": "loras", "name": "Flux 1D LYZA Female"},
    {"id": 2587660, "file": "Anya v16.safetensors", "dir": "loras", "name": "Flux 1D ANYA Female"},
    {"id": 2587585, "file": "Kael V16.safetensors", "dir": "loras", "name": "Flux 1D Kael Latina Female"},
    {"id": 2586288, "file": "Gwendolynn_Blonde_Beauty_Flux.safetensors", "dir": "loras", "name": "Gwendolynn Blonde Flux"},
    # -- Pony LoRA --
    {"id": 2588106, "file": "middycut.safetensors", "dir": "loras", "name": "Middy cut Pony"},
    {"id": 2589013, "file": "farahpop.safetensors", "dir": "loras", "name": "Farah (Prince of Persia) Pony"},
    {"id": 2588646, "file": "c4r4dun3.safetensors", "dir": "loras", "name": "Cara Dune (Mandalorian) Pony"},
    {"id": 2589169, "file": "r4mp4rt.safetensors", "dir": "loras", "name": "Rampart (Apex Legends) Pony"},
    {"id": 2590909, "file": "1ll4r1.safetensors", "dir": "loras", "name": "Illari (Overwatch) Pony"},
    {"id": 2591466, "file": "hawgog.safetensors", "dir": "loras", "name": "hotdog costume pony"},
    {"id": 2591506, "file": "r4ze.safetensors", "dir": "loras", "name": "Raze (Valorant) Pony"},
    # -- NoobAI LoRA --
    {"id": 2589216, "file": "yuu.safetensors", "dir": "loras", "name": "yuu NoobAI"},
    {"id": 2585480, "file": "dream_journey_(umamusume)_NoobAI.safetensors", "dir": "loras", "name": "Dream Journey NoobAI"},
    {"id": 2586527, "file": "Art_Deco_Interior_2_(Buildings)_(NoobAI)_(AD).safetensors", "dir": "loras", "name": "Art Deco Interior NoobAI"},
    {"id": 2586882, "file": "MHASty_(My_Hero_Academia)_(NoobAI)_(AD).safetensors", "dir": "loras", "name": "My Hero Academia Style NoobAI"},
    {"id": 2586726, "file": "CuAwVi_(Buildings)_(Architecture)_(NoobAI)_(AD).safetensors", "dir": "loras", "name": "Cutaway View NoobAI"},
    {"id": 2586007, "file": "ArDec2_(Buildings)_(NoobAI)_(AD).safetensors", "dir": "loras", "name": "Art Deco NoobAI"},
    {"id": 2589499, "file": "SetAdv_(Gods_of_Egypt)_(NoobAI)_(AD).safetensors", "dir": "loras", "name": "Set Advanced NoobAI"},
    # -- LoCon --
    {"id": 2589385, "file": "ChiyuMahouV1.safetensors", "dir": "loras", "name": "Chiyu Mahou Illustrious/NoobAI"},
    {"id": 2587133, "file": "looped-style.safetensors", "dir": "loras", "name": "Looped Style Pony XL"},
    {"id": 2590183, "file": "ninas-world-style.safetensors", "dir": "loras", "name": "Nina's World Style Pony XL"},
    # -- 特殊 LoRA --
    {"id": 2585656, "file": "_sherum_trickcal-elesico-ilxl.safetensors", "dir": "loras", "name": "Sherum Trickcal Illustrious/NoobAI"},
    {"id": 2588918, "file": "DVGQ6NFATCWS55A8K291G5PC90.safetensors", "dir": "loras", "name": "Bao the Whale Valentine Nurse"},
    # -- Workflows (zip/json) --
    {"id": 2534583, "file": "wan22I2vComfyuiWorkflowSVI_v11.zip", "dir": "workflows", "name": "SVI FFLF Wan 2.2 Workflow"},
    {"id": 2572452, "file": "wan22ImageToVideo_v10.zip", "dir": "workflows", "name": "Wan 2.2 image to video Workflow"},
    {"id": 2526617, "file": "ltx23WorkflowCollection_v10.zip", "dir": "workflows", "name": "LTX 2.3 Workflow Collection"},
    {"id": 2563128, "file": "ltx23ClearLearning_v10.zip", "dir": "workflows", "name": "LTX 2.3 Clear Learning Workflow"},
    {"id": 2570937, "file": "wanVace21FlowArchive_simple.zip", "dir": "workflows", "name": "Wan Vace 2.1 Flow Archive"},
    {"id": 2568753, "file": "ltx23WwsDistilled_v10.json", "dir": "workflows", "name": "LTX 2.3 WW's Distilled Enhancer"},
    {"id": 2575568, "file": "wan22AnimateWorkflow_v10.zip", "dir": "workflows", "name": "Wan 2.2 animate workflow"},
    {"id": 2587093, "file": "ltx23EditAnythingInComfyui_v10.zip", "dir": "workflows", "name": "LTX 2.3 Edit Anything Workflow"},
    {"id": 2587104, "file": "ltx23PromptRelayInComfyui_v10.zip", "dir": "workflows", "name": "LTX 2.3 Prompt Relay Workflow"},
    {"id": 2566341, "file": "ltx2322BICLoraOutpaint_v10.json", "dir": "workflows", "name": "LTX-2.3 22B IC-LoRA Outpaint Workflow"},
    {"id": 2524864, "file": "wan21FunImageToVideoAnd_v10.zip", "dir": "workflows", "name": "Wan 2.1 Fun I2V T2V Workflow"},
    {"id": 2524877, "file": "wan21FunMotionControlAI_v10.zip", "dir": "workflows", "name": "Wan 2.1 Fun Motion Control"},
    {"id": 2585899, "file": "ultimateWorkflowSuperCompleteComfyuiSDXLILLUSD15_v30.zip", "dir": "workflows", "name": "Ultimate Workflow Super Complete"},
    {"id": 2585899, "file": "ultimateWorkflowSuperCompleteComfyuiSDXLILLUSD15_v30.json", "dir": "workflows", "name": "Ultimate Workflow Super Complete (json)"},
    {"id": 2587111, "file": "ltx23CozyFeltInComfyui_v10.zip", "dir": "workflows", "name": "LTX 2.3 Cozy Felt Workflow"},

    # ===== 来自 NSFW模型审核清单_2026-05-02.md =====
    {"id": 2522967, "file": "AI Girl Fictional Women Series17_high_noise.safetensors", "dir": "loras", "name": "AI Girl Series17 Wan 2.2 T2V"},
    {"id": 2522688, "file": "wan22AIORapid_v10.zip", "dir": "workflows", "name": "WAN 2.2 AIO Rapid Workflow"},
    {"id": 2524167, "file": "wan22VideoOutpaintingVACE_v10.zip", "dir": "workflows", "name": "Wan 2.2 Video Outpainting VACE"},
    {"id": 2534759, "file": "wan22WanAppEasyAppMode_v10.zip", "dir": "workflows", "name": "WanApp Wan2.2 EASY APP MODE"},
    {"id": 2587373, "file": "shalltear_bloodfallen_overlord.safetensors", "dir": "loras", "name": "Shalltear Bloodfallen Illustrious"},
    {"id": 2585608, "file": "prostitute_two_overlord.safetensors", "dir": "loras", "name": "Prostitute Two (Overlord) Illustrious"},
    {"id": 667086, "file": "NSFW_MASTER_FLUX.safetensors", "dir": "loras", "name": "NSFW MASTER FLUX"},
    {"id": 958009, "file": "RedCraft.safetensors", "dir": "checkpoints", "name": "RedCraft 红潮"},
    {"id": 1277670, "file": "JANKU_Chenkin_NoobAI_RouWei.safetensors", "dir": "checkpoints", "name": "JANKU Illustrious merge"},
    {"id": 376130, "file": "Nova_Anime_XL.safetensors", "dir": "checkpoints", "name": "Nova Anime XL"},
    {"id": 974693, "file": "Realism_Illustrious_StableYogi.safetensors", "dir": "checkpoints", "name": "Realism Illustrious Stable Yogi"},
]

# 全局锁和计数器
_print_lock = threading.Lock()
_stats_lock = threading.Lock()
_global_stats = {"success": 0, "failed": 0, "skipped": 0, "total": 0, "results": []}


def safe_print(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


def create_session():
    """创建带重试的 requests session"""
    sess = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    sess.headers.update(HEADERS)
    return sess


def get_local_files_map():
    """扫描本地模型文件"""
    file_map = {}
    for base_dir in [LORAS_DIR, CHECKPOINTS_DIR, DIFFUSION_DIR]:
        if base_dir.exists():
            for f in base_dir.rglob("*"):
                if f.is_file() and f.suffix.lower() in (".safetensors", ".gguf", ".zip", ".json"):
                    file_map[f.name] = str(f)
    return file_map


def get_model_download_url(session, model_id: int, mirror_idx: int = 0) -> tuple:
    """通过 Civitai API 获取模型下载 URL，支持多镜像重试"""
    for attempt in range(len(API_MIRRORS)):
        mirror = API_MIRRORS[(mirror_idx + attempt) % len(API_MIRRORS)]
        url = f"{mirror}/models/{model_id}"
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            model_versions = data.get("modelVersions", [])
            if not model_versions:
                return None, None, f"模型 {model_id} 没有版本信息"
            latest = model_versions[0]
            files = latest.get("files", [])
            if not files:
                return None, None, f"模型 {model_id} 没有可下载文件"
            primary_file = files[0]
            download_url = primary_file.get("downloadUrl", "")
            filename = primary_file.get("name", "")
            file_size = primary_file.get("sizeKB", 0) * 1024
            return download_url, filename, None, file_size
        except requests.RequestException as e:
            if attempt == len(API_MIRRORS) - 1:
                return None, None, str(e), 0
            time.sleep(1)
    return None, None, "所有镜像均失败", 0


def download_file(session, url: str, dest_path: Path, model_name: str, model_index: tuple) -> dict:
    """下载单个文件，支持断点续传"""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    idx, total = model_index

    # 断点续传：检查已有部分
    resume_pos = 0
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")
    if temp_path.exists():
        resume_pos = temp_path.stat().st_size
        safe_print(f"[{idx}/{total}] 🔄 续传: {model_name} (从 {resume_pos/1024/1024:.0f}MB)")

    dl_headers = HEADERS.copy()
    if resume_pos > 0:
        dl_headers["Range"] = f"bytes={resume_pos}-"

    retries = 0
    while retries <= MAX_RETRIES:
        try:
            with session.get(url, headers=dl_headers, stream=True, timeout=600) as resp:
                if resume_pos > 0 and resp.status_code == 206:
                    pass  # Range 请求成功
                elif resume_pos > 0:
                    # 服务器不支持断点续传，从头开始
                    resume_pos = 0
                    dl_headers.pop("Range", None)
                    temp_path.unlink(missing_ok=True)
                    if retries == 0:
                        continue  # 重试一次不带 Range

                resp.raise_for_status()

                # 确定总大小
                content_range = resp.headers.get("Content-Range", "")
                if content_range:
                    total_size = int(content_range.split("/")[-1])
                else:
                    total_size = int(resp.headers.get("Content-Length", 0))

                mode = "ab" if resume_pos > 0 else "wb"
                downloaded = resume_pos
                start_time = time.time()
                last_report = start_time

                with open(temp_path, mode) as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 256):
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.time()
                        if now - last_report > 5 and total_size > 0:
                            elapsed = now - start_time
                            speed = (downloaded - resume_pos) / elapsed / 1024 / 1024 if elapsed > 0 else 0
                            pct = downloaded / total_size * 100
                            safe_print(f"[{idx}/{total}] 📥 {model_name}: {pct:.0f}% ({downloaded/1024/1024:.0f}/{total_size/1024/1024:.0f}MB) {speed:.1f}MB/s")
                            last_report = now

                # 下载完成，重命名
                if dest_path.exists():
                    dest_path.unlink()
                temp_path.rename(dest_path)

                elapsed = time.time() - start_time
                final_speed = (downloaded - resume_pos) / elapsed / 1024 / 1024 if elapsed > 0 else 0
                safe_print(f"[{idx}/{total}] ✅ 完成: {model_name} ({downloaded/1024/1024:.0f}MB, {final_speed:.1f}MB/s)")

                return {"id": idx, "name": model_name, "status": "success", "file": str(dest_path), "size": downloaded}

        except Exception as e:
            retries += 1
            if retries <= MAX_RETRIES:
                safe_print(f"[{idx}/{total}] ⚠ 重试 {retries}/{MAX_RETRIES}: {model_name} - {e}")
                time.sleep(retries * 3)
                # 重新计算续传位置
                if temp_path.exists():
                    resume_pos = temp_path.stat().st_size
                    dl_headers["Range"] = f"bytes={resume_pos}-"
                continue
            else:
                safe_print(f"[{idx}/{total}] ❌ 失败: {model_name} - {e}")
                if temp_path.exists():
                    temp_path.unlink()
                return {"id": idx, "name": model_name, "status": "failed", "error": str(e)}


def process_model(model_info, session, dir_map, args, idx: int, total: int):
    """处理单个模型的完整流程（API 查询 + 下载）"""
    m, dest_path = model_info
    model_id = m["id"]
    model_name = m["name"]

    # 获取下载 URL
    download_url, api_filename, error, file_size = get_model_download_url(session, model_id, mirror_idx=idx % len(API_MIRRORS))
    if error:
        safe_print(f"[{idx}/{total}] ❌ API: {model_name} - {error}")
        with _stats_lock:
            _global_stats["failed"] += 1
            _global_stats["results"].append({"id": model_id, "name": model_name, "status": "api_error", "error": error})
        return

    # 确定目标路径
    actual_filename = api_filename or m["file"]
    dest_dir = dir_map.get(m["dir"], LORAS_DIR)
    actual_dest = dest_dir / actual_filename

    # 检查是否已存在
    if actual_dest.exists() and actual_dest.stat().st_size > 1024:
        safe_print(f"[{idx}/{total}] ⏭ 跳过: {model_name} (已存在)")
        with _stats_lock:
            _global_stats["skipped"] += 1
            _global_stats["results"].append({"id": model_id, "name": model_name, "status": "skipped"})
        return

    # 也检查 .part 文件
    temp_path = actual_dest.with_suffix(actual_dest.suffix + ".part")

    # 下载
    result = download_file(session, download_url, actual_dest, model_name, (idx, total))
    with _stats_lock:
        if result["status"] == "success":
            _global_stats["success"] += 1
        else:
            _global_stats["failed"] += 1
        _global_stats["results"].append(result)


def save_progress():
    pass  # 日志在主函数中统一保存


def main():
    parser = argparse.ArgumentParser(description="批量下载 Civitai NSFW 模型（多线程）")
    parser.add_argument("--dry-run", action="store_true", help="仅检查，不下载")
    parser.add_argument("--limit", type=int, default=0, help="限制下载数量，0=全部")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"并发数 (默认 {MAX_WORKERS})")
    parser.add_argument("--resume", action="store_true", default=True, help="断点续传")
    args = parser.parse_args()

    workers = args.workers

    # 创建工作流目录
    workflows_dir = DOWNLOAD_DIR / "ComfyUI" / "user" / "default" / "workflows" / "downloaded_civitai"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  Civitai NSFW 模型批量下载工具 v2 (多线程并发)")
    print("=" * 70)

    # 扫描本地文件
    local_files = get_local_files_map()
    print(f"\n📁 本地已有模型文件: {len(local_files)} 个")

    # 确定目标目录映射
    dir_map = {
        "loras": LORAS_DIR,
        "checkpoints": CHECKPOINTS_DIR,
        "diffusion_models": DIFFUSION_DIR,
        "workflows": workflows_dir,
    }

    # 过滤需要下载的
    to_download = []
    skipped_existing = []
    for m in MODELS_TO_DOWNLOAD:
        filename = m["file"]
        dest_dir = dir_map.get(m["dir"], LORAS_DIR)
        dest_path = dest_dir / filename

        if dest_path.exists() and dest_path.stat().st_size > 1024:
            skipped_existing.append((m["name"], filename))
            continue

        # 也检查 API 真实文件名
        alt_path = dest_dir / m.get("alt_file", "")
        if alt_path.exists() and alt_path.stat().st_size > 1024:
            skipped_existing.append((m["name"], alt_path.name))
            continue

        to_download.append((m, dest_path))

    total_models = len(MODELS_TO_DOWNLOAD)
    need_download = len(to_download)

    print(f"\n📋 总计模型: {total_models}")
    print(f"⏭ 已存在跳过: {len(skipped_existing)}")
    print(f"⬇ 需要下载: {need_download}")

    if args.limit > 0:
        to_download = to_download[:args.limit]
        print(f"🔢 限制下载: {args.limit} 个")

    if skipped_existing and len(skipped_existing) <= 15:
        print(f"\n--- 跳过的文件 (本地已存在) ---")
        for name, fname in skipped_existing:
            print(f"  ✓ {name} → {fname}")
    elif skipped_existing:
        print(f"\n--- 跳过的前15个文件 ---")
        for name, fname in skipped_existing[:15]:
            print(f"  ✓ {name} → {fname}")
        print(f"  ... 还有 {len(skipped_existing) - 15} 个")

    if not to_download:
        print("\n✅ 所有模型已在本地，无需下载！")
        return

    print(f"\n{'='*70}")
    if args.dry_run:
        print("🔍 DRY RUN 模式 (不实际下载)")
        for m, dest_path in to_download:
            print(f"  → {m['name']} (ID: {m['id']}) → {dest_path}")
        return

    # 统计
    total = len(to_download)
    _global_stats["total"] = total
    start_time = time.time()

    print(f"🚀 开始下载，并发数: {workers}\n")

    # 创建 session (每个线程一个)
    session = create_session()

    # 并发下载
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for i, model_info in enumerate(to_download):
            future = executor.submit(process_model, model_info, session, dir_map, args, i + 1, total)
            futures[future] = i

        # 等待所有完成
        for future in as_completed(futures):
            future.result()  # 获取异常（如果有）

    # 汇总
    elapsed = time.time() - start_time
    hours, rem = divmod(elapsed, 3600)
    minutes, seconds = divmod(rem, 60)

    print(f"\n{'='*70}")
    print(f"📊 下载完成!")
    print(f"  ✅ 成功: {_global_stats['success']}")
    print(f"  ❌ 失败: {_global_stats['failed']}")
    print(f"  ⏭ 跳过: {_global_stats['skipped']}")
    print(f"  ⏱ 耗时: {int(hours)}h {int(minutes)}m {int(seconds)}s")
    if need_download > 0:
        # 计算总下载量
        total_size = sum(
            r.get("size", 0) for r in _global_stats["results"] if r.get("status") == "success"
        )
        if total_size > 0:
            overall_speed = total_size / elapsed / 1024 / 1024 if elapsed > 0 else 0
            print(f"  📦 下载量: {total_size/1024/1024:.0f}MB ({overall_speed:.1f}MB/s 平均)")

    # 保存日志
    log = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_seconds": elapsed,
        "summary": {
            "total": total,
            "success": _global_stats["success"],
            "failed": _global_stats["failed"],
            "skipped": _global_stats["skipped"],
        },
        "results": _global_stats["results"],
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"  📝 日志: {LOG_FILE}")

    # 列出失败项
    failed_items = [r for r in _global_stats["results"] if r.get("status") in ("failed", "api_error")]
    if failed_items:
        print(f"\n--- 失败列表 ---")
        for r in failed_items:
            print(f"  ❌ {r['name']}: {r.get('error', r.get('status', 'unknown'))}")


if __name__ == "__main__":
    main()