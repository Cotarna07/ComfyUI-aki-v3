# -*- coding: utf-8 -*-
"""Build evidence-grounded product-image briefs with a local vision model.

The VLM is used as a director and risk detector, never as the sole approval
gate for factual e-commerce imagery. Source photos provide product evidence;
style references can guide campaign mood but cannot establish SKU facts.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(r"D:\ComfyUI-aki-v3")
DEFAULT_MODEL = "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M"
DEFAULT_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_RUNTIME_ROOT = (
    ROOT / "agent-skills" / "comfyui" / "runtime" / "product_campaign_director_20260527"
)
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze product views and plan evidence-grounded campaign images."
    )
    parser.add_argument("--product-dir", type=Path, required=True)
    parser.add_argument("--product-id", help="Defaults to the product directory name.")
    parser.add_argument(
        "--style-reference",
        action="append",
        type=Path,
        default=[],
        help="Existing creative image used only as visual direction, repeatable.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def encode_image(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return base64.b64encode(path.read_bytes()).decode("ascii")


def ask_json(
    url: str,
    model: str,
    prompt: str,
    images: list[Path],
    num_predict: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [encode_image(path) for path in images],
            }
        ],
        "stream": False,
        "format": "json",
        "keep_alive": 0,
        "options": {"temperature": 0, "num_predict": num_predict, "num_ctx": 8192},
    }
    response = requests.post(url, json=payload, timeout=1200)
    response.raise_for_status()
    content = response.json()["message"]["content"]
    return json.loads(content)


def collect_source_images(product_dir: Path) -> list[Path]:
    images = [
        path
        for path in sorted(product_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if not images:
        raise ValueError(f"No product images found under {product_dir}")
    return images


def evidence_prompt(filename: str) -> str:
    return f"""
You are extracting auditable product facts from one source sales image named {filename}.
Answer in Chinese as strict JSON only. Inspect visible evidence, not assumptions.
Required keys:
- source_file: exactly "{filename}"
- evidence_role: one of standalone_product_view, packaging_reference, dimension_reference, unclear
- product_category: string
- view_orientation: string
- visible_configuration: string
- minifigure_or_accessory_state: array of visible item/state strings
- removable_or_exploded_parts: array of visible detached/floating/removal demonstrations, empty if none
- fixed_identity_features: array of visible product features worth preserving
- product_surface_marks: array of markings visibly printed on the toy itself, empty if none
- catalog_or_packaging_facts: array of brand/item/age/piece/dimension facts shown outside the toy
- seller_overlay_text_not_product: array of sales slogans or page graphics not part of the toy
- suitable_factual_uses: array
- uncertainty: array
Pay special attention to whether a character is outside the vehicle or seated inside it, and
whether a roof/lightbar module is installed or visibly detached/floating above the vehicle.
Packaging artwork can support catalog verification but is not by itself a direct photograph of
the physical item. Do not treat seller overlay copy as product identity. Do not claim authenticity
or infer unseen assembly states.
""".strip()


def analyze_evidence(
    source_images: list[Path],
    url: str,
    model: str,
) -> list[dict[str, Any]]:
    evidence = []
    for source in source_images:
        evidence.append(
            ask_json(url, model, evidence_prompt(source.name), [source], num_predict=1200)
        )
        print(f"Evidence analyzed: {source.name}")
    return evidence


def style_prompt(reference_names: list[str]) -> str:
    return f"""
You are studying creative benchmark images for a product campaign. The supplied images are
creative outputs named in order: {', '.join(reference_names)}.
Do not infer factual SKU content from them. Return compact strict Chinese JSON with:
- strengths_to_emulate: array of visual design strengths
- camera_and_scale_patterns: array
- lighting_and_environment_patterns: array
- typography_strategy: array
- product_fidelity_risks: array of visual changes that must be checked against source photos
Keep each array concise and evidence-based.
""".strip()


def analyze_style(
    style_references: list[Path],
    url: str,
    model: str,
) -> dict[str, Any]:
    if not style_references:
        return {
            "strengths_to_emulate": [],
            "camera_and_scale_patterns": [],
            "lighting_and_environment_patterns": [],
            "typography_strategy": [],
            "product_fidelity_risks": [],
        }
    return ask_json(
        url,
        model,
        style_prompt([path.name for path in style_references]),
        style_references,
        num_predict=1800,
    )


def plan_prompt(
    product_id: str,
    evidence: list[dict[str, Any]],
    style_analysis: dict[str, Any],
) -> str:
    return f"""
