# -*- coding: utf-8 -*-
"""Batch test runner for the 2026-05-31 ComfyUI workflow set.

The runner keeps source workflows read-only, converts UI workflows through
ComfyUI, writes patched API jobs to product-media runtime, and can submit the
jobs with Queue Manager-visible metadata.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


REPO = Path(__file__).resolve().parents[3]
COMFY_INPUT = REPO / "ComfyUI" / "input"
COMFY_OUTPUT = REPO / "ComfyUI" / "output"
COMFY_MODELS = REPO / "ComfyUI" / "models"
DEFAULT_WORKFLOW_DIR = REPO / "agent-skills" / "comfyui" / "workflows" / "TEST" / "26-5-31"
DEFAULT_RUNTIME_ROOT = REPO / "agent-projects" / "product-media" / "runtime" / "product_image"
LOCKED_COMPOSE_SCRIPT = REPO / "agent-projects" / "product-media" / "scripts" / "lock_foreground_compose.py"
SCENE_COMPOSE_SCRIPT = REPO / "agent-projects" / "product-media" / "scripts" / "scene_compose.py"
SCENE_VERIFY_SCRIPT = REPO / "agent-projects" / "product-media" / "scripts" / "scene_verify.py"
AGENT_NAME = "codex"

sys.path.insert(0, str(REPO / "agent-projects" / "comfyui-shared"))
from comfyui_shared.client import ComfyClient, ComfyClientConfig  # noqa: E402


def now_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_path(value: str | Path, base: Path = REPO) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def http_json(server: str, method: str, path: str, body: Any | None = None, timeout: int = 120) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(server.rstrip("/") + path, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {path}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach ComfyUI {path}: {exc.reason}") from exc


def convert_workflow(server: str, workflow_path: Path) -> dict[str, Any]:
    workflow = read_json(workflow_path)
    converted = http_json(server, "POST", "/workflow/convert", workflow, timeout=180)
    if not isinstance(converted, dict):
        raise RuntimeError(f"Unexpected /workflow/convert result for {workflow_path.name}: {type(converted)}")
    return converted


def required_class_types(api_graph: dict[str, Any]) -> set[str]:
    return {
        node.get("class_type")
        for node in api_graph.values()
        if isinstance(node, dict) and isinstance(node.get("class_type"), str)
    }


def iter_model_files(*subdirs: str, filename: str) -> list[Path]:
    hits: list[Path] = []
    for subdir in subdirs:
        root = COMFY_MODELS / subdir
        if not root.exists():
            continue
        direct = root / filename
        if direct.exists():
            hits.append(direct)
        hits.extend(root.rglob(filename))
    return sorted(set(hits))


def has_model(*subdirs: str, filename: str) -> bool:
    return bool(iter_model_files(*subdirs, filename=filename))


def model_status(filename: str, subdirs: list[str]) -> dict[str, Any]:
    hits = iter_model_files(*subdirs, filename=filename)
    record = {
        "name": filename,
        "search_dirs": subdirs,
        "present": bool(hits),
        "paths": [display_path(path) for path in hits[:5]],
    }
    if not hits and COMFY_MODELS.exists():
        elsewhere = sorted(COMFY_MODELS.rglob(filename))
        if elsewhere:
            record["found_elsewhere"] = [display_path(path) for path in elsewhere[:5]]
            record["placement_note"] = "Found on disk, but not under the directory type required by this loader."
    return record


def classify_workflow(path: Path, api_graph: dict[str, Any], available_nodes: set[str]) -> dict[str, Any]:
    missing_nodes = sorted(required_class_types(api_graph) - available_nodes)
    name = path.name
    record: dict[str, Any] = {
        "workflow": name,
        "api_node_count": len(api_graph),
        "missing_node_types": missing_nodes,
        "status": "diagnostic",
        "usable_for_product_static": False,
        "notes": [],
        "models": [],
    }

    if name == "image_flux2_klein_image_edit_4b_distilled.json":
        models = [
            model_status("flux-2-klein-4b-fp8.safetensors", ["diffusion_models", "unet"]),
            model_status("qwen_3_4b.safetensors", ["text_encoders", "clip"]),
            model_status("flux2-vae.safetensors", ["vae/FLUX2"]),
        ]
        record["models"] = models
        ready = not missing_nodes and all(item["present"] for item in models)
        record["status"] = "ready" if ready else "blocked"
        record["usable_for_product_static"] = ready
        record["patch_profile"] = "flux2_klein_pruned_fixedvae"
        record["notes"].append(
            "Best current re-render candidate. It must be pruned to SaveImage 9 and patched to FLUX2\\flux2-vae.safetensors."
        )
    elif name == "templates-qwen_image_edit-crop_and_stitch-fusion.json":
        models = [
            model_status("qwen_image_edit_2509_fp8_e4m3fn.safetensors", ["diffusion_models", "unet"]),
            model_status("Qwen-Image-Edit-2509-Fusion.safetensors", ["loras"]),
            model_status("Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors", ["loras"]),
            model_status("qwen_image_vae.safetensors", ["vae", "vae/QWEN"]),
            model_status("qwen_2.5_vl_7b_fp8_scaled.safetensors", ["text_encoders", "text_encoders/QWEN", "clip"]),
        ]
        record["models"] = models
        record["status"] = "blocked" if missing_nodes or not all(item["present"] for item in models[:2]) else "optional"
        record["usable_for_product_static"] = False
        record["notes"].append(
            "Qwen image edit route is optional for later comparison; current local model placement must be fixed before testing."
        )
    elif name == "image_flux2_fp8.json":
        models = [
            model_status("mistral_3_small_flux2_fp8.safetensors", ["text_encoders", "clip"]),
            model_status("flux2_dev_fp8mixed.safetensors", ["diffusion_models", "unet"]),
            model_status("Flux2TurboComfyv2.safetensors", ["loras"]),
        ]
        record["models"] = models
        record["status"] = "blocked"
        record["notes"].append("Flux2 full route is blocked locally by missing model files.")
    elif name.startswith("template_ltx2_3"):
        record["status"] = "blocked" if missing_nodes else "video_only"
        record["usable_for_product_static"] = False
        record["notes"].append("LTX workflows target video subtitle/watermark cleanup, not static product hero image tests.")
    elif name == "gsl_starter_1_3.json":
        record["status"] = "diagnostic"
        record["usable_for_product_static"] = False
        record["notes"].append("Converted API graph is tiny because the main subgraph is bypassed/collapsed; not a ready test route.")
    return record


def preflight(plan: dict[str, Any], batch_dir: Path, server: str) -> dict[str, Any]:
    client = ComfyClient(ComfyClientConfig(server=server, prompt_timeout_seconds=900))
    stats = client.check_server()
    inventory = client.get_node_inventory()
    if not stats.online:
        raise RuntimeError(f"ComfyUI is offline: {stats.error}")
    if not inventory.online:
        raise RuntimeError(f"Cannot read /object_info: {inventory.error}")

    workflow_dir = resolve_path(plan.get("workflow_dir", str(DEFAULT_WORKFLOW_DIR)))
    converted_dir = batch_dir / "api_converted"
    records: list[dict[str, Any]] = []
    available_nodes = set(inventory.node_types)
    for workflow_path in sorted(workflow_dir.glob("*.json")):
        try:
            api_graph = convert_workflow(server, workflow_path)
            write_json(converted_dir / f"{workflow_path.stem}.api.json", api_graph)
            item = classify_workflow(workflow_path, api_graph, available_nodes)
            item["converted_api"] = display_path(converted_dir / f"{workflow_path.stem}.api.json")
        except Exception as exc:
            item = {
                "workflow": workflow_path.name,
                "status": "convert_failed",
                "usable_for_product_static": False,
                "error": str(exc),
            }
        records.append(item)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "server": server,
        "comfyui": {
            "online": stats.online,
            "version": stats.version,
            "gpu": stats.gpu,
            "vram_free_gb": stats.vram_free_gb,
            "vram_total_gb": stats.vram_total_gb,
            "node_type_count": inventory.count,
        },
        "workflow_dir": display_path(workflow_dir),
        "workflows": records,
    }
    write_json(batch_dir / "preflight_report.json", report)
    print(f"[preflight] wrote {display_path(batch_dir / 'preflight_report.json')}")
    return report


def unique_strings(values: list[Any], limit: int = 18) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if isinstance(value, dict):
            text = str(value.get("fact") or value.get("text") or value)
        else:
            text = str(value)
        text = " ".join(text.split())
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def fallback_prompt_plan(product: dict[str, Any], reason: str | None = None) -> dict[str, Any]:
    overrides = product.get("prompt_overrides", {})
    category = product.get("category_hint") or "the product"
    must = unique_strings(overrides.get("must_preserve", []), limit=12)
    if not must:
        must = [
            f"the exact visible {category} identity",
            "all visible parts, colors, materials, accessories, characters, quantities, scale and relative positions",
            "printed details, transparent parts, stickers, packaging marks and product-specific shapes when visible",
        ]
    factual_scene = overrides.get(
        "factual_scene",
        "premium ecommerce studio scene, clean neutral tabletop, soft high-end lighting, natural contact shadow, clear product detail",
    )
    campaign_scene = overrides.get(
        "campaign_scene",
        "premium advertising scene with cinematic but believable lighting and a richer background around the unchanged product",
    )
    forbidden = unique_strings(
        overrides.get("creative_forbidden", [])
        + [
            "adding or removing product parts",
            "changing product structure, color, material, character identity, part count or scale",
            "generating readable text, watermarks, logos, fake packaging or extra products",
        ],
        limit=14,
    )
    return build_prompt_plan(
        product=product,
        identity=str(category),
        must_preserve=must,
        creative_allowed=unique_strings(overrides.get("creative_allowed", []), limit=8),
        creative_forbidden=forbidden,
        warnings=[reason] if reason else [],
        factual_scene=factual_scene,
        campaign_scene=campaign_scene,
        source="fallback",
        raw_reviews=[],
    )


def build_prompt_plan(
    product: dict[str, Any],
    identity: str,
    must_preserve: list[str],
    creative_allowed: list[str],
    creative_forbidden: list[str],
    warnings: list[str],
    factual_scene: str,
    campaign_scene: str,
    source: str,
    raw_reviews: list[dict[str, Any]],
) -> dict[str, Any]:
    product_id = product["product_id"]
    must_text = "; ".join(must_preserve)
    forbidden_text = "; ".join(creative_forbidden)
    factual_prompt = (
        f"Preserve the exact same product from the input image. Product identity: {identity}. "
        f"Must preserve: {must_text}. Edit only the non-product background, floor/tabletop, lighting, "
        f"contact shadow, camera polish and atmosphere into: {factual_scene}. Keep all visible structures, "
        "colors, materials, accessories, quantities, printed/transparent pieces, character positions, scale "
        "and relative positions unchanged. Do not add, remove, redesign, reposition, recolor, change material, "
        f"generate readable text, watermarks, logos, packaging, extra props, extra people or duplicate products. "
        f"Forbidden changes: {forbidden_text}."
    )
    campaign_prompt = (
        f"Create a premium creative campaign image around the same product while preserving the product identity: {identity}. "
        f"Must preserve: {must_text}. Build the scene as: {campaign_scene}. The result is creative_campaign, "
        "not a factual product verification image. Do not imply altered parts are real, and do not invent readable "
        f"product text or fake packaging. Forbidden changes: {forbidden_text}."
    )
    return {
        "product_id": product_id,
        "source": source,
        "identity": identity,
        "must_preserve": must_preserve,
        "creative_allowed": creative_allowed,
        "creative_forbidden": creative_forbidden,
        "warnings": warnings,
        "factual_prompt": factual_prompt,
        "campaign_prompt": campaign_prompt,
        "raw_reviews": raw_reviews,
    }


def merge_vlm_records(product: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    overrides = product.get("prompt_overrides", {})
    parsed_values = [record["parsed"] for record in records if isinstance(record.get("parsed"), dict)]
    identity = ""
    for parsed in parsed_values:
        identity = str(parsed.get("product_identity") or "").strip()
        if identity:
            break
    if not identity:
        identity = str(product.get("category_hint") or product["product_id"])

    must = unique_strings(
        [item for parsed in parsed_values for item in parsed.get("must_preserve", [])]
        + overrides.get("must_preserve", []),
        limit=16,
    )
    if not must:
        must = fallback_prompt_plan(product)["must_preserve"]

    allowed = unique_strings(
        [item for parsed in parsed_values for item in parsed.get("creative_allowed", [])]
        + overrides.get("creative_allowed", []),
        limit=10,
    )
    forbidden = unique_strings(
        [item for parsed in parsed_values for item in parsed.get("creative_forbidden", [])]
        + overrides.get("creative_forbidden", [])
        + [
            "changing product structure, colors, materials, visible quantities, accessories or character relations",
            "inventing readable packaging text, fake logos, fake labels or extra SKU components",
        ],
        limit=16,
    )
    warnings = unique_strings(
        [item for parsed in parsed_values for item in parsed.get("warnings", [])]
        + [record.get("error") for record in records if record.get("error")],
        limit=12,
    )
    return build_prompt_plan(
        product=product,
        identity=identity,
        must_preserve=must,
        creative_allowed=allowed,
        creative_forbidden=forbidden,
        warnings=warnings,
        factual_scene=overrides.get(
            "factual_scene",
            "premium ecommerce studio scene, clean neutral tabletop, soft high-end lighting, natural contact shadow, clear product detail",
        ),
        campaign_scene=overrides.get(
            "campaign_scene",
            "premium advertising scene with richer environment, cinematic lighting and strong visual appeal around the unchanged product",
        ),
        source="vlm",
        raw_reviews=records,
    )


def run_vlm_for_product(product: dict[str, Any], plan: dict[str, Any], batch_dir: Path, refresh: bool) -> dict[str, Any]:
    settings = plan.get("vlm", {})
    prompt_dir = batch_dir / "prompts"
    cache_dir = batch_dir / "vlm"
    prompt_path = prompt_dir / f"{product['product_id']}_prompt_plan.json"
    cache_path = cache_dir / f"{product['product_id']}_{settings.get('backend', 'ollama')}.json"
    if prompt_path.exists() and cache_path.exists() and not refresh:
        return read_json(prompt_path)

    if settings.get("backend", "ollama") != "ollama":
        prompt_plan = fallback_prompt_plan(product, "Only the Ollama VLM backend is wired into this batch runner.")
        write_json(prompt_path, prompt_plan)
        return prompt_plan

    try:
        vlm_root = REPO / "agent-projects" / "product-vlm-review"
        sys.path.insert(0, str(vlm_root))
        from product_vlm_review.ollama_backend import review_with_ollama  # type: ignore
        from product_vlm_review.prompt import build_review_prompt  # type: ignore
        from product_vlm_review.runtime import parse_json_object  # type: ignore
    except Exception as exc:
        prompt_plan = fallback_prompt_plan(product, f"VLM modules unavailable: {exc}")
        write_json(prompt_path, prompt_plan)
        return prompt_plan

    model = settings.get("model", "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M")
    base_url = settings.get("base_url", "http://127.0.0.1:11434")
    timeout = int(settings.get("timeout_seconds", 240))
    image_values = product.get("images") or [product.get("primary_image")]
    images = [resolve_path(value) for value in image_values if value]
    if not images:
        prompt_plan = fallback_prompt_plan(product, "No product images were provided for VLM prompt design.")
        write_json(prompt_path, prompt_plan)
        return prompt_plan

    records: list[dict[str, Any]] = []
    if settings.get("per_image", True):
        for image in images:
            record: dict[str, Any] = {"image": display_path(image), "model": model}
            try:
                raw = review_with_ollama(build_review_prompt([image]), [image], model, base_url, timeout)
                parsed, error = parse_json_object(raw)
                record.update({"raw": raw, "parsed": parsed, "error": error})
            except Exception as exc:
                record.update({"raw": "", "parsed": None, "error": str(exc)})
            records.append(record)
    else:
        record = {"images": [display_path(image) for image in images], "model": model}
        try:
            raw = review_with_ollama(build_review_prompt(images), images, model, base_url, timeout)
            parsed, error = parse_json_object(raw)
            record.update({"raw": raw, "parsed": parsed, "error": error})
        except Exception as exc:
            record.update({"raw": "", "parsed": None, "error": str(exc)})
        records.append(record)

    write_json(cache_path, {"product_id": product["product_id"], "records": records})
    if not any(record.get("parsed") for record in records):
        prompt_plan = fallback_prompt_plan(product, "VLM did not return parseable product facts; used conservative generic prompt.")
    else:
        prompt_plan = merge_vlm_records(product, records)
    write_json(prompt_path, prompt_plan)
    print(f"[vlm] wrote {display_path(prompt_path)}")
    return prompt_plan


def free_comfy_vram(server: str) -> None:
    """让 ComfyUI 卸载已加载模型、释放显存。

    16GB 卡上 ComfyUI 与 Ollama 抢显存：若 ComfyUI 占着显存，Ollama 会把 qwen3-vl
    挤到 CPU 上跑（GPU 利用率几乎为 0，VLM 极慢）。在 VLM 阶段前先让出显存。最佳努力，失败忽略。"""
    try:
        http_json(server, "POST", "/free", {"unload_models": True, "free_memory": True}, timeout=30)
        print("[vram] requested ComfyUI to unload models before VLM stage")
    except Exception as exc:
        print(f"[vram] free request skipped: {exc}")


def build_source_selection_prompt(images: list[Path]) -> str:
    labels = "\n".join(f"- Image-{index}: {image.name}" for index, image in enumerate(images, start=1))
    return (
        "你是电商商品主图筛选助手。下面是同一个速卖通商品的多张列表图，"
        "多数带有营销文字、角标、包装盒或拼接排版。\n"
        "请只根据图片内容，选出最适合做\"商品优化主图原料\"的一张，优先级：\n"
        "1) 商品本体（已组装成品）画面占比大、清晰、完整；"
        "2) 商品本体上没有压字/水印/角标遮挡；"
        "3) 叠加营销文字与拼接排版尽量少，便于抠图或重绘；"
        "4) 单一主体优先，避免以包装盒、规格表、九宫格拼图为主的图。\n"
        f"图片映射：\n{labels}\n"
        "请严格输出一个 JSON 对象：\n"
        "{\n"
        '  "best_image": "Image-N",\n'
        '  "reason": "一句话中文理由",\n'
        '  "scores": [{"image": "Image-1", "product_clarity": 0.0, "overlay_clutter": 0.0, '
        '"is_packaging_or_collage": false, "note": "简述"}],\n'
        '  "ranking": ["Image-N", "..."]\n'
        "}\n"
        "product_clarity 越高表示成品商品越大越清晰；overlay_clutter 越高表示叠加文字/角标越多。"
        "不要输出 Markdown 代码块。"
    )


def make_thumbnail(src: Path, dst_dir: Path, max_side: int = 768) -> Path:
    """把候选图缩到 max_side 长边再喂给 VLM：选源只看构图/遮挡，不需要原分辨率，
    这样能大幅降低图像 token，避免多图 + 长提示撑爆 Ollama 上下文导致空响应。"""
    from PIL import Image  # 本地依赖，lock_foreground_compose 也用

    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{src.stem}.jpg"
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((max_side, max_side), Image.LANCZOS)
            im.save(dst, format="JPEG", quality=85)
        return dst
    except Exception:
        return src


def image_token_to_path(token: Any, images: list[Path]) -> Path | None:
    digits = "".join(ch for ch in str(token or "") if ch.isdigit())
    if not digits:
        return None
    index = int(digits)
    if 1 <= index <= len(images):
        return images[index - 1]
    return None


def select_source_image(product: dict[str, Any], plan: dict[str, Any], batch_dir: Path, refresh: bool) -> dict[str, Any]:
    product_id = product["product_id"]
    cache_path = batch_dir / "source_select" / f"{product_id}.json"
    if cache_path.exists() and not refresh:
        return read_json(cache_path)

    image_values = list(product.get("images") or [])
    if not image_values and product.get("primary_image"):
        image_values = [product["primary_image"]]
    images = [resolve_path(value) for value in image_values if value]
    images = [path for path in images if path.exists()]

    def finish(selected: Path | None, source: str, reason: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        record = {
            "product_id": product_id,
            "selected": display_path(selected) if selected else None,
            "source": source,
            "reason": reason,
            "candidates": [display_path(path) for path in images],
        }
        if extra:
            record.update(extra)
        write_json(cache_path, record)
        print(f"[source] {product_id} -> {record['selected']} ({source})")
        return record

    if not images:
        return finish(None, "none", "没有可读取的候选图片。")
    if len(images) == 1:
        return finish(images[0], "single", "仅有一张候选图片。")

    settings = plan.get("vlm", {})
    backend = settings.get("backend", "ollama")
    if backend != "ollama":
        return finish(images[0], "heuristic", f"未接入 VLM backend {backend}，回退第一张。")

    try:
        vlm_root = REPO / "agent-projects" / "product-vlm-review"
        sys.path.insert(0, str(vlm_root))
        from product_vlm_review.ollama_backend import review_with_ollama  # type: ignore
        from product_vlm_review.runtime import parse_json_object  # type: ignore
    except Exception as exc:
        return finish(images[0], "heuristic", f"VLM 模块不可用（{exc}），回退第一张。")

    model = settings.get("model", "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M")
    base_url = settings.get("base_url", "http://127.0.0.1:11434")
    timeout = int(settings.get("timeout_seconds", 240))
    prompt = build_source_selection_prompt(images)
    # 缩略图喂给 VLM，避免多张大图 + 长 JSON 提示撑爆 Ollama 上下文（会返回空内容）。
    thumb_dir = batch_dir / "source_select" / "_thumbs" / product_id
    thumbs = [make_thumbnail(path, thumb_dir, int(settings.get("select_max_side", 768))) for path in images]
    select_options = {
        "num_ctx": int(settings.get("select_num_ctx", 8192)),
        "num_predict": int(settings.get("select_num_predict", 1200)),
    }
    try:
        raw = review_with_ollama(prompt, thumbs, model, base_url, timeout, options=select_options)
    except Exception as exc:
        return finish(images[0], "heuristic", f"VLM 选源失败（{exc}），回退第一张。")
    parsed, error = parse_json_object(raw)
    chosen = image_token_to_path((parsed or {}).get("best_image"), images) if isinstance(parsed, dict) else None
    extra = {"model": model, "raw": raw, "parsed": parsed, "parse_error": error}
    if chosen is None:
        return finish(images[0], "heuristic", "VLM 未返回可用 best_image，回退第一张。", extra)
    reason = str((parsed or {}).get("reason", "")).strip() or "VLM 选定最清晰的成品主图。"
    return finish(chosen, "vlm", reason, extra)


def resolve_primary_images(plan: dict[str, Any], batch_dir: Path, refresh: bool, force: bool) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for product in plan.get("products", []):
        needs = force or product.get("auto_select_source") or not product.get("primary_image")
        if not needs:
            continue
        record = select_source_image(product, plan, batch_dir, refresh)
        if record.get("selected"):
            product["primary_image"] = record["selected"]
        records[product["product_id"]] = record
    if records:
        write_json(batch_dir / "source_select" / "_summary.json", records)
    return records


def prepare_prompt_plans(plan: dict[str, Any], batch_dir: Path, use_vlm: bool, refresh: bool) -> dict[str, dict[str, Any]]:
    prompt_plans: dict[str, dict[str, Any]] = {}
    for product in plan.get("products", []):
        if use_vlm:
            prompt_plans[product["product_id"]] = run_vlm_for_product(product, plan, batch_dir, refresh)
        else:
            prompt_plan = fallback_prompt_plan(product)
            write_json(batch_dir / "prompts" / f"{product['product_id']}_prompt_plan.json", prompt_plan)
            prompt_plans[product["product_id"]] = prompt_plan
    return prompt_plans


def stage_input_for_comfy(src: Path, batch_id: str, product_id: str) -> str:
    src = src.resolve()
    try:
        rel = src.relative_to(COMFY_INPUT.resolve())
        return rel.as_posix()
    except ValueError:
        digest = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:10]
        dst_dir = COMFY_INPUT / "agent_product_tests" / batch_id / product_id
        dst_dir.mkdir(parents=True, exist_ok=True)
        suffix = src.suffix or ".png"
        dst = dst_dir / f"{src.stem}_{digest}{suffix}"
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        return dst.relative_to(COMFY_INPUT).as_posix()


def dependency_node_ids(api_graph: dict[str, Any], roots: list[str]) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)

    def visit_value(value: Any) -> None:
        if isinstance(value, list):
            if len(value) == 2 and isinstance(value[0], str) and value[0] in api_graph:
                stack.append(value[0])
            else:
                for item in value:
                    visit_value(item)
        elif isinstance(value, dict):
            for item in value.values():
                visit_value(item)

    while stack:
        node_id = stack.pop()
        if node_id in seen or node_id not in api_graph:
            continue
        seen.add(node_id)
        visit_value(api_graph[node_id].get("inputs", {}))
    return seen


def prune_to_roots(api_graph: dict[str, Any], roots: list[str]) -> dict[str, Any]:
    keep = dependency_node_ids(api_graph, roots)
    return {node_id: copy.deepcopy(api_graph[node_id]) for node_id in sorted(keep)}


def set_input(api_graph: dict[str, Any], node_id: str, input_name: str, value: Any) -> None:
    if node_id not in api_graph:
        raise KeyError(f"Missing node {node_id}")
    api_graph[node_id].setdefault("inputs", {})[input_name] = value


def build_flux2_klein_job(
    source_api: dict[str, Any],
    product: dict[str, Any],
    prompt_plan: dict[str, Any],
    batch_id: str,
    workflow: dict[str, Any],
    track: str,
    seed: int,
    job_dir: Path,
) -> dict[str, Any]:
    nodes = workflow.get("nodes", {})
    save_node = str(nodes.get("save_node", "9"))
    load_node = str(nodes.get("load_image_node", "76"))
    prompt_node = str(nodes.get("prompt_node", "75:74"))
    seed_node = str(nodes.get("seed_node", "75:73"))
    vae_node = str(nodes.get("vae_node", "75:72"))
    scheduler_node = str(nodes.get("scheduler_node", "75:62"))

    api_graph = prune_to_roots(source_api, [save_node])
    prompt = prompt_plan["campaign_prompt"] if track == "creative_campaign" else prompt_plan["factual_prompt"]
    product_id = product["product_id"]
    input_path = resolve_path(product.get("primary_image") or product.get("images", [None])[0])
    input_name = stage_input_for_comfy(input_path, batch_id, product_id)
    job_name = f"{product_id}_{workflow['name']}_{track}_s{seed}"
    prefix = f"agent_runs/{batch_id}/{product_id}/{workflow['name']}_{track}_s{seed}"

    set_input(api_graph, load_node, "image", input_name)
    set_input(api_graph, prompt_node, "text", prompt)
    set_input(api_graph, seed_node, "noise_seed", int(seed))
    set_input(api_graph, vae_node, "vae_name", workflow.get("vae_name", "FLUX2\\flux2-vae.safetensors"))
    set_input(api_graph, save_node, "filename_prefix", prefix)
    if "steps" in workflow:
        set_input(api_graph, scheduler_node, "steps", int(workflow["steps"]))
    if "megapixels" in workflow:
        scale_node = str(nodes.get("scale_node", "75:80"))
        set_input(api_graph, scale_node, "megapixels", float(workflow["megapixels"]))

    api_path = job_dir / f"{job_name}.api.json"
    write_json(api_path, api_graph)
    return {
        "job_name": job_name,
        "kind": "comfy_api",
        "workflow_name": workflow["name"],
        "patch_profile": workflow.get("patch_profile"),
        "product_id": product_id,
        "track": track,
        "seed": int(seed),
        "input": display_path(input_path),
        "comfy_input": input_name,
        "api_path": display_path(api_path),
        "filename_prefix": prefix,
        "prompt": prompt,
        "status": "prepared",
    }


def build_locked_jobs(
    product: dict[str, Any],
    workflow: dict[str, Any],
    batch_id: str,
) -> list[dict[str, Any]]:
    product_id = product["product_id"]
    input_path = resolve_path(product.get("primary_image") or product.get("images", [None])[0])
    modes = workflow.get("modes", ["studio_light", "studio_dark"])
    jobs: list[dict[str, Any]] = []
    for mode in modes:
        jobs.append(
            {
                "name": f"{product_id}_locked_{mode}",
                "src": str(input_path),
                "mode": "compose",
                "bg": mode,
                "reflection": bool(workflow.get("reflection", False)),
                "erode": workflow.get("erode", 1),
                "feather": workflow.get("feather", 1.0),
            }
        )
    return jobs


def build_scene_jobs(product: dict[str, Any], workflow: dict[str, Any], batch_id: str) -> list[dict[str, Any]]:
    """从 product["scenes"]（多主题列表）或 product["scene"]（单个）生成 scene_compose 的 job。

    每个 scene 支持 seeds:[...] 多 seed；多主题 × 多 seed 一次出一批供挑图。"""
    scenes = product.get("scenes")
    if not scenes:
        single = product.get("scene")
        scenes = [single] if single else []
    product_id = product["product_id"]
    jobs: list[dict[str, Any]] = []
    for scene in scenes:
        if not scene or not scene.get("prompt"):
            continue
        src = scene.get("src") or product.get("primary_image") or (product.get("images") or [None])[0]
        if not src:
            continue
        seeds = scene.get("seeds") or [scene.get("seed", 70000)]
        tag = scene.get("tag", "sdxl")
        for seed in seeds:
            job = {
                "name": f"{product_id}_scene_{tag}_s{seed}",
                "src": str(resolve_path(src)),
                "scene_prompt": scene["prompt"],
                "main_component_only": bool(scene.get("main_component_only", False)),
                "motion": bool(scene.get("motion", False)),
                "motion_angle": scene.get("motion_angle", 0),
                "motion_strength": scene.get("motion_strength", 21),
                "seed": int(seed),
                "max_side": scene.get("max_side", workflow.get("max_side", 1024)),
            }
            if scene.get("negative"):
                job["negative"] = scene["negative"]
            if scene.get("layout"):
                job["layout"] = scene["layout"]
            jobs.append(job)
    return jobs


def enabled_workflows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [workflow for workflow in plan.get("workflows", []) if workflow.get("enabled", True)]


def prepare_jobs(plan: dict[str, Any], batch_dir: Path, server: str, prompt_plans: dict[str, dict[str, Any]]) -> dict[str, Any]:
    workflow_dir = resolve_path(plan.get("workflow_dir", str(DEFAULT_WORKFLOW_DIR)))
    job_dir = batch_dir / "api_jobs"
    records_dir = batch_dir / "records"
    prepared: list[dict[str, Any]] = []
    locked_jobs: list[dict[str, Any]] = []
    scene_jobs: list[dict[str, Any]] = []
    scene_workflow: dict[str, Any] | None = None
    converted_cache: dict[str, dict[str, Any]] = {}

    for workflow in enabled_workflows(plan):
        workflow_type = workflow.get("type")
        if workflow_type == "builtin_locked_foreground":
            for product in plan.get("products", []):
                locked_jobs.extend(build_locked_jobs(product, workflow, plan["batch_id"]))
            continue

        if workflow_type == "builtin_scene_compose":
            scene_workflow = workflow
            for product in plan.get("products", []):
                scene_jobs.extend(build_scene_jobs(product, workflow, plan["batch_id"]))
            continue

        if workflow_type != "converted_api":
            prepared.append({"workflow_name": workflow.get("name"), "status": "skipped", "reason": f"Unknown type {workflow_type}"})
            continue

        source_path = resolve_path(workflow.get("source", ""), base=workflow_dir)
        if not source_path.exists():
            prepared.append({"workflow_name": workflow.get("name"), "status": "blocked", "reason": f"Missing source {source_path}"})
            continue

        source_key = str(source_path.resolve())
        if source_key not in converted_cache:
            converted_cache[source_key] = convert_workflow(server, source_path)
            write_json(batch_dir / "api_converted" / f"{source_path.stem}.api.json", converted_cache[source_key])
        source_api = converted_cache[source_key]

        if workflow.get("patch_profile") != "flux2_klein_pruned_fixedvae":
            prepared.append(
                {
                    "workflow_name": workflow.get("name"),
                    "status": "skipped",
                    "reason": "No effect-priority patch profile is implemented for this workflow yet.",
                }
            )
            continue

        for product in plan.get("products", []):
            prompt_plan = prompt_plans[product["product_id"]]
            tracks = workflow.get("tracks") or [product.get("track_default", "factual_product")]
            seeds = workflow.get("seeds") or [int(time.time())]
            for track in tracks:
                for seed in seeds:
                    prepared.append(
                        build_flux2_klein_job(source_api, product, prompt_plan, plan["batch_id"], workflow, track, int(seed), job_dir)
                    )

    locked_spec = {"batch_id": plan["batch_id"], "jobs": locked_jobs}
    write_json(records_dir / "locked_foreground_jobs.json", locked_spec)

    if scene_workflow is not None:
        scene_spec = {
            "batch_id": plan["batch_id"],
            "server": server,
            "checkpoint": scene_workflow.get("checkpoint", "SDXL\\juggernautXL_v9Rdphoto2Lightning.safetensors"),
            "steps": scene_workflow.get("steps", 8),
            "cfg": scene_workflow.get("cfg", 2.0),
            "sampler": scene_workflow.get("sampler", "dpmpp_sde"),
            "scheduler": scene_workflow.get("scheduler", "karras"),
            "max_side": scene_workflow.get("max_side", 1024),
            "timeout": scene_workflow.get("timeout", 600),
            "jobs": scene_jobs,
        }
        write_json(records_dir / "scene_jobs.json", scene_spec)

    manifest = {
        "batch_id": plan["batch_id"],
        "prepared_at": datetime.now().isoformat(timespec="seconds"),
        "jobs": prepared,
        "locked_foreground_jobs": locked_jobs,
        "scene_jobs": scene_jobs,
    }
    write_json(batch_dir / "job_manifest.json", manifest)
    print(f"[prepare] wrote {display_path(batch_dir / 'job_manifest.json')}")
    return manifest


def collect_outputs(history_item: dict[str, Any], out_dir: Path, name_prefix: str = "") -> list[str]:
    saved: list[str] = []
    for node_output in history_item.get("outputs", {}).values():
        for image in node_output.get("images", []):
            if image.get("type") != "output":
                continue
            src = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
            if not src.exists():
                continue
            # 不同产品/job 的 SaveImage 会产出同样的 basename（如 *_00001_.png），
            # 平铺到同一 outputs/ 会互相覆盖，故用 job 名做前缀保证唯一。
            dst_name = f"{name_prefix}__{image['filename']}" if name_prefix else image["filename"]
            dst = out_dir / dst_name
            shutil.copy2(src, dst)
            saved.append(display_path(dst))
    return saved


def submit_comfy_jobs(plan: dict[str, Any], batch_dir: Path, server: str, wait: bool, dry_run: bool) -> list[dict[str, Any]]:
    manifest_path = batch_dir / "job_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError("Run prepare before submit.")
    manifest = read_json(manifest_path)
    client = ComfyClient(
        ComfyClientConfig(
            server=server,
            prompt_timeout_seconds=int(plan.get("prompt_timeout_seconds", 1200)),
            poll_interval_seconds=float(plan.get("poll_interval_seconds", 2.0)),
        )
    )
    out_dir = batch_dir / "outputs"
    records_dir = batch_dir / "records"
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for job in manifest.get("jobs", []):
        if job.get("kind") != "comfy_api" or job.get("status") != "prepared":
            continue
        api_path = resolve_path(job["api_path"])
        run_id = uuid.uuid4().hex[:8]
        client_id = f"agent:{AGENT_NAME}|workflow:{job['workflow_name']}|run:{run_id}"
        extra_data = {
            "agent": AGENT_NAME,
            "workflow_name": job["workflow_name"],
            "source_workflow": job.get("patch_profile"),
            "track": job["track"],
            "product_id": job["product_id"],
            "seed": job["seed"],
            "notes": (
                f"batch={plan['batch_id']}; product={job['product_id']}; track={job['track']}; "
                f"input={job['input']}; seed={job['seed']}; prompt={job['prompt']}"
            ),
        }
        record = {
            **job,
            "run_id": run_id,
            "client_id": client_id,
            "extra_data": extra_data,
            "submitted_at": datetime.now().isoformat(timespec="seconds"),
        }
        if dry_run:
            record["status"] = "dry_run_not_submitted"
            results.append(record)
            continue
        prompt_payload = read_json(api_path)
        prompt_id = client.submit_prompt(prompt_payload, extra_data=extra_data, client_id=client_id)
        record["prompt_id"] = prompt_id
        record["status"] = "queued"
        print(f"[submit] {job['job_name']} prompt_id={prompt_id}")
        if wait:
            result = client.wait_for_result(prompt_id)
            record["status"] = result.status
            record["outputs"] = collect_outputs(result.history, out_dir, name_prefix=job["job_name"]) if result.history else []
            print(f"[done] {job['job_name']} status={record['status']} outputs={len(record.get('outputs', []))}")
        results.append(record)
        write_json(records_dir / f"comfy_{job['job_name']}_{run_id}.json", record)

    write_json(records_dir / f"comfy_submit_{now_id()}.json", results)
    return results


def run_locked_foreground(batch_dir: Path, dry_run: bool) -> dict[str, Any]:
    spec_path = batch_dir / "records" / "locked_foreground_jobs.json"
    if not spec_path.exists():
        return {"status": "skipped", "reason": "No locked foreground jobs spec."}
    spec = read_json(spec_path)
    if not spec.get("jobs"):
        return {"status": "skipped", "reason": "No locked foreground jobs enabled."}
    command = [sys.executable, str(LOCKED_COMPOSE_SCRIPT), str(spec_path)]
    record = {"command": command, "job_count": len(spec["jobs"])}
    if dry_run:
        record["status"] = "dry_run_not_run"
        return record
    print(f"[locked] running {len(spec['jobs'])} foreground-lock jobs")
    # 子进程把 stdout 重配为 UTF-8；父进程在 Windows 上默认按 GBK 解码会炸（0xa6），显式指定 UTF-8。
    proc = subprocess.run(
        command, cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    record.update({"status": "completed" if proc.returncode == 0 else "failed", "returncode": proc.returncode})
    record["stdout_tail"] = (proc.stdout or "")[-3000:]
    record["stderr_tail"] = (proc.stderr or "")[-3000:]
    write_json(batch_dir / "records" / f"locked_foreground_{now_id()}.json", record)
    if proc.returncode != 0:
        raise RuntimeError(f"Locked foreground baseline failed: {proc.stderr[-1200:]}")
    return record


def run_scene_compose(batch_dir: Path, dry_run: bool) -> dict[str, Any]:
    spec_path = batch_dir / "records" / "scene_jobs.json"
    if not spec_path.exists():
        return {"status": "skipped", "reason": "No scene jobs spec."}
    spec = read_json(spec_path)
    if not spec.get("jobs"):
        return {"status": "skipped", "reason": "No scene jobs enabled."}
    command = [sys.executable, str(SCENE_COMPOSE_SCRIPT), str(spec_path)]
    record = {"command": command, "job_count": len(spec["jobs"])}
    if dry_run:
        record["status"] = "dry_run_not_run"
        return record
    print(f"[scene] running {len(spec['jobs'])} scene-compose jobs")
    proc = subprocess.run(
        command, cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    record.update({"status": "completed" if proc.returncode == 0 else "failed", "returncode": proc.returncode})
    record["stdout_tail"] = (proc.stdout or "")[-3000:]
    record["stderr_tail"] = (proc.stderr or "")[-3000:]
    write_json(batch_dir / "records" / f"scene_compose_{now_id()}.json", record)
    if proc.returncode != 0:
        raise RuntimeError(f"Scene compose failed: {(proc.stderr or '')[-1200:]}")
    return record


def run_scene_verify(batch_dir: Path, server: str, free_comfy: bool) -> dict[str, Any]:
    spec_path = batch_dir / "records" / "scene_jobs.json"
    if not spec_path.exists():
        return {"status": "skipped", "reason": "No scene jobs spec to verify."}
    if read_json(spec_path).get("jobs") in (None, []):
        return {"status": "skipped", "reason": "No scene jobs to verify."}
    if free_comfy:
        free_comfy_vram(server)  # 让出显存给 Ollama VLM
    command = [sys.executable, str(SCENE_VERIFY_SCRIPT), str(spec_path)]
    print("[verify] running scene fidelity verification (qwen3-vl)")
    proc = subprocess.run(
        command, cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    record = {
        "status": "completed" if proc.returncode == 0 else "failed",
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-3000:],
        "stderr_tail": (proc.stderr or "")[-3000:],
    }
    write_json(batch_dir / "records" / f"scene_verify_{now_id()}.json", record)
    return record


def write_markdown_report(plan: dict[str, Any], batch_dir: Path) -> Path:
    preflight_path = batch_dir / "preflight_report.json"
    manifest_path = batch_dir / "job_manifest.json"
    prompt_dir = batch_dir / "prompts"
    preflight_data = read_json(preflight_path) if preflight_path.exists() else {}
    manifest = read_json(manifest_path) if manifest_path.exists() else {"jobs": [], "locked_foreground_jobs": []}
    lines: list[str] = []
    lines.append(f"# Workflow Effect Test Report - {plan['batch_id']}")
    lines.append("")
    lines.append("## Design Position")
    lines.append("")
    lines.append("- Factual product outputs must preserve the source SKU; better-looking but structurally altered images are failed factual candidates.")
    lines.append("- Locked foreground composition is the factual baseline because product pixels come from the source image.")
    lines.append("- Flux2 Klein is the current ready re-render route; it needs human or VLM-assisted fidelity review before product-page use.")
    lines.append("- Per-product VLM prompt design is necessary when products differ in structure, parts, color, or people/accessory relations; cached prompt plans avoid repeated VLM calls.")
    lines.append("")
    lines.append("## Preflight")
    lines.append("")
    comfy = preflight_data.get("comfyui", {})
    if comfy:
        lines.append(f"- ComfyUI: {comfy.get('version')} | GPU: {comfy.get('gpu')} | VRAM free/total: {comfy.get('vram_free_gb')}/{comfy.get('vram_total_gb')} GB")
    for item in preflight_data.get("workflows", []):
        notes = " ".join(item.get("notes", []))
        lines.append(f"- `{item.get('workflow')}`: {item.get('status')} | missing nodes: {item.get('missing_node_types', [])} | {notes}")
    lines.append("")
    lines.append("## Source Image Selection")
    lines.append("")
    select_dir = batch_dir / "source_select"
    for product in plan.get("products", []):
        select_path = select_dir / f"{product['product_id']}.json"
        if select_path.exists():
            record = read_json(select_path)
            lines.append(
                f"- `{product['product_id']}`: selected={record.get('selected')} "
                f"(via {record.get('source')}) | {record.get('reason', '')}"
            )
        else:
            lines.append(f"- `{product['product_id']}`: primary={product.get('primary_image')} (no selection record)")
    lines.append("")
    lines.append("## Products And Prompt Plans")
    lines.append("")
    for product in plan.get("products", []):
        prompt_path = prompt_dir / f"{product['product_id']}_prompt_plan.json"
        source = "missing"
        warnings: list[str] = []
        if prompt_path.exists():
            prompt_plan = read_json(prompt_path)
            source = prompt_plan.get("source", "")
            warnings = prompt_plan.get("warnings", [])
        lines.append(f"- `{product['product_id']}`: prompt_source={source}; warnings={warnings}")
    lines.append("")
    lines.append("## Prepared Jobs")
    lines.append("")
    for job in manifest.get("locked_foreground_jobs", []):
        lines.append(f"- locked baseline `{job['name']}`: src={display_path(resolve_path(job['src']))}, bg={job.get('bg')}")
    for job in manifest.get("jobs", []):
        lines.append(f"- Comfy `{job.get('job_name')}`: status={job.get('status')}, track={job.get('track')}, seed={job.get('seed')}, api={job.get('api_path')}")
    for job in manifest.get("scene_jobs", []):
        lines.append(f"- scene `{job.get('name')}`: src={display_path(resolve_path(job['src']))}, motion={job.get('motion')}, layout={bool(job.get('layout'))}")
    lines.append("")

    verify_dir = batch_dir / "verify"
    verify_files = sorted(verify_dir.glob("scene_verify_*.json")) if verify_dir.exists() else []
    if verify_files:
        latest: dict[str, dict[str, Any]] = {}
        for vf in verify_files:  # 取每个 name 最新一次的判定
            for rec in read_json(vf):
                latest[rec.get("name", vf.stem)] = rec
        npass = sum(1 for r in latest.values() if r.get("verdict") == "PASS")
        lines.append("## Scene Fidelity Verify (qwen3-vl)")
        lines.append("")
        lines.append(f"- PASS {npass}/{len(latest)} (商品本体对照原图，背景不同不算失败)")
        for name, rec in sorted(latest.items()):
            lines.append(f"- `{name}`: **{rec.get('verdict')}** — {rec.get('reason', '')}")
        lines.append("")

    lines.append("## Fidelity Gate")
    lines.append("")
    lines.append("- Check visible part count, silhouette, color, material, character/accessory identity, relative placement and scale against the source image.")
    lines.append("- Factual candidates fail if any key SKU fact changes, even if the lighting or scene looks stronger.")
    lines.append("- Creative campaign candidates must be labeled as creative and cannot replace factual product verification images.")
    report_path = batch_dir / "report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[report] wrote {display_path(report_path)}")
    return report_path


def build_sample_plan(path: Path) -> dict[str, Any]:
    plan = {
        "batch_id": "workflow_effect_tests_20260531",
        "workflow_dir": "agent-skills/comfyui/workflows/TEST/26-5-31",
        "runtime_root": "agent-projects/product-media/runtime/product_image",
        "server": "http://127.0.0.1:8188",
        "prompt_timeout_seconds": 1200,
        "poll_interval_seconds": 2.0,
        "vlm": {
            "enabled": False,
            "backend": "ollama",
            "model": "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M",
            "base_url": "http://127.0.0.1:11434",
            "per_image": True,
            "timeout_seconds": 240,
        },
        "products": [
            {
                "product_id": "outpost_demo",
                "track_default": "factual_product",
                "category_hint": "LEGO-style outpost building set",
                "primary_image": "ComfyUI/input/agent_tests/product_image_crossset/inputs/outpost.webp",
                "images": ["ComfyUI/input/agent_tests/product_image_crossset/inputs/outpost.webp"],
                "prompt_overrides": {
                    "must_preserve": [
                        "tall outpost tower",
                        "small hut",
                        "horse build",
                        "ladder",
                        "characters, pig and small accessories when visible",
                    ],
                    "factual_scene": "premium ecommerce studio scene with clean neutral tabletop, warm soft morning light and clear contact shadows",
                    "campaign_scene": "warm adventure-themed advertising scene around the unchanged brick-built outpost product",
                },
            },
            {
                "product_id": "racecar_demo",
                "track_default": "factual_product",
                "category_hint": "LEGO-style race car building set",
                "primary_image": "ComfyUI/input/agent_tests/product_image_crossset/inputs/racecar.webp",
                "images": ["ComfyUI/input/agent_tests/product_image_crossset/inputs/racecar.webp"],
                "prompt_overrides": {
                    "must_preserve": [
                        "open-wheel race car silhouette",
                        "front and rear wings",
                        "wheel count and tire placement",
                        "visible driver/minifigure relation when present",
                        "sponsor-like printed details only if already visible",
                    ],
                    "factual_scene": "bright premium tabletop studio with crisp reflections, soft shadows and no added text",
                    "campaign_scene": "dynamic racing showroom advertisement around the unchanged brick-built race car",
                },
            },
        ],
        "workflows": [
            {
                "name": "locked_foreground_baseline",
                "enabled": True,
                "type": "builtin_locked_foreground",
                "modes": ["studio_light", "studio_dark"],
                "reflection": False,
            },
            {
                "name": "flux2_klein_4b",
                "enabled": True,
                "type": "converted_api",
                "source": "image_flux2_klein_image_edit_4b_distilled.json",
                "patch_profile": "flux2_klein_pruned_fixedvae",
                "tracks": ["factual_product"],
                "seeds": [26053102],
                "steps": 4,
                "megapixels": 1.0,
                "vae_name": "FLUX2\\flux2-vae.safetensors",
                "nodes": {
                    "save_node": "9",
                    "load_image_node": "76",
                    "prompt_node": "75:74",
                    "seed_node": "75:73",
                    "vae_node": "75:72",
                    "scheduler_node": "75:62",
                    "scale_node": "75:80",
                },
            },
            {
                "name": "qwen_image_edit_2509_fusion",
                "enabled": False,
                "type": "converted_api",
                "source": "templates-qwen_image_edit-crop_and_stitch-fusion.json",
                "reason_disabled": "Blocked until Qwen Image Edit model, Fusion LoRA and correct model placement are available.",
            },
            {
                "name": "flux2_full_fp8",
                "enabled": False,
                "type": "converted_api",
                "source": "image_flux2_fp8.json",
                "reason_disabled": "Blocked by missing Flux2 full models on this local install.",
            },
        ],
    }
    write_json(path, plan)
    return plan


def load_plan(args: argparse.Namespace) -> tuple[dict[str, Any], Path, str]:
    if not args.plan:
        raise SystemExit("--plan is required unless --init-plan is used.")
    plan_path = resolve_path(args.plan)
    plan = read_json(plan_path)
    runtime_root = resolve_path(plan.get("runtime_root", str(DEFAULT_RUNTIME_ROOT)))
    batch_dir = runtime_root / plan["batch_id"]
    batch_dir.mkdir(parents=True, exist_ok=True)
    server = args.server or plan.get("server", "http://127.0.0.1:8188")
    return plan, batch_dir, server


def run(args: argparse.Namespace) -> int:
    if args.init_plan:
        path = resolve_path(args.init_plan)
        build_sample_plan(path)
        print(f"[init] wrote {display_path(path)}")
        return 0

    plan, batch_dir, server = load_plan(args)
    if args.only:
        wanted = {pid.strip() for pid in args.only.split(",") if pid.strip()}
        kept = [p for p in plan.get("products", []) if p.get("product_id") in wanted]
        missing = wanted - {p.get("product_id") for p in kept}
        if missing:
            raise SystemExit(f"--only 指定的产品不存在: {sorted(missing)}")
        plan["products"] = kept
        print(f"[filter] only products: {[p['product_id'] for p in kept]}")
    stage = args.stage
    use_vlm = bool(args.use_vlm or plan.get("vlm", {}).get("enabled", False))
    if args.skip_vlm:
        use_vlm = False
    prompt_plans: dict[str, dict[str, Any]] = {}

    if stage in {"preflight", "all"}:
        preflight(plan, batch_dir, server)

    will_select = stage in {"select", "vlm", "prepare", "submit", "report", "all"} and not args.no_select_source
    will_prompt_vlm = stage in {"vlm", "prepare", "submit", "report", "all"} and use_vlm
    if (will_select or will_prompt_vlm) and not args.no_free_comfy:
        free_comfy_vram(server)

    if will_select:
        resolve_primary_images(plan, batch_dir, refresh=args.refresh_source, force=args.select_source)

    if stage in {"vlm", "prepare", "submit", "report", "all"}:
        prompt_plans = prepare_prompt_plans(plan, batch_dir, use_vlm=use_vlm, refresh=args.refresh_vlm)

    if stage in {"prepare", "all"}:
        prepare_jobs(plan, batch_dir, server, prompt_plans)

    if stage in {"submit", "all"}:
        if not (batch_dir / "job_manifest.json").exists():
            prepare_jobs(plan, batch_dir, server, prompt_plans)
        locked_record = run_locked_foreground(batch_dir, dry_run=args.dry_run or args.skip_locked)
        write_json(batch_dir / "records" / f"locked_foreground_submit_{now_id()}.json", locked_record)
        if not args.skip_comfy:
            submit_comfy_jobs(plan, batch_dir, server, wait=not args.no_wait, dry_run=args.dry_run)
        if not args.skip_scene:
            scene_record = run_scene_compose(batch_dir, dry_run=args.dry_run or args.skip_scene)
            write_json(batch_dir / "records" / f"scene_compose_submit_{now_id()}.json", scene_record)

    if stage in {"verify", "all"} and not args.skip_verify:
        verify_record = run_scene_verify(batch_dir, server, free_comfy=not args.no_free_comfy)
        write_json(batch_dir / "records" / f"scene_verify_submit_{now_id()}.json", verify_record)

    if stage in {"report", "all"}:
        write_markdown_report(plan, batch_dir)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and run product-image workflow effect tests for 26-5-31 workflows.")
    parser.add_argument("--plan", help="Test plan JSON.")
    parser.add_argument("--init-plan", help="Write a starter plan JSON and exit.")
    parser.add_argument("--stage", choices=["preflight", "select", "vlm", "prepare", "submit", "verify", "report", "all"], default="all")
    parser.add_argument("--server", help="Override ComfyUI server URL.")
    parser.add_argument("--use-vlm", action="store_true", help="Generate per-product prompt plans with the configured VLM.")
    parser.add_argument("--skip-vlm", action="store_true", help="Force conservative non-VLM prompt plans.")
    parser.add_argument("--refresh-vlm", action="store_true", help="Ignore cached VLM prompt plans.")
    parser.add_argument("--select-source", action="store_true", help="Force VLM source-image selection even when primary_image is pinned.")
    parser.add_argument("--no-select-source", action="store_true", help="Disable VLM source-image selection; use pinned primary_image as-is.")
    parser.add_argument("--refresh-source", action="store_true", help="Ignore cached source-image selection results.")
    parser.add_argument("--dry-run", action="store_true", help="Prepare records but do not run foreground lock or submit ComfyUI jobs.")
    parser.add_argument("--no-wait", action="store_true", help="Queue ComfyUI jobs and exit without polling for outputs.")
    parser.add_argument("--skip-locked", action="store_true", help="Do not run the locked-foreground baseline during submit/all.")
    parser.add_argument("--skip-comfy", action="store_true", help="Do not submit ComfyUI (flux2) jobs during submit/all; locked baseline only.")
    parser.add_argument("--skip-scene", action="store_true", help="Do not run scene_compose (SDXL themed-scene) jobs during submit/all.")
    parser.add_argument("--skip-verify", action="store_true", help="Do not run qwen3-vl scene fidelity verification during verify/all.")
    parser.add_argument("--only", help="Comma-separated product_ids to keep; run a small subset batch.")
    parser.add_argument("--no-free-comfy", action="store_true", help="Do not ask ComfyUI to free VRAM before VLM stages.")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
