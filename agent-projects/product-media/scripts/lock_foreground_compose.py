# -*- coding: utf-8 -*-
"""前景锁定商品图优化器（RMBG-2.0 抠图，绝不重绘主体）。

为什么用它：Flux Kontext 整图重绘会把结构复杂的 SKU（如 F1 赛车的 halo/前后翼/
赞助贴纸）熔化，违反真实性门禁。此脚本只动背景，商品像素始终来自原图。

两种模式（每个 job 用 mode 指定）：
- compose : RMBG 抠出商品 → 程序化影棚渐变背景 → 合成接触阴影（可选倒影）。
            自动去掉所有背景上的营销文字；背景为程序生成，零幻觉（不会冒出多余汽车）。
- detext  : 保留原图，只在指定区域用阈值找到叠加文字并 cv2 inpaint 抹除；
            商品区域用 RMBG mask 保护，绝不被涂改。适合背景本就高级的原图（如 06）。

用法：
    python lock_foreground_compose.py <jobs.json>
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image, ImageFilter
from torchvision import transforms

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

_REPO = Path(__file__).resolve().parents[3]
RMBG_DIR = Path(r"D:\ComfyUI-aki-v3\ComfyUI\models\RMBG\RMBG-2.0")
RUNTIME_ROOT = _REPO / "agent-projects" / "product-media" / "runtime" / "product_image"

_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
_MODEL = None
_TF = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def get_model():
    """直接用 RMBG-2.0 自带 birefnet.py 构图 + 加载 safetensors。

    避开 transformers.from_pretrained 与该版本 transformers 的 BiRefNet 兼容问题
    （all_tied_weights_keys）。
    """
    global _MODEL
    if _MODEL is None:
        import importlib.util
        import types
        from safetensors.torch import load_file

        # birefnet.py 用了相对导入，需以包形式加载
        pkg = types.ModuleType("rmbg2pkg")
        pkg.__path__ = [str(RMBG_DIR)]
        sys.modules["rmbg2pkg"] = pkg
        for sub in ("BiRefNet_config", "birefnet"):
            spec = importlib.util.spec_from_file_location(f"rmbg2pkg.{sub}", str(RMBG_DIR / f"{sub}.py"))
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"rmbg2pkg.{sub}"] = mod
            spec.loader.exec_module(mod)
        BiRefNet = sys.modules["rmbg2pkg.birefnet"].BiRefNet
        BiRefNetConfig = sys.modules["rmbg2pkg.BiRefNet_config"].BiRefNetConfig

        m = BiRefNet(config=BiRefNetConfig(bb_pretrained=False))
        m.load_state_dict(load_file(str(RMBG_DIR / "model.safetensors")))
        m.to(_DEVICE).eval()
        if _DEVICE == "cuda":
            m.half()
        _MODEL = m
    return _MODEL


def predict_alpha(img: Image.Image) -> Image.Image:
    """返回与 img 同尺寸的 L 通道 alpha（商品=白）。"""
    model = get_model()
    x = _TF(img.convert("RGB")).unsqueeze(0).to(_DEVICE)
    if _DEVICE == "cuda":
        x = x.half()
    with torch.no_grad():
        pred = model(x)[-1].sigmoid().float().cpu()[0, 0]
    a = (pred.numpy() * 255).astype(np.uint8)
    return Image.fromarray(a).resize(img.size, Image.LANCZOS)


def refine_alpha(alpha: Image.Image, erode: int = 1, feather: float = 1.0) -> Image.Image:
    """轻微内缩 + 羽化，消除白底来源的亮边。"""
    a = np.array(alpha)
    if erode > 0:
        k = np.ones((erode * 2 + 1, erode * 2 + 1), np.uint8)
        a = cv2.erode(a, k, iterations=1)
    out = Image.fromarray(a)
    if feather > 0:
        out = out.filter(ImageFilter.GaussianBlur(feather))
    return out


# ── 程序化背景 ────────────────────────────────────────────────────────────────
def make_background(size: tuple[int, int], style: str) -> Image.Image:
    w, h = size
    yy = np.linspace(0, 1, h)[:, None]
    xx = np.linspace(0, 1, w)[None, :]
    if style == "studio_dark":
        top, bot = np.array([46, 50, 54]), np.array([16, 17, 20])
        base = top[None, None] * (1 - yy[..., None]) + bot[None, None] * yy[..., None]
        r = np.sqrt((xx - 0.5) ** 2 + (yy - 0.42) ** 2)
        glow = np.clip(1 - r / 0.75, 0, 1)[..., None] * np.array([30, 30, 34])[None, None]
        arr = np.clip(base + glow, 0, 255)
    elif style == "studio_light":
        top, bot = np.array([247, 248, 250]), np.array([214, 217, 221])
        arr = top[None, None] * (1 - yy[..., None]) + bot[None, None] * yy[..., None]
        arr = np.broadcast_to(arr, (h, w, 3)).copy()
    elif style == "studio_red":
        top, bot = np.array([40, 22, 24]), np.array([14, 12, 14])
        base = top[None, None] * (1 - yy[..., None]) + bot[None, None] * yy[..., None]
        r = np.sqrt((xx - 0.5) ** 2 + (yy - 0.4) ** 2)
        glow = np.clip(1 - r / 0.7, 0, 1)[..., None] * np.array([70, 20, 22])[None, None]
        arr = np.clip(base + glow, 0, 255)
    else:
        raise ValueError(f"unknown bg style: {style}")
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def add_contact_shadow(bg: Image.Image, alpha: Image.Image, opacity=0.42, blur=24, squash=0.16, oy=10) -> Image.Image:
    """根据主体轮廓在脚下生成柔和接触阴影。"""
    a = np.array(alpha)
    ys, xs = np.where(a > 30)
    if len(xs) == 0:
        return bg
    x0, x1, y1 = xs.min(), xs.max(), ys.max()
    cx, bw = (x0 + x1) // 2, (x1 - x0)
    sh_h = max(8, int(bw * squash))
    sh = Image.new("L", bg.size, 0)
    arr = np.array(sh)
    cv2.ellipse(arr, (int(cx), int(y1 + oy)), (int(bw * 0.55), sh_h), 0, 0, 360, 255, -1)
    sh = Image.fromarray(arr).filter(ImageFilter.GaussianBlur(blur))
    sh = Image.eval(sh, lambda v: int(v * opacity))
    out = bg.copy()
    black = Image.new("RGB", bg.size, (0, 0, 0))
    out.paste(black, (0, 0), sh)
    return out


def add_reflection(canvas: Image.Image, product: Image.Image, alpha: Image.Image, opacity=0.10, fade=0.45) -> Image.Image:
    a = np.array(alpha)
    ys = np.where(a.max(axis=1) > 30)[0]
    if len(ys) == 0:
        return canvas
    y1 = ys.max()
    refl = product.transpose(Image.FLIP_TOP_BOTTOM)
    refl_a = alpha.transpose(Image.FLIP_TOP_BOTTOM)
    h = refl.size[1]
    grad = np.linspace(opacity, 0, h)[:, None]
    grad = np.clip(grad / max(opacity, 1e-6) * opacity * (np.array(refl_a) / 255.0), 0, 1)
    refl_a2 = Image.fromarray((grad * 255).astype(np.uint8)[: int(h * fade)])
    refl = refl.crop((0, 0, refl.size[0], int(h * fade)))
    canvas.paste(refl, (0, y1), refl_a2)
    return canvas


# ── 文字抹除（保留原背景）────────────────────────────────────────────────────
def detext(img: Image.Image, alpha: Image.Image, regions: list[dict]) -> Image.Image:
    """在指定矩形区域内按阈值找到叠加文字并 inpaint；商品区域(alpha)受保护。"""
    rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = np.zeros((h, w), np.uint8)
    prot = (np.array(alpha) > 40)
    prot = cv2.dilate(prot.astype(np.uint8), np.ones((5, 5), np.uint8))
    for reg in regions:
        x0, y0, x1, y1 = [int(v) for v in reg["box"]]
        sub = np.zeros((h, w), bool)
        sub[y0:y1, x0:x1] = True
        kind = reg.get("kind", "bright")
        if kind == "bright":          # 白字
            hit = (gray > reg.get("thr", 200))
        elif kind == "dark":          # 黑字
            hit = (gray < reg.get("thr", 90))
        elif kind == "red":           # 红 logo
            hit = (hsv[..., 1] > 90) & ((hsv[..., 0] < 12) | (hsv[..., 0] > 168)) & (hsv[..., 2] > 70)
        elif kind == "block":         # 整块直接抹
            hit = np.ones((h, w), bool)
        else:
            hit = np.zeros((h, w), bool)
        mask[sub & hit & (~prot.astype(bool))] = 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=reg.get("dilate", 2) if regions else 2)
    out = cv2.inpaint(rgb, mask, 4, cv2.INPAINT_TELEA)
    return Image.fromarray(out)


# ── 单个 job ──────────────────────────────────────────────────────────────────
def run_job(job: dict, out_dir: Path) -> dict:
    src = Path(job["src"])
    img = Image.open(src).convert("RGB")
    if job.get("crop"):
        img = img.crop(tuple(job["crop"]))
    alpha = refine_alpha(predict_alpha(img), erode=job.get("erode", 1), feather=job.get("feather", 1.0))

    if job["mode"] == "detext":
        result = detext(img, alpha, job["regions"])
    elif job["mode"] == "compose":
        canvas = make_background(img.size, job.get("bg", "studio_dark"))
        canvas = add_contact_shadow(
            canvas, alpha,
            opacity=job.get("shadow_opacity", 0.42),
            blur=job.get("shadow_blur", 24),
            squash=job.get("shadow_squash", 0.16),
            oy=job.get("shadow_oy", 10),
        )
        if job.get("reflection"):
            canvas = add_reflection(canvas, img, alpha, opacity=job.get("refl_opacity", 0.10))
        canvas.paste(img, (0, 0), alpha)
        result = canvas
    else:
        raise ValueError(job["mode"])

    out_path = out_dir / f"{job['name']}.png"
    result.save(out_path)
    # 同时存一张抠图 alpha 供核验
    alpha.save(out_dir / f"{job['name']}__alpha.png")
    return {"name": job["name"], "mode": job["mode"], "src": str(src), "crop": job.get("crop"),
            "bg": job.get("bg"), "out": str(out_path), "size": list(img.size)}


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    batch_dir = RUNTIME_ROOT / spec["batch_id"]
    out_dir = batch_dir / "outputs"
    rec_dir = batch_dir / "records"
    out_dir.mkdir(parents=True, exist_ok=True)
    rec_dir.mkdir(parents=True, exist_ok=True)

    print(f"RMBG device={_DEVICE}; 加载模型…")
    get_model()
    print("模型就绪。")

    results = []
    for job in spec["jobs"]:
        print(f"▸ {job['name']} ({job['mode']}, bg={job.get('bg')})")
        results.append(run_job(job, out_dir))
        print(f"  -> {results[-1]['out']}")

    rec = rec_dir / f"compose_{datetime.now():%Y%m%d_%H%M%S}.json"
    rec.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成 {len(results)} 张；记录 → {rec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
