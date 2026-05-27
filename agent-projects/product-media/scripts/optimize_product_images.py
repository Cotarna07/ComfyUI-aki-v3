# -*- coding: utf-8 -*-
"""商品图优化批量执行器（Flux.1 Kontext 整图编辑）。

设计目标：把"本次处理经验"固化为可复用的批量工具。
- 运行器稳定，作业规格放在独立 JSON（argv[1]），便于迭代提示词/裁切/LoRA。
- 按 class_type 定位节点，避免硬编码节点编号。
- 提交前用 /object_info 校验所需节点类型确实存在（不凭文档猜节点）。
- client_id / extra_data 满足 Queue Manager 可见性（见 comfyui_api_rules.md）。
- 产物与运行记录写入 product-media/runtime/product_image/<batch_id>/。

用法：
    python optimize_product_images.py <jobs.json> [--dry-run]
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import uuid
from datetime import datetime
from pathlib import Path

from PIL import Image

# Windows 控制台默认 GBK，统一切到 UTF-8 以打印中文/符号
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

# ── 共享客户端（agent-projects/comfyui-shared，纯 stdlib）──────────────────────
_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "agent-projects" / "comfyui-shared"))
from comfyui_shared.client import ComfyClient, ComfyClientConfig  # noqa: E402

# ── 固定路径 ──────────────────────────────────────────────────────────────────
WORKFLOW_PATH = _REPO / "agent-skills" / "comfyui" / "workflows" / "api" / "kontext_product_edit.json"
COMFY_INPUT = Path(r"D:\ComfyUI-aki-v3\ComfyUI\input")
COMFY_OUTPUT = Path(r"D:\ComfyUI-aki-v3\ComfyUI\output")
RUNTIME_ROOT = _REPO / "agent-projects" / "product-media" / "runtime" / "product_image"
AGENT_NAME = "claude"
WORKFLOW_NAME = "kontext_product_edit"


def find_node(workflow: dict, class_type: str) -> tuple[str, dict] | tuple[None, None]:
    for nid, node in workflow.items():
        if node.get("class_type") == class_type:
            return nid, node
    return None, None


def latent_size(w: int, h: int, target_long: int = 1024, multiple: int = 16) -> tuple[int, int]:
    """按输入比例缩放到长边≈target_long，并对齐到 multiple 的倍数。"""
    scale = target_long / max(w, h)
    nw = max(multiple, round(w * scale / multiple) * multiple)
    nh = max(multiple, round(h * scale / multiple) * multiple)
    return nw, nh


def stage_input(src: Path, dst_name: str, crop: list[int] | None) -> tuple[str, int, int]:
    """把源图（可选裁切）落到 ComfyUI/input，返回 (文件名, 宽, 高)。"""
    im = Image.open(src).convert("RGB")
    if crop:
        im = im.crop(tuple(crop))  # (left, top, right, bottom)
    dst = COMFY_INPUT / dst_name
    im.save(dst, "PNG")
    return dst_name, im.width, im.height


def inject_lora(workflow: dict, lora_name: str, strength: float) -> None:
    """在 UNETLoader -> KSampler.model 之间插入 LoraLoaderModelOnly。"""
    unet_id, _ = find_node(workflow, "UNETLoader")
    ks_id, ksampler = find_node(workflow, "KSampler")
    if not unet_id or not ks_id:
        raise RuntimeError("找不到 UNETLoader 或 KSampler，无法注入 LoRA")
    new_id = "100"
    workflow[new_id] = {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"model": [unet_id, 0], "lora_name": lora_name, "strength_model": strength},
        "_meta": {"title": "Remove-Text LoRA"},
    }
    ksampler["inputs"]["model"] = [new_id, 0]


def build_workflow(template: dict, job: dict, defaults: dict, input_name: str, w: int, h: int) -> dict:
    wf = copy.deepcopy(template)

    _, load = find_node(wf, "LoadImage")
    load["inputs"]["image"] = input_name

    _, enc = find_node(wf, "CLIPTextEncode")
    enc["inputs"]["text"] = job["prompt"]

    _, guid = find_node(wf, "FluxGuidance")
    guid["inputs"]["guidance"] = job.get("guidance", defaults.get("guidance", 2.8))

    _, ks = find_node(wf, "KSampler")
    ks["inputs"]["seed"] = job["seed"]
    ks["inputs"]["steps"] = job.get("steps", defaults.get("steps", 28))
    ks["inputs"]["cfg"] = defaults.get("cfg", 1.0)
    ks["inputs"]["sampler_name"] = defaults.get("sampler", "euler")
    ks["inputs"]["scheduler"] = defaults.get("scheduler", "simple")
    ks["inputs"]["denoise"] = defaults.get("denoise", 1.0)

    _, lat = find_node(wf, "EmptySD3LatentImage")
    lat["inputs"]["width"] = w
    lat["inputs"]["height"] = h

    _, save = find_node(wf, "SaveImage")
    save["inputs"]["filename_prefix"] = job["_prefix"]

    if job.get("lora"):
        inject_lora(wf, job["lora"]["name"], job["lora"].get("strength", 1.0))

    return wf


def required_class_types(workflow: dict) -> set[str]:
    return {n.get("class_type") for n in workflow.values() if isinstance(n, dict)}


def collect_outputs(history_item: dict, out_dir: Path) -> list[str]:
    saved = []
    for node_output in history_item.get("outputs", {}).values():
        for img in node_output.get("images", []):
            if img.get("type") != "output":
                continue
            src = COMFY_OUTPUT / img.get("subfolder", "") / img["filename"]
            if src.exists():
                dst = out_dir / img["filename"]
                shutil.copy2(src, dst)
                saved.append(str(dst))
    return saved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs_file")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    spec = json.loads(Path(args.jobs_file).read_text(encoding="utf-8"))
    batch_id = spec["batch_id"]
    product_id = spec.get("product_id", "")
    defaults = spec.get("defaults", {})
    jobs = spec["jobs"]

    template = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

    client = ComfyClient(ComfyClientConfig(prompt_timeout_seconds=900))
    stats = client.check_server()
    if not stats.online:
        print(f"[ABORT] ComfyUI 不可达: {stats.error}")
        return 1
    print(f"[OK] ComfyUI {stats.version}  GPU={stats.gpu}  VRAM_free={stats.vram_free_gb}GB")

    # 节点校验（提交前确认所需 class_type 真实存在）
    inv = client.get_node_inventory()
    needed = required_class_types(template) | ({"LoraLoaderModelOnly"} if any(j.get("lora") for j in jobs) else set())
    missing = sorted(t for t in needed if t and t not in inv.node_types)
    if missing:
        print(f"[ABORT] 缺少节点类型: {missing}")
        return 1
    print(f"[OK] 节点校验通过 ({len(needed)} 类型)")

    batch_dir = RUNTIME_ROOT / batch_id
    out_dir = batch_dir / "outputs"
    rec_dir = batch_dir / "records"
    staged_dir = batch_dir / "staged_inputs"
    for d in (out_dir, rec_dir, staged_dir):
        d.mkdir(parents=True, exist_ok=True)

    results = []
    for job in jobs:
        run_id = uuid.uuid4().hex[:8]
        job["_prefix"] = f"product_media/{batch_id}/{job['name']}"
        client_id = f"agent:{AGENT_NAME}|workflow:{WORKFLOW_NAME}|run:{run_id}"

        src = Path(job["src"])
        input_name = f"optsrc_{product_id}_{job['name']}_{run_id}.png"
        input_name, iw, ih = stage_input(src, input_name, job.get("crop"))
        shutil.copy2(COMFY_INPUT / input_name, staged_dir / input_name)

        if job.get("width") and job.get("height"):
            w, h = job["width"], job["height"]
        else:
            w, h = latent_size(iw, ih)

        notes = (
            f"track={job['track']}; product={product_id}; input={src.name}; "
            f"crop={job.get('crop')}; seed={job['seed']}; size={w}x{h}; "
            f"steps={job.get('steps', defaults.get('steps', 28))}; "
            f"guidance={job.get('guidance', defaults.get('guidance', 2.8))}; "
            f"sampler={defaults.get('sampler', 'euler')}/{defaults.get('scheduler', 'simple')}; "
            f"model=flux1-dev-kontext_fp8_scaled; lora={job.get('lora')}; {job.get('notes', '')}"
        )
        extra_data = {
            "agent": AGENT_NAME,
            "workflow_name": WORKFLOW_NAME,
            "source": f"aliexpress/{product_id}",
            "track": job["track"],
            "notes": notes,
        }

        wf = build_workflow(template, job, defaults, input_name, w, h)

        print(f"\n▸ {job['name']}  run={run_id}  size={w}x{h}  seed={job['seed']}  lora={bool(job.get('lora'))}")
        if args.dry_run:
            (rec_dir / f"{job['name']}_{run_id}_DRYRUN.json").write_text(
                json.dumps({"client_id": client_id, "extra_data": extra_data, "workflow": wf}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print("  [DRY-RUN] 已写出工作流，未提交")
            results.append({"name": job["name"], "run_id": run_id, "status": "dry_run", "seed": job["seed"]})
            continue

        try:
            pid = client.submit_prompt(wf, extra_data=extra_data, client_id=client_id)
            print(f"  提交 prompt_id={pid}，等待生成…")
            res = client.wait_for_result(pid)
            saved = collect_outputs(res.history, out_dir) if res.history else []
            status = "completed" if saved else res.status
            print(f"  状态={status}  输出={saved}")
            record = {
                "name": job["name"], "run_id": run_id, "prompt_id": pid, "status": status,
                "client_id": client_id, "seed": job["seed"], "size": [w, h],
                "track": job["track"], "src": str(src), "crop": job.get("crop"),
                "lora": job.get("lora"), "prompt": job["prompt"], "notes": notes,
                "saved_files": saved, "ts": datetime.now().isoformat(),
            }
            (rec_dir / f"{job['name']}_{run_id}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            results.append(record)
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERROR] {exc}")
            results.append({"name": job["name"], "run_id": run_id, "status": "error", "error": str(exc)})

    summary = batch_dir / f"batch_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("status") == "completed")
    print(f"\n完成 {ok}/{len(results)}；摘要 → {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