You are the visual director for an e-commerce product-image workflow.
Product id: {product_id}

Here is source-photo evidence extracted independently from the original sales images:
{json.dumps(evidence, ensure_ascii=False, indent=2)}

Here is a style-only analysis of creative benchmark images. It must not override source evidence:
{json.dumps(style_analysis, ensure_ascii=False, indent=2)}

Design a practical workflow that uses a VLM for analysis and an image-editing model for rendering.
Return strict Chinese JSON with these keys:
- product_identity_manifest: object with confirmed_constants, configuration_variants, uncertain_items
- fixed_workflow_stages: array of objects with stage, model_role, input, output, rejection_rule
- shot_briefs: exactly four objects, with ids:
  rain_city_assembled_outside, rain_city_feature_exploded_inside,
  catalog_factual_clean, specification_layout_post
  Each brief must contain track (factual_product or creative_campaign), base_source_files,
  evidence_basis, render_mode (image_edit or deterministic_post),
  source_orientation_preserved (boolean), composition, editable_regions, do_not_change,
  generation_prompt_en, overlay_text_strategy, validation_checks.
- generator_model_requirements: array
- vlm_limitations: array

Rules:
1. `factual_product` may only use a product configuration visibly evidenced in a named original
   source file. Combining evidence from different configurations is not factual unless explicitly
   downgraded to creative_campaign.
2. For `factual_product`, preserve the same camera orientation, item positions, crop logic and
   assembled/detached state from its chosen source photograph. Background cleaning, a modest
   support surface and contact shadows are allowed; a new camera angle is forbidden.
3. Packaging artwork or dimensions may be reused as original pixels or typeset after verification;
   never ask an image model to invent or rerender a product box for factual delivery.
4. Rainy cinematic street lighting, reflections, bokeh and rim light may be creative edits.
5. Exact title/specification text should be typeset deterministically after image generation, not
   entrusted to the diffusion/image-editing model.
6. State clearly when an exploded roof or a seated police figure is already supported by source evidence.
7. In a creative shot, do not propose changing minifigure face, product surface text, part counts
   or construction as an editable region. Those remain validation targets.
8. `rain_city_feature_exploded_inside` must use an original source that visibly proves both the
   seated-inside character and detached/floating roof/lightbar state.
9. `catalog_factual_clean` must use a standalone product photograph rather than packaging artwork.
10. `specification_layout_post` must use render_mode `deterministic_post`; its packaging pixels
    and verified type are laid out without generative rerendering.
