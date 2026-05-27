# -*- coding: utf-8 -*-
"""
Kontext 产品图优化批量处理脚本
依据 agent-skills/comfyui/skills/comfyui-product-image-integrity/SKILL.md
轨道: factual_product（真实商品展示）
"""

import json
import os
import sys
import time
import uuid
import shutil
import requests
import random
from pathlib import Path
from datetime import datetime

# ─── 配置 ───────────────────────────────────────────
COMFYUI_URL = "http://127.0.0.1:8188"
WORKFLOW_PATH = Path(__file__).resolve().parent.parent.parent.parent / "comfyui" / "workflows" / "api" / "kontext_product_edit.json"
COMFYUI_INPUT = Path(r"D:\ComfyUI-aki-v3\ComfyUI\input")
COMFYUI_OUTPUT = Path(r"D:\ComfyUI-aki-v3\ComfyUI\output")
RUNTIME_DIR = Path(__file__).resolve().parent.parent.parent / "runtime" / "product_image_optimizer"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

# 产品目录列表
PRODUCT_DIRS = [
    r"Y:\tiktok_ins_crawl\aliexpress\images\1005010410824249",
    r"Y:\tiktok_ins_crawl\aliexpress\images\1005010739958948",
    r"Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323",
    r"Y:\tiktok_ins_crawl\aliexpress\images\1005008273906722",
    r"Y:\tiktok_ins_crawl\aliexpress\images\1005009067934624",
]

# ─── 提示词模板（factual_product 轨道）───────────────
FACTUAL_PROMPT = """Preserve the identical building block / brick toy military vehicle as shown: keep the exact silhouette, brick structure, color distribution, all connected components, weapon accessories, tire count, turret shape, and relative positioning of every part. The product must remain instantly recognizable as the same brick-built toy set.

Edit only the background and lighting: replace the white studio background with a subtle product showcase environment — a clean slightly reflective dark grey platform surface with soft gradient background, gentle top-down studio lighting with warm highlights, and realistic grounded contact shadows beneath the vehicle.

Keep the product bright, sharp, and clearly brick/plastic-built. Every stud, brick edge, and connection point must remain fully visible and inspectable. Do not blur or overexpose any structural detail.

Do NOT add, remove, redesign, reposition, recolor, or change material of any component. Do NOT generate text, logos, packaging, watermarks, or spec labels. Do NOT transform the brick toy into a real military vehicle or any other material. Do NOT change the number of tires, weapons, turrets, or structural modules."""

