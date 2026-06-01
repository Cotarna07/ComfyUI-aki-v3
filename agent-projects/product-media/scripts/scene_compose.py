# -*- coding: utf-8 -*-
"""场景化商品图生成（抠图锁定 + SDXL 背景重绘 + 贴回原商品）。

为什么这么做：整图重绘（flux2-klein）会改坏 SKU（加人偶、虚构包装）。本脚本只让
扩散模型重绘"背景区域"，商品区域用 RMBG mask 锁住，最后把原商品像素羽化贴回，
保证商品零漂移，同时给它一个贴合主题的真实场景（市区飞驰的警车、赛道赛车、
我的世界苦力怕等）。

链路：
  RMBG → 商品 alpha → 背景 mask（商品取反）→ ComfyUI SDXL VAEEncodeForInpaint
  只重绘背景 → 取回生成图 → 背景层可选运动模糊 → 贴回原商品（侵蚀+羽化）→ 接触阴影。

用法：
    python scene_compose.py <jobs.json>
jobs.json: {"batch_id": "...", "server": "http://127.0.0.1:8188",
            "checkpoint": "SDXL\\juggernautXL_v9Rdphoto2Lightning.safetensors",
            "jobs": [{"name","src","scene_prompt","negative"?, "motion"?, "motion_angle"?,
                      "seed"?, "steps"?, "cfg"?, "sampler"?, "scheduler"?, "max_side"?}]}
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

_REPO = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO / "agent-projects" / "product-media" / "scripts"
RUNTIME_ROOT = _REPO / "agent-projects" / "product-media" / "runtime" / "product_image"
COMFY_INPUT = _REPO / "ComfyUI" / "input"
COMFY_OUTPUT = _REPO / "ComfyUI" / "output"
AGENT_NAME = "claude"

# 复用 lock_foreground_compose 的 RMBG 抠图与接触阴影，避免重复加载/实现
sys.path.insert(0, str(_SCRIPTS))
import lock_foreground_compose as lf  # noqa: E402

sys.path.insert(0, str(_REPO / "agent-projects" / "comfyui-shared"))
from comfyui_shared.client import ComfyClient, ComfyClientConfig  # noqa: E402

DEFAULT_NEG = (
    "extra toys, duplicate product, second car, miniatures, people, extra figures, "
    "text, words, watermark, logo, signboard, low quality, blurry, deformed, jpeg artifacts, clutter"
)


def keep_largest_component(alpha: Image.Image, thr: int = 40) -> Image.Image:
    """只保留最大连通主体，丢掉悬浮的拆解小件、单独的人偶等。

    用于拆解演示图（如警车把车顶件悬浮展示）：避免把漂浮件也放进场景里像 UFO。"""
    a = np.array(alpha)
    binary = (a > thr).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n <= 2:
        return alpha
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    out = np.where(labels == largest, a, 0).astype(np.uint8)
    return Image.fromarray(out)


def fit_size(size: tuple[int, int], max_side: int) -> tuple[int, int]:
    """缩放到长边 max_side 且对齐到 8 的倍数（SDXL 友好）。"""
    w, h = size
    scale = max_side / max(w, h)
    nw, nh = max(8, round(w * scale)), max(8, round(h * scale))
    nw -= nw % 8
    nh -= nh % 8
    return nw, nh


def aspect_canvas(aspect: str, max_side: int) -> tuple[int, int]:
    """按宽高比给出对齐到 8 的画布尺寸（长边=max_side）。aspect 形如 '4:5' / '16:9' / '1:1'。"""
    try:
        rw, rh = (float(v) for v in str(aspect).split(":"))
    except Exception:
        rw = rh = 1.0
    if rw >= rh:
        cw, ch = max_side, round(max_side * rh / rw)
    else:
        ch, cw = max_side, round(max_side * rw / rh)
    cw -= cw % 8
    ch -= ch % 8
    return max(8, cw), max(8, ch)


def place_on_canvas(
    prod_rgb: Image.Image, prod_alpha: Image.Image, canvas_size: tuple[int, int],
    product_scale: float, anchor: str, margin: float = 0.06, bg_gray: int = 127,
) -> tuple[Image.Image, Image.Image]:
    """把商品紧致裁剪后按比例/锚点摆到中性灰画布上，返回 (画布RGB, 画布alpha)。

    用于构图控制：商品占比、放在下方/居中/留出标题空间，背景随后由 SDXL 重绘。"""
    a = np.array(prod_alpha)
    ys, xs = np.where(a > 20)
    if len(xs) == 0:
        return prod_rgb, prod_alpha
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    pr = prod_rgb.crop((x0, y0, x1 + 1, y1 + 1))
    pa = prod_alpha.crop((x0, y0, x1 + 1, y1 + 1))
    cw, ch = canvas_size
    pw, ph = pr.size
    s = (product_scale * ch) / ph
    if pw * s > (1 - 2 * margin) * cw:  # 不要超出画布宽度
        s = (1 - 2 * margin) * cw / pw
    nw, nh = max(1, round(pw * s)), max(1, round(ph * s))
    pr = pr.resize((nw, nh), Image.LANCZOS)
    pa = pa.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (cw, ch), (bg_gray, bg_gray, bg_gray))
    cal = Image.new("L", (cw, ch), 0)
    m = round(margin * ch)
    if "bottom" in anchor:
        py = ch - nh - m
    elif "top" in anchor:
        py = m
    else:
        py = (ch - nh) // 2
    if "left" in anchor:
        px = round(margin * cw)
    elif "right" in anchor:
        px = cw - nw - round(margin * cw)
    else:
        px = (cw - nw) // 2
    canvas.paste(pr, (px, py), pa)
    cal.paste(pa, (px, py))
    return canvas, cal


def build_inpaint_graph(
    checkpoint: str,
    image_name: str,
    mask_name: str,
    positive: str,
    negative: str,
    seed: int,
    steps: int,
    cfg: float,
    sampler: str,
    scheduler: str,
    grow_mask_by: int,
    filename_prefix: str,
) -> dict:
    """SDXL 背景重绘 API 图：mask 白=重绘背景，商品区域(黑)由原图 latent 保留。"""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "5": {"class_type": "LoadImageMask", "inputs": {"image": mask_name, "channel": "red"}},
        "6": {
            "class_type": "VAEEncodeForInpaint",
            "inputs": {"pixels": ["4", 0], "vae": ["1", 2], "mask": ["5", 0], "grow_mask_by": grow_mask_by},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["6", 0],
                "seed": int(seed),
                "steps": int(steps),
                "cfg": float(cfg),
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": 1.0,
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": filename_prefix}},
    }


def fetch_output_image(history: dict) -> Image.Image | None:
    for node_output in (history or {}).get("outputs", {}).values():
        for image in node_output.get("images", []):
            if image.get("type") != "output":
                continue
            src = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
            if src.exists():
                return Image.open(src).convert("RGB")
    return None


def motion_blur_background(scene: Image.Image, alpha: Image.Image, angle_deg: float, strength: int) -> Image.Image:
    """只对背景做方向性运动模糊，商品区域保持清晰，营造'飞驰'速度感。"""
    if strength < 3:
        return scene
    arr = np.array(scene)
    k = np.zeros((strength, strength), np.float32)
    k[strength // 2, :] = 1.0
    M = cv2.getRotationMatrix2D((strength / 2 - 0.5, strength / 2 - 0.5), angle_deg, 1.0)
    k = cv2.warpAffine(k, M, (strength, strength))
    s = k.sum()
    k = k / s if s > 0 else k
    blurred = cv2.filter2D(arr, -1, k)
    a = (np.array(alpha).astype(np.float32) / 255.0)[..., None]  # 商品=1
    a = np.clip(a * 1.0, 0, 1)
    out = blurred * (1 - a) + arr * a
    return Image.fromarray(out.astype(np.uint8))


def run_job(job: dict, spec: dict, client: ComfyClient, out_dir: Path) -> dict:
    src = Path(job["src"])
    img = Image.open(src).convert("RGB")
    if job.get("crop"):
        img = img.crop(tuple(job["crop"]))

    max_side = int(job.get("max_side", spec.get("max_side", 1024)))
    target = fit_size(img.size, max_side)
    img = img.resize(target, Image.LANCZOS)

    raw_alpha = lf.predict_alpha(img)
    if job.get("main_component_only"):
        raw_alpha = keep_largest_component(raw_alpha)
    alpha = lf.refine_alpha(raw_alpha, erode=job.get("erode", 1), feather=job.get("feather", 1.5))

    # 构图控制：把商品重新摆到指定宽高比/占比/锚点的画布上（留标题空间等）
    layout = job.get("layout")
    if layout:
        canvas_size = aspect_canvas(layout.get("aspect", "1:1"), max_side)
        img, alpha = place_on_canvas(
            img, alpha, canvas_size,
            product_scale=float(layout.get("product_scale", 0.7)),
            anchor=layout.get("anchor", "bottom-center"),
            margin=float(layout.get("margin", 0.06)),
        )

    bg_mask = Image.fromarray(255 - np.array(alpha))  # 背景=白=重绘

    run_id = uuid.uuid4().hex[:8]
    stem = f"{job['name']}_{run_id}"
    img_name = f"agent_scene_{stem}.png"
    mask_name = f"agent_scene_{stem}_bgmask.png"
    (COMFY_INPUT).mkdir(parents=True, exist_ok=True)
    img.save(COMFY_INPUT / img_name)
    bg_mask.save(COMFY_INPUT / mask_name)

    checkpoint = job.get("checkpoint", spec.get("checkpoint", "SDXL\\juggernautXL_v9Rdphoto2Lightning.safetensors"))
    graph = build_inpaint_graph(
        checkpoint=checkpoint,
        image_name=img_name,
        mask_name=mask_name,
        positive=job["scene_prompt"],
        negative=job.get("negative") or DEFAULT_NEG,
        seed=int(job.get("seed", 12345)),
        steps=int(job.get("steps", spec.get("steps", 8))),
        cfg=float(job.get("cfg", spec.get("cfg", 2.0))),
        sampler=job.get("sampler", spec.get("sampler", "dpmpp_sde")),
        scheduler=job.get("scheduler", spec.get("scheduler", "karras")),
        grow_mask_by=int(job.get("grow_mask_by", 12)),
        filename_prefix=f"agent_scene/{spec['batch_id']}/{job['name']}",
    )

    client_id = f"agent:{AGENT_NAME}|workflow:scene_compose|run:{run_id}"
    extra_data = {
        "agent": AGENT_NAME,
        "workflow_name": "scene_compose_sdxl_bg_inpaint",
        "source": "agent-projects/product-media/scripts/scene_compose.py",
        "notes": f"batch={spec['batch_id']}; job={job['name']}; src={src}; scene={job['scene_prompt'][:120]}",
    }
    print(f"▸ submit {job['name']} (seed={job.get('seed', 12345)})")
    prompt_id = client.submit_prompt(graph, extra_data=extra_data, client_id=client_id)
    result = client.wait_for_result(prompt_id)
    scene = fetch_output_image(result.history) if result.history else None
    if scene is None:
        return {"name": job["name"], "status": "failed", "reason": "no output image", "prompt_id": prompt_id}
    scene = scene.resize(img.size, Image.LANCZOS)

    # 运动模糊只作用于背景
    if job.get("motion"):
        scene = motion_blur_background(scene, alpha, float(job.get("motion_angle", 0.0)), int(job.get("motion_strength", 21)))

    # 贴回原商品（再侵蚀一点，避免重绘渗入商品边缘）+ 接触阴影
    paste_alpha = lf.refine_alpha(alpha, erode=job.get("paste_erode", 2), feather=job.get("paste_feather", 1.2))
    scene = lf.add_contact_shadow(scene, paste_alpha, opacity=job.get("shadow_opacity", 0.35),
                                  blur=job.get("shadow_blur", 22), squash=job.get("shadow_squash", 0.16))
    scene.paste(img, (0, 0), paste_alpha)

    out_path = out_dir / f"{job['name']}.png"
    scene.save(out_path)
    alpha.save(out_dir / f"{job['name']}__alpha.png")
    print(f"  -> {out_path}")
    return {"name": job["name"], "status": "ok", "out": str(out_path), "prompt_id": prompt_id,
            "src": str(src), "scene_prompt": job["scene_prompt"], "size": list(img.size)}


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    batch_dir = RUNTIME_ROOT / spec["batch_id"]
    out_dir = batch_dir / "outputs"
    rec_dir = batch_dir / "records"
    out_dir.mkdir(parents=True, exist_ok=True)
    rec_dir.mkdir(parents=True, exist_ok=True)

    server = spec.get("server", "http://127.0.0.1:8188")
    client = ComfyClient(ComfyClientConfig(server=server, prompt_timeout_seconds=int(spec.get("timeout", 600))))
    print(f"RMBG device={lf._DEVICE}; 加载模型…")
    lf.get_model()
    print("模型就绪。")

    results = []
    for job in spec["jobs"]:
        results.append(run_job(job, spec, client, out_dir))

    rec = rec_dir / f"scene_compose_{datetime.now():%Y%m%d_%H%M%S}.json"
    rec.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r.get("status") == "ok")
    print(f"\n完成 {ok}/{len(results)} 张；记录 → {rec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