11. The VLM may plan and flag risks, but final factual approval remains manual.
""".strip()


def build_plan(
    product_id: str,
    evidence: list[dict[str, Any]],
    style_analysis: dict[str, Any],
    url: str,
    model: str,
) -> dict[str, Any]:
    return ask_json(
        url,
        model,
        plan_prompt(product_id, evidence, style_analysis),
        [],
        num_predict=6000,
    )


def evidence_text(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False).lower()


def find_catalog_warnings(evidence: list[dict[str, Any]]) -> list[str]:
    piece_values: dict[str, list[str]] = {}
    for item in evidence:
        for fact in item.get("catalog_or_packaging_facts", []):
            lowered = str(fact).lower()
            if not any(term in lowered for term in ("piece", "pcs", "零件", "件数")):
                continue
            for value in re.findall(r"\d+", lowered):
                piece_values.setdefault(value, []).append(str(item.get("source_file", "")))
    if len(piece_values) <= 1:
        return []
    rendered = "; ".join(
        f"{value} ({', '.join(sources)})" for value, sources in sorted(piece_values.items())
    )
    return [f"VLM 对件数读取得到冲突值：{rendered}；排版前必须人工核对原图。"]


def validate_plan(plan: dict[str, Any], evidence: list[dict[str, Any]]) -> list[str]:
    evidence_by_source = {
        str(item.get("source_file", "")): item for item in evidence if item.get("source_file")
    }
    errors: list[str] = []
    shots = {shot.get("id"): shot for shot in plan.get("shot_briefs", [])}
    expected_shots = {
        "rain_city_assembled_outside",
        "rain_city_feature_exploded_inside",
        "catalog_factual_clean",
        "specification_layout_post",
    }
    missing = sorted(expected_shots - set(shots))
    if missing:
        errors.append(f"Missing required shot briefs: {', '.join(missing)}")
    for shot_id, shot in shots.items():
        sources = shot.get("base_source_files", [])
        missing_sources = [source for source in sources if source not in evidence_by_source]
        if missing_sources:
            errors.append(f"{shot_id}: unknown source files {missing_sources}")
            continue
        source_evidence = [evidence_by_source[source] for source in sources]
        if shot.get("track") == "factual_product" and shot_id != "specification_layout_post":
            if any(
                item.get("evidence_role") != "standalone_product_view"
                for item in source_evidence
            ):
                errors.append(
                    f"{shot_id}: factual image_edit must start from standalone product imagery"
                )
            if shot.get("source_orientation_preserved") is not True:
                errors.append(f"{shot_id}: factual track must preserve source orientation")
        if shot_id == "rain_city_feature_exploded_inside":
            supports_configuration = False
            for item in source_evidence:
                text = evidence_text(item)
                has_inside = any(term in text for term in ("inside", "车内", "驾驶座", "坐在"))
                has_detached = bool(item.get("removable_or_exploded_parts"))
                if has_inside and has_detached:
                    supports_configuration = True
            if not supports_configuration:
                errors.append(
                    f"{shot_id}: selected source does not prove both seated figure and detached roof/lightbar"
                )
        if shot_id == "catalog_factual_clean" and shot.get("render_mode") != "image_edit":
            errors.append(f"{shot_id}: must be an image_edit based on a standalone source")
        if shot_id == "specification_layout_post":
            if shot.get("render_mode") != "deterministic_post":
                errors.append(
                    f"{shot_id}: specification/packaging layout must be deterministic_post"
                )
    return errors


def repair_prompt(
    product_id: str,
    evidence: list[dict[str, Any]],
    style_analysis: dict[str, Any],
    rejected_plan: dict[str, Any],
    errors: list[str],
) -> str:
    return f"""
Repair an unsafe product campaign plan. Return the full strict JSON plan using the same schema as
the rejected plan; do not include commentary.
Product id: {product_id}
Source evidence:
{json.dumps(evidence, ensure_ascii=False, indent=2)}
Style-only direction:
{json.dumps(style_analysis, ensure_ascii=False, indent=2)}
Rejected plan:
{json.dumps(rejected_plan, ensure_ascii=False, indent=2)}
Deterministic gate failures:
{json.dumps(errors, ensure_ascii=False, indent=2)}

Required repairs:
- Use the original view that proves a seated police figure and a detached/floating roof/lightbar
  for `rain_city_feature_exploded_inside`.
- Use a standalone source product photograph for `catalog_factual_clean`, preserve its exact
  orientation and arrangement, and set render_mode to `image_edit`.
- Set `specification_layout_post` to render_mode `deterministic_post`; do not ask a generator to
  redraw packaging or type.
