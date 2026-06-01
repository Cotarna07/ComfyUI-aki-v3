# -*- coding: utf-8 -*-
"""场景图真实性二次验收（qwen3-vl 对照原图核验商品事实）。

为什么需要：scene_compose 已把原商品像素贴回，理论上零漂移；但抠图边缘、运动模糊
渗透、丢件等仍可能出问题。本脚本用 VLM 对照"原始商品图 vs 生成场景图"，只判商品本体
是否一致（背景/氛围不同不算失败），给出 PASS/FAIL，便于批量初筛。

用法：
    python scene_verify.py <scene_jobs.json>   # 复用 scene 任务里的 name/src 映射
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

_REPO = Path(__file__).resolve().parents[3]
RUNTIME_ROOT = _REPO / "agent-projects" / "product-media" / "runtime" / "product_image"

sys.path.insert(0, str(_REPO / "agent-projects" / "product-vlm-review"))
from product_vlm_review.ollama_backend import review_with_ollama  # noqa: E402
from product_vlm_review.runtime import parse_json_object  # noqa: E402

MODEL = "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M"
BASE_URL = "http://127.0.0.1:11434"

PROMPT = (
    "Image-1 是原始商品图，Image-2 是生成的场景广告图。"
    "请只对比【商品本体】的事实一致性：结构/轮廓、颜色、材质、可见配件与数量、"
    "人物/配件关系、印刷与贴纸、比例。背景、场景、光影、氛围不同都【允许】，不算失败。"
    "严格输出一个 JSON 对象，不要 Markdown：\n"
    '{"product_consistent": true/false, '
    '"changes": ["商品本体出现的不一致点（如有）"], '
    '"verdict": "PASS" 或 "FAIL", '
    '"reason": "一句话中文理由"}\n'
    "只要商品本体与原图一致就 PASS；若商品结构/颜色/配件/数量被改或多出/缺少部件则 FAIL。"
)


def thumb(path: Path, tmp_dir: Path, max_side: int = 768) -> Path:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dst = tmp_dir / f"{path.stem}_{abs(hash(str(path))) % 10000}.jpg"
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side), Image.LANCZOS)
            im.save(dst, "JPEG", quality=88)
        return dst
    except Exception:
        return path


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    batch_dir = RUNTIME_ROOT / spec["batch_id"]
    out_dir = batch_dir / "outputs"
    tmp_dir = batch_dir / "verify" / "_thumbs"
    results = []
    for job in spec.get("jobs", []):
        name = job["name"]
        src = Path(job["src"])
        gen = out_dir / f"{name}.png"
        rec = {"name": name, "src": str(src), "output": str(gen)}
        if not gen.exists():
            rec.update({"verdict": "MISSING", "reason": "scene output not found"})
            results.append(rec)
            print(f"  {name}: MISSING")
            continue
        try:
            imgs = [thumb(src, tmp_dir), thumb(gen, tmp_dir)]
            raw = review_with_ollama(PROMPT, imgs, MODEL, BASE_URL, 240, options={"num_ctx": 8192, "num_predict": 700})
            parsed, err = parse_json_object(raw)
            if isinstance(parsed, dict):
                rec.update({
                    "verdict": str(parsed.get("verdict", "?")).upper(),
                    "product_consistent": parsed.get("product_consistent"),
                    "changes": parsed.get("changes", []),
                    "reason": parsed.get("reason", ""),
                })
            else:
                rec.update({"verdict": "PARSE_ERROR", "reason": err, "raw": raw[:400]})
        except Exception as exc:
            rec.update({"verdict": "ERROR", "reason": str(exc)})
        results.append(rec)
        print(f"  {name}: {rec.get('verdict')} - {rec.get('reason', '')[:60]}")

    rec_path = batch_dir / "verify" / f"scene_verify_{datetime.now():%Y%m%d_%H%M%S}.json"
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    npass = sum(1 for r in results if r.get("verdict") == "PASS")
    print(f"\nPASS {npass}/{len(results)}；记录 → {rec_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