# ─── 工具函数 ────────────────────────────────────────
def load_workflow(path: Path) -> dict:
    """加载 API 工作流 JSON"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_node_by_type(workflow: dict, node_type: str) -> dict | None:
    """在 workflow 中查找指定类型的节点"""
    for node in workflow["nodes"]:
        if node["type"] == node_type:
            return node
    return None


def update_workflow(workflow: dict, input_image_path: str, prompt: str, output_prefix: str, seed: int, width: int = 1024, height: int = 1024):
    """修改工作流参数"""
    # 更新 LoadImage 节点的图片路径
    loader = find_node_by_type(workflow, "LoadImage")
    if loader:
        loader["widgets_values"][0] = input_image_path

    # 更新 CLIPTextEncode 的提示词
    encoder = find_node_by_type(workflow, "CLIPTextEncode")
    if encoder:
        encoder["widgets_values"][0] = prompt

    # 更新 SaveImage 的输出前缀
    saver = find_node_by_type(workflow, "SaveImage")
    if saver:
        saver["widgets_values"][0] = output_prefix

    # 更新 KSampler 的 seed
    sampler = find_node_by_type(workflow, "KSampler")
    if sampler:
        sampler["widgets_values"][0] = seed

    # 更新 EmptyFlux2LatentImage 的尺寸
    empty_latent = find_node_by_type(workflow, "EmptyFlux2LatentImage")
    if empty_latent:
        empty_latent["widgets_values"][0] = width
        empty_latent["widgets_values"][1] = height


def submit_prompt(workflow: dict, client_id: str) -> dict:
    """提交工作流到 ComfyUI API"""
    payload = {
        "prompt": workflow,
        "client_id": client_id,
        "extra_data": {
            "agent": "copilot",
            "workflow_name": "kontext_product_edit",
            "source": "aliexpress_product_optimizer",
            "notes": ""
        }
    }
    r = requests.post(f"{COMFYUI_URL}/prompt", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def get_history(prompt_id: str) -> dict:
    """获取任务历史"""
    r = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=30)
    r.raise_for_status()
    return r.json()


def wait_for_completion(prompt_id: str, timeout: int = 600) -> dict | None:
    """轮询等待任务完成"""
    start = time.time()
    while time.time() - start < timeout:
        history = get_history(prompt_id)
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(3)
    return None


def copy_input_image(src_path: str, product_id: str, img_file: str) -> str:
    """将输入图片复制到 ComfyUI input 目录"""
    src = Path(src_path) / img_file
    dst_name = f"product_{product_id}_{img_file}"
    dst = COMFYUI_INPUT / dst_name
    shutil.copy2(src, dst)
    print(f"  已复制: {src} → {dst}")
    return dst_name


def save_output_files(history_entry: dict, product_id: str, run_id: str):
    """保存输出文件到 runtime 目录"""
    output_dir = RUNTIME_DIR / product_id / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for node_id, node_output in history_entry.get("outputs", {}).items():
        for img_info in node_output.get("images", []):
            src = COMFYUI_OUTPUT / img_info["subfolder"] / img_info["filename"]
            dst = output_dir / img_info["filename"]
            if src.exists():
                shutil.copy2(src, dst)
                saved.append(str(dst))
                print(f"  已保存: {dst}")
    return saved


def process_product(product_dir: str, workflow_template: dict, dry_run: bool = False) -> list[dict]:
    """处理单个产品的所有图片"""
    product_id = Path(product_dir).name
    results = []

    # 获取该产品目录下的所有图片（排除 Thumbs.db）
    img_extensions = (".jpg", ".jpeg", ".png", ".webp")
    images = sorted([
        f for f in os.listdir(product_dir)
        if f.lower().endswith(img_extensions) and not f.startswith("Thumbs")
    ])

    print(f"\n{'='*60}")
    print(f"产品: {product_id} ({len(images)} 张图片)")
    print(f"{'='*60}")

    for img_file in images:
        run_id = uuid.uuid4().hex[:8]
        client_id = f"agent:copilot|workflow:kontext_product_edit|run:{run_id}"
        output_prefix = f"product_optimized/{product_id}"

        print(f"\n  ▸ {img_file} (run: {run_id})")

        # 复制输入图片
        input_name = copy_input_image(product_dir, product_id, img_file)

        # 深拷贝工作流模板并修改
        workflow = json.loads(json.dumps(workflow_template))
        seed = random.randint(0, 2**31 - 1)

        update_workflow(
            workflow,
            input_image_path=input_name,
            prompt=FACTUAL_PROMPT,
            output_prefix=output_prefix,
            seed=seed
        )

        # 更新 extra_data
        workflow["extra_data"] = {
            "agent": "copilot",
            "workflow_name": "kontext_product_edit",
            "source": f"aliexpress/{product_id}",
            "notes": f"factual_product; seed={seed}; steps=28; guidance=2.8; sampler=euler; scheduler=simple; model=flux1-dev-kontext_fp8_scaled; input={img_file}"
        }

        if dry_run:
            print(f"  [DRY RUN] seed={seed}, 将提交但跳过执行")
            results.append({"product_id": product_id, "img_file": img_file, "run_id": run_id, "seed": seed, "status": "dry_run"})
            continue

        try:
            # 提交任务
            result = submit_prompt(workflow, client_id)
            prompt_id = result.get("prompt_id")
            if not prompt_id:
                print(f"  ✗ 提交失败: {result}")
                results.append({"product_id": product_id, "img_file": img_file, "run_id": run_id, "seed": seed, "status": "submit_failed"})
                continue

            print(f"  ✓ 已提交: prompt_id={prompt_id}, seed={seed}")

            # 等待完成
            print(f"  ⏳ 等待生成...")
            history = wait_for_completion(prompt_id, timeout=600)

            if history is None:
                print(f"  ✗ 超时")
                results.append({"product_id": product_id, "img_file": img_file, "run_id": run_id, "seed": seed, "prompt_id": prompt_id, "status": "timeout"})
                continue

            # 检查状态
            status = history.get("status", {})
            if status.get("completed", False):
                print(f"  ✓ 生成完成")
                saved = save_output_files(history, product_id, run_id)
                results.append({
                    "product_id": product_id, "img_file": img_file, "run_id": run_id,
                    "seed": seed, "prompt_id": prompt_id, "status": "completed",
                    "saved_files": saved
                })
            else:
                print(f"  ✗ 状态异常: {status}")
                results.append({"product_id": product_id, "img_file": img_file, "run_id": run_id, "seed": seed, "prompt_id": prompt_id, "status": "failed", "status_detail": status})

        except Exception as e:
            print(f"  ✗ 异常: {e}")
            results.append({"product_id": product_id, "img_file": img_file, "run_id": run_id, "seed": seed, "status": "error", "error": str(e)})

    return results


def main():
    print("=" * 60)
    print("Kontext 产品图优化 - 批量处理")
    print(f"时间: {datetime.now().isoformat()}")
    print(f"轨道: factual_product")
    print(f"模型: flux1-dev-kontext_fp8_scaled (FP8)")
    print(f"参数: steps=28, guidance=2.8, sampler=euler, scheduler=simple")
    print("=" * 60)

    # 检查 ComfyUI 连通性
    try:
        r = requests.get(f"{COMFYUI_URL}/system_stats", timeout=5)
        stats = r.json()
        print(f"\nComfyUI 状态: ✓ 运行中 (GPU: {stats.get('system', {}).get('gpu', 'N/A')})")
    except Exception as e:
        print(f"\nComfyUI 不可达: {e}")
        print("请先启动 ComfyUI 服务")
        sys.exit(1)

    # 加载工作流模板
    workflow_template = load_workflow(WORKFLOW_PATH)
    print(f"工作流模板: ✓ 已加载 ({WORKFLOW_PATH})")

    # 确认
    print(f"\n即将处理 {len(PRODUCT_DIRS)} 个产品")
    print("提示词预览:")
    print("-" * 40)
    print(FACTUAL_PROMPT[:200] + "...")
    print("-" * 40)

    # 逐个处理产品
    all_results = []
    for i, product_dir in enumerate(PRODUCT_DIRS):
        if not Path(product_dir).exists():
            print(f"\n⚠ 跳过不存在的目录: {product_dir}")
            continue

        # 只处理第一张图片（01.jpg/png）做快速测试
        results = process_product(product_dir, workflow_template, dry_run=False)
        all_results.extend(results)

    # 保存结果摘要
    summary_path = RUNTIME_DIR / f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n结果摘要已保存: {summary_path}")

    # 汇总
    completed = [r for r in all_results if r["status"] == "completed"]
    failed = [r for r in all_results if r["status"] != "completed"]
    print(f"\n{'='*60}")
    print(f"处理完成: {len(completed)} 成功, {len(failed)} 失败")
    for r in completed:
        print(f"  ✓ {r['product_id']}/{r['img_file']} → {r.get('saved_files', [])}")
    for r in failed:
        print(f"  ✗ {r['product_id']}/{r['img_file']} → {r['status']}")


if __name__ == "__main__":
    main()