- Keep title/spec facts as deterministic verified overlays only.
- Never add a value contradicted by, or not reliably readable from, the supplied source evidence.
""".strip()


def build_validated_plan(
    product_id: str,
    evidence: list[dict[str, Any]],
    style_analysis: dict[str, Any],
    url: str,
    model: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    warnings = find_catalog_warnings(evidence)
    plan = build_plan(product_id, evidence, style_analysis, url, model)
    errors = validate_plan(plan, evidence)
    attempts = 1
    if errors:
        print("Plan rejected by deterministic gate; requesting one repair.")
        plan = ask_json(
            url,
            model,
            repair_prompt(product_id, evidence, style_analysis, plan, errors),
            [],
            num_predict=6000,
        )
        attempts += 1
        errors = validate_plan(plan, evidence)
    validation = {
        "passed": not errors,
        "attempts": attempts,
        "errors": errors,
        "warnings": warnings,
        "requires_manual_catalog_verification": bool(warnings),
        "note": "Passing this structural gate does not approve factual publication.",
    }
    return plan, validation


def render_report(
    product_id: str,
    source_images: list[Path],
    style_references: list[Path],
    evidence: list[dict[str, Any]],
    style_analysis: dict[str, Any],
    plan: dict[str, Any],
    plan_validation: dict[str, Any],
    model: str,
) -> str:
    lines = [
        f"# 商品视觉导演测试记录：{product_id}",
        "",
        f"- 生成时间：`{datetime.now():%Y-%m-%d %H:%M:%S}`",
        f"- 视觉分析模型：`{model}`（本地 Ollama）",
        "- 使用边界：VLM 用于读取证据、规划镜头和提出风险，不能单独批准真实商品图发布。",
        f"- 原始证据图：{', '.join(f'`{path.name}`' for path in source_images)}",
    ]
    if style_references:
        lines.append(
            "- 风格参照图："
            + ", ".join(f"`{path.name}`" for path in style_references)
            + "（仅作广告视觉参考）"
        )
    lines.extend(["", "## 逐图证据", ""])
    for item in evidence:
        lines.append(f"### {item.get('source_file', 'unknown')}")
        lines.append("")
        lines.append(f"- 角色/附件状态：{'; '.join(item.get('minifigure_or_accessory_state', []))}")
        detached = item.get("removable_or_exploded_parts", [])
        lines.append(f"- 拆解或可拆结构：{'; '.join(detached) if detached else '未见明确拆解状态'}")
        lines.append(f"- 用途：{'; '.join(item.get('suitable_factual_uses', []))}")
        lines.append("")
    lines.extend(["## 网页端风格拆解", ""])
    for strength in style_analysis.get("strengths_to_emulate", []):
        lines.append(f"- {strength}")
    lines.append("")
    lines.extend(["## 镜头方案", ""])
    for brief in plan.get("shot_briefs", []):
        lines.append(f"### {brief.get('id', 'shot')} (`{brief.get('track', 'unknown')}`)")
        lines.append("")
        lines.append(f"- 源图依据：{', '.join(brief.get('base_source_files', []))}")
        lines.append(f"- 构图：{brief.get('composition', '')}")
        lines.append(f"- 文案方式：{brief.get('overlay_text_strategy', '')}")
        lines.append("")
    lines.extend(["## 程序门禁", ""])
    lines.append(f"- 镜头方案结构校验：{'通过' if plan_validation.get('passed') else '失败'}")
    lines.append(f"- 规划尝试次数：`{plan_validation.get('attempts', 0)}`")
    for error in plan_validation.get("errors", []):
        lines.append(f"- 拒绝原因：{error}")
    for warning in plan_validation.get("warnings", []):
        lines.append(f"- 人工核验警告：{warning}")
    lines.append("")
    lines.extend(
        [
            "## 重要边界",
            "",
            "- 能从原图证据证明的人物位置或拆解状态，可进入对应保真候选分支。",
            "- 未由同一源图证明的配置组合，只能作为创意广告候选，不能冒充真实展示图。",
            "- 标题、件数、年龄与货号应后期排版并回查包装证据，不由生成模型自由书写。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    product_id = args.product_id or args.product_dir.name
    source_images = collect_source_images(args.product_dir)
    for reference in args.style_reference:
        if not reference.is_file():
            raise FileNotFoundError(reference)
    output_dir = args.output_dir or (DEFAULT_RUNTIME_ROOT / product_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    evidence = analyze_evidence(source_images, args.url, args.model)
    style_analysis = analyze_style(args.style_reference, args.url, args.model)
    print("Creative style references analyzed.")
    plan, plan_validation = build_validated_plan(
        product_id, evidence, style_analysis, args.url, args.model
    )
    payload = {
        "product_id": product_id,
        "source_images": [str(path) for path in source_images],
        "style_references": [str(path) for path in args.style_reference],
        "model": args.model,
        "diagnostic_only": True,
        "evidence": evidence,
        "style_analysis": style_analysis,
        "plan": plan,
        "plan_validation": plan_validation,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    json_path = output_dir / "director_manifest.json"
    report_path = output_dir / "director_report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(
        render_report(
            product_id,
            source_images,
            args.style_reference,
            evidence,
            style_analysis,
            plan,
            plan_validation,
            args.model,
        ),
        encoding="utf-8",
    )
    print(f"Manifest: {json_path}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
