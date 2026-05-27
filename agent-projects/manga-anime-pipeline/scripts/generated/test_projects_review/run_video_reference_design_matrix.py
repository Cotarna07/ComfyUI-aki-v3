from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = PROJECT_ROOT.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageDraw, ImageFont

from pipeline.comfy.client import ComfyClient, ComfyClientConfig
from pipeline.comfy.provenance import write_output_provenance_files
from pipeline.common.io import read_json, write_json


RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "2026-05-15_test_projects_short_manga"
REVIEW_DIR = RUNTIME_ROOT / "review"
DEFAULT_PROMPT_PACK = REVIEW_DIR / "optimized_prompt_pack.json"
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "tests" / "Test_projects"
DEFAULT_OUTPUT_ROOT = REVIEW_DIR / "video_reference_design_matrix"
COMFY_OUTPUT_ROOT = WORKSPACE_ROOT / "ComfyUI" / "output"
REQUIRED_NODES = {
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
}


@dataclass(frozen=True)
class CheckpointCase:
    ckpt_name: str
    label: str


@dataclass(frozen=True)
class WorkflowVariant:
    variant_id: str
    label: str
    purpose: str
    positive_suffix: str
    negative_suffix: str
    width: int
    height: int
    steps: int
    cfg: float
    sampler: str = "euler"
    scheduler: str = "normal"


CHECKPOINT_CASES = [
    CheckpointCase("waiIllustriousSDXL_v170.safetensors", "waiIllustriousSDXL_v170"),
    CheckpointCase("animagineXLV31_v31.safetensors", "animagineXLV31_v31"),
    CheckpointCase("hassakuXLIllustrious_v34.safetensors", "hassakuXLIllustrious_v34"),
    CheckpointCase("Illustrious-XL-v0.1.safetensors", "Illustrious-XL-v0_1"),
]

WORKFLOW_VARIANTS = [
    WorkflowVariant(
        variant_id="video_identity_fullbody",
        label="视频身份锚点全身图",
        purpose="先测试角色发色、发型、校服、身高气质是否稳定，作为 I2V 首帧或 LoRA 参考图候选。",
        positive_suffix=(
            "anime production character reference, solo full body, front view, natural standing pose, "
            "clean readable silhouette, accurate teenage proportions, camera-ready image-to-video reference, "
            "plain warm gray studio background, no text, no speech bubbles, no watermark"
        ),
        negative_suffix=(
            "childlike redesign, chibi, super deformed, toddler face, oversized head, toy-like body, "
            "extra character, speech bubble, new text, logo, watermark, busy background"
        ),
        width=832,
        height=1216,
        steps=22,
        cfg=6.4,
    ),
    WorkflowVariant(
        variant_id="video_story_keyframe",
        label="趣味短视频首帧",
        purpose="测试更有内容的单人首帧：保留角色身份，同时给后续短视频模型一个可动的情绪和动作起点。",
        positive_suffix=(
            "single-character anime keyframe for a light comedy school short video, dynamic three-quarter pose, "
            "expressive face, subtle motion potential, clean hands, slight hair motion, soft pastel lighting, "
            "simple classroom or school corridor background, no readable text, no speech bubbles"
        ),
        negative_suffix=(
            "static doll pose, empty expression, stiff body, heavy action blur, extra person, duplicate body, "
            "unreadable text, new subtitles, speech bubble, crowded background"
        ),
        width=1024,
        height=1024,
        steps=20,
        cfg=6.8,
    ),
    WorkflowVariant(
        variant_id="expression_reference_sheet",
        label="表情与动画参考小设定",
        purpose="测试角色脸和表情稳定性，帮助判断后续表情驱动、口型或动作镜头是否容易漂。",
        positive_suffix=(
            "clean anime model sheet, one main full body character plus two small expression bust callouts, "
            "same identity in every callout, smile and surprised expression, production design sheet, "
            "clear school uniform details, no labels, no typography, plain neutral background"
        ),
        negative_suffix=(
            "different identities in callouts, two different girls, crowd, chibi, low age impression, "
            "generated text, captions, speech bubble, watermark, messy layout"
        ),
        width=1024,
        height=1280,
        steps=24,
        cfg=7.1,
    ),
]

BASE_NEGATIVE = (
    "worst quality, low quality, lowres, blurry, jpeg artifacts, bad anatomy, bad hands, extra fingers, "
    "missing fingers, fused fingers, deformed face, asymmetrical eyes, cropped head, out of frame, "
    "text, letters, kanji, chinese characters, random text, unreadable text, labels, callout boxes, "
    "watermark, logo, signature, speech bubble, blank speech bubble, white oval, duplicate character, "
    "multiple girls, two girls, group, split screen, identity drift, inconsistent hairstyle, inconsistent eye color, "
    "wrong school uniform, changed age, changed body proportions, photorealistic, 3D render"
)


def main() -> int:
    args = parse_args()
    prompt_pack = read_json(args.prompt_pack)
    source_images = source_image_paths(args.source_dir)
    object_info = get_json(args.server.rstrip("/") + "/object_info")
    validate_nodes(object_info)
    checkpoint_cases = available_checkpoints(object_info, args.checkpoints)
    variants = available_variants(args.workflow_variants)
    if not checkpoint_cases:
        raise RuntimeError("No requested checkpoints are available in ComfyUI")
    if not variants:
        raise RuntimeError("No requested workflow variants are configured")

    run_id = args.run_id or time.strftime("%Y%m%d_%H%M%S")
    output_root = args.output_root / run_id
    output_root.mkdir(parents=True, exist_ok=True)

    client = ComfyClient(ComfyClientConfig(server=args.server, timeout_seconds=args.timeout_seconds))
    client.check_server()

    tasks: list[dict[str, Any]] = []
    characters = list(prompt_pack.get("characters", []))
    for checkpoint_index, checkpoint in enumerate(checkpoint_cases):
        for variant_index, variant in enumerate(variants):
            for character_index, character in enumerate(characters):
                if args.max_cases and len(tasks) >= args.max_cases:
                    break
                seed = args.seed + checkpoint_index * 10000 + variant_index * 1000 + character_index * 101
                tasks.append(
                    submit_case(
                        client=client,
                        checkpoint=checkpoint,
                        variant=variant,
                        character=character,
                        run_id=run_id,
                        seed=seed,
                        output_root=output_root,
                        source_images=source_images,
                        prompt_pack_path=args.prompt_pack,
                        poll_attempts=args.poll_attempts,
                        poll_interval_seconds=args.poll_interval_seconds,
                    )
                )
            if args.max_cases and len(tasks) >= args.max_cases:
                break
        if args.max_cases and len(tasks) >= args.max_cases:
            break

    result = {
        "workflow_name": "video_reference_design_matrix_sdxl",
        "run_id": run_id,
        "server": args.server,
        "source_dir": rel(args.source_dir),
        "source_images": [rel(path) for path in source_images],
        "prompt_pack": rel(args.prompt_pack),
        "output_root": rel(output_root),
        "checkpoints": [case.ckpt_name for case in checkpoint_cases],
        "workflow_variants": [variant_to_record(variant) for variant in variants],
        "tasks": tasks,
    }
    render_contact_sheets(tasks, output_root)
    render_source_sheet(source_images, output_root / "source_manga_contact_sheet.jpg")
    write_json(output_root / "video_reference_design_tasks.json", result)
    write_summary_markdown(result, output_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def submit_case(
    *,
    client: ComfyClient,
    checkpoint: CheckpointCase,
    variant: WorkflowVariant,
    character: dict[str, Any],
    run_id: str,
    seed: int,
    output_root: Path,
    source_images: list[Path],
    prompt_pack_path: Path,
    poll_attempts: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    character_id = str(character.get("character_id") or "character")
    condition_id = f"{checkpoint.label}__{variant.variant_id}"
    case_dir = output_root / "by_condition" / condition_id
    case_dir.mkdir(parents=True, exist_ok=True)
    positive = build_positive_prompt(character, variant)
    negative = build_negative_prompt(character, variant)
    filename_prefix = f"manga_anime_pipeline/test_projects_short_manga/video_reference_design_matrix/{run_id}/{condition_id}/{character_id}"
    workflow = build_sdxl_workflow(
        checkpoint=checkpoint.ckpt_name,
        positive=positive,
        negative=negative,
        width=variant.width,
        height=variant.height,
        steps=variant.steps,
        cfg=variant.cfg,
        sampler=variant.sampler,
        scheduler=variant.scheduler,
        seed=seed,
        filename_prefix=filename_prefix,
    )
    client_id = f"agent:copilot|workflow:video_reference_design_matrix_sdxl|run:{run_id}"
    extra_data = {
        "agent": "copilot",
        "workflow_name": "video_reference_design_matrix_sdxl",
        "source": "manga-anime-pipeline",
        "character_id": character_id,
        "checkpoint": checkpoint.ckpt_name,
        "workflow_variant": variant.variant_id,
        "seed": seed,
        "notes": (
            f"video reference design matrix; checkpoint={checkpoint.ckpt_name}; variant={variant.variant_id}; "
            f"size={variant.width}x{variant.height}; steps={variant.steps}; cfg={variant.cfg}; "
            f"sampler={variant.sampler}; scheduler={variant.scheduler}; prompt_pack={rel(prompt_pack_path)}; "
            f"source_images={len(source_images)} manga panels"
        ),
    }
    response = client.submit_prompt({"prompt": workflow, "client_id": client_id, "extra_data": extra_data})
    prompt_id = str(response.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI submit response missing prompt_id: {response}")
    entry = wait_for_history(client, prompt_id, poll_attempts, poll_interval_seconds)
    copied = copy_history_images(entry, case_dir, character_id)
    task_context = {
        "condition_id": condition_id,
        "checkpoint": checkpoint.ckpt_name,
        "checkpoint_label": checkpoint.label,
        "workflow_variant": variant_to_record(variant),
        "character_id": character_id,
        "display_name": character.get("display_name"),
        "seed": seed,
        "sampler": variant.sampler,
        "scheduler": variant.scheduler,
        "cfg": variant.cfg,
        "steps": variant.steps,
        "size": [variant.width, variant.height],
        "source_images": [rel(path) for path in source_images],
        "positive_prompt": positive,
        "negative_prompt": negative,
    }
    provenance_files = write_output_provenance_files(
        copied,
        project_root=PROJECT_ROOT,
        workflow=workflow,
        workflow_name="video_reference_design_matrix_sdxl",
        prompt_id=prompt_id,
        client_id=client_id,
        extra_data=extra_data,
        task_context=task_context,
        history_status=entry.get("status") if isinstance(entry.get("status"), dict) else {},
    )
    return {
        **task_context,
        "prompt_id": prompt_id,
        "output_files": [rel(path) for path in copied],
        "provenance_files": [rel(path) for path in provenance_files],
        "status": "finished" if copied else "finished_without_images",
    }


def build_positive_prompt(character: dict[str, Any], variant: WorkflowVariant) -> str:
    character_id = str(character.get("character_id") or "")
    optimized = str(character.get("optimized_design_prompt") or "")
    parts = [
        "masterpiece, best quality, anime style, polished key visual quality",
        "solo, single character only, one girl, consistent identity, clean line art, delicate cel shading",
        "manga-to-anime adaptation of a light comedy school romance, faithful to the provided source panels",
        "Japanese navy-and-white sailor school uniform, red bow or tie, pleated skirt, loafers",
        role_prompt(character_id, variant.variant_id),
        traits_prompt(character),
        optimized,
        variant.positive_suffix,
    ]
    return join_prompt(parts)


def build_negative_prompt(character: dict[str, Any], variant: WorkflowVariant) -> str:
    parts = [
        BASE_NEGATIVE,
        role_negative(str(character.get("character_id") or "")),
        variant.negative_suffix,
        str(character.get("optimized_negative_prompt") or character.get("negative_prompt") or ""),
    ]
    return join_prompt(parts)


def role_prompt(character_id: str, variant_id: str) -> str:
    if character_id == "char_dark_ponytail":
        base = (
            "tall slender high school girl, about 172cm impression, dark purple hair, high ponytail tied with a black ribbon, "
            "long side locks, purple eyes, lively mischievous smile, confident teasing personality, slightly mature proportions"
        )
        if variant_id == "video_story_keyframe":
            return base + ", playful reaction pose, holding chopsticks or a small strawberry, surprised but charming expression"
        if variant_id == "expression_reference_sheet":
            return base + ", expression callouts show teasing smile and bashful surprise, same purple eyes and high ponytail"
        return base
    if character_id == "char_silver_longhair":
        base = (
            "petite but age-appropriate high school girl, about 142cm impression, silver white long straight hair, "
            "black hairband, green eyes, gentle soft smile, calm bright personality, delicate but not childish proportions"
        )
        if variant_id == "video_story_keyframe":
            return base + ", offering a strawberry with a warm playful smile, gentle hand gesture, light comedy keyframe"
        if variant_id == "expression_reference_sheet":
            return base + ", expression callouts show gentle smile and small surprised face, same hairband and green eyes"
        return base
    return ""


def role_negative(character_id: str) -> str:
    if character_id == "char_dark_ponytail":
        return "silver hair, white hair, green eyes, short hair, extra pale-haired girl"
    if character_id == "char_silver_longhair":
        return "purple hair, high ponytail, purple eyes, short hair, extra dark-haired girl"
    return ""


def traits_prompt(character: dict[str, Any]) -> str:
    traits = character.get("visual_traits") or {}
    parts = [
        str(traits.get("hair_color") or ""),
        str(traits.get("hair_style") or ""),
        str(traits.get("eye_color") or ""),
        str(traits.get("outfit") or ""),
        str(traits.get("height") or ""),
        " ".join(str(item) for item in traits.get("descriptions", []) if item),
    ]
    return ", ".join(part for part in parts if part)


def build_sdxl_workflow(
    *,
    checkpoint: str,
    positive: str,
    negative: str,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    sampler: str,
    scheduler: str,
    seed: int,
    filename_prefix: str,
) -> dict[str, Any]:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": positive}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": negative}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": sampler,
                "scheduler": scheduler,
                "denoise": 1.0,
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": filename_prefix}},
    }


def wait_for_history(
    client: ComfyClient,
    prompt_id: str,
    poll_attempts: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    for attempt in range(max(1, poll_attempts)):
        if attempt:
            time.sleep(max(0.0, poll_interval_seconds))
        history = client.get_history(prompt_id)
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        if not entry:
            continue
        status_info = entry.get("status") if isinstance(entry.get("status"), dict) else {}
        if str(status_info.get("status_str", "")).lower() in {"error", "failed"}:
            raise RuntimeError(f"ComfyUI history failed for {prompt_id}: {status_info}")
        if entry.get("outputs"):
            return entry
    raise TimeoutError(f"ComfyUI history did not finish for {prompt_id}")


def copy_history_images(entry: dict[str, Any], output_dir: Path, character_id: str) -> list[Path]:
    copied: list[Path] = []
    for node_output in (entry.get("outputs") or {}).values():
        for image in node_output.get("images", []) or []:
            filename = str(image.get("filename") or "")
            if not filename:
                continue
            subfolder = str(image.get("subfolder") or "")
            source = COMFY_OUTPUT_ROOT / subfolder / filename
            if not source.exists():
                continue
            target = output_dir / f"{character_id}_{len(copied) + 1:02d}{source.suffix}"
            shutil.copy2(source, target)
            copied.append(target)
    return copied


def render_contact_sheets(tasks: list[dict[str, Any]], output_root: Path) -> None:
    render_sheet(tasks, output_root / "all_conditions_contact_sheet.jpg", "全部条件总览")
    for key, folder, title_prefix in [
        ("checkpoint_label", "by_checkpoint", "按模型查看"),
        ("workflow_variant.variant_id", "by_workflow", "按工作流查看"),
        ("character_id", "by_character", "按角色查看"),
    ]:
        target_dir = output_root / folder
        target_dir.mkdir(exist_ok=True)
        for value in sorted({group_value(task, key) for task in tasks}):
            label = safe_name(value)
            render_sheet(
                [task for task in tasks if group_value(task, key) == value],
                target_dir / f"{label}.jpg",
                f"{title_prefix}: {value}",
            )


def render_sheet(tasks: list[dict[str, Any]], output_path: Path, title: str) -> None:
    if not tasks:
        return
    thumb_w, thumb_h = 260, 360
    label_h = 112
    margin = 28
    cols = min(6, max(1, len(tasks)))
    rows = (len(tasks) + cols - 1) // cols
    width = margin * 2 + cols * thumb_w + (cols - 1) * 18
    height = margin * 2 + 58 + rows * (thumb_h + label_h + 18)
    sheet = Image.new("RGB", (width, height), "#f6f5f1")
    draw = ImageDraw.Draw(sheet)
    fonts = fonts_for_sheet()
    draw.text((margin, margin), title, font=fonts["title"], fill="#1d1c19")
    for index, task in enumerate(tasks):
        row, col = divmod(index, cols)
        x = margin + col * (thumb_w + 18)
        y = margin + 58 + row * (thumb_h + label_h + 18)
        draw.rounded_rectangle((x - 8, y - 8, x + thumb_w + 8, y + thumb_h + label_h + 8), radius=8, fill="#ffffff", outline="#d5d1c8")
        image_path = first_existing(task.get("output_files", []))
        if image_path:
            paste_image(sheet, image_path, (x, y), (thumb_w, thumb_h))
        variant = task.get("workflow_variant") or {}
        text = f"{task['checkpoint_label']}\n{variant.get('label', '')}\n{task['display_name']}\nseed {task['seed']}"
        draw_multiline(draw, text, (x, y + thumb_h + 10), thumb_w, fonts["small"], "#292621")
    sheet.save(output_path, quality=92)


def render_source_sheet(source_images: list[Path], output_path: Path) -> None:
    if not source_images:
        return
    thumb_w, thumb_h = 260, 340
    margin = 24
    width = margin * 2 + len(source_images) * thumb_w + (len(source_images) - 1) * 16
    height = margin * 2 + 46 + thumb_h + 52
    sheet = Image.new("RGB", (width, height), "#f6f5f1")
    draw = ImageDraw.Draw(sheet)
    fonts = fonts_for_sheet()
    draw.text((margin, margin), "源漫画素材", font=fonts["title"], fill="#1d1c19")
    for index, image_path in enumerate(source_images):
        x = margin + index * (thumb_w + 16)
        y = margin + 46
        draw.rounded_rectangle((x - 8, y - 8, x + thumb_w + 8, y + thumb_h + 46), radius=8, fill="#ffffff", outline="#d5d1c8")
        paste_image(sheet, image_path, (x, y), (thumb_w, thumb_h))
        draw_multiline(draw, image_path.name, (x, y + thumb_h + 8), thumb_w, fonts["small"], "#292621")
    sheet.save(output_path, quality=92)


def paste_image(sheet: Image.Image, image_path: Path, xy: tuple[int, int], size: tuple[int, int]) -> None:
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        image.thumbnail(size, Image.Resampling.LANCZOS)
        frame = Image.new("RGB", size, "#e1dfd8")
        frame.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
        sheet.paste(frame, xy)


def write_summary_markdown(result: dict[str, Any], output_root: Path) -> None:
    def local(path: Path) -> str:
        return str(path.relative_to(output_root)).replace("\\", "/")

    lines = [
        "# 角色视频参考图矩阵测试结果",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- 源漫画目录: `{result['source_dir']}`",
        f"- 提示词包: `{result['prompt_pack']}`",
        f"- 任务 JSON: `{rel(output_root / 'video_reference_design_tasks.json')}`",
        f"- 总览拼图: `{rel(output_root / 'all_conditions_contact_sheet.jpg')}`",
        f"- 源漫画拼图: `{rel(output_root / 'source_manga_contact_sheet.jpg')}`",
        "",
        "## 实验目标",
        "",
        "本轮不是直接生成完整视频，而是先为后续图生视频挑选稳定的角色参考图。判断重点是角色身份、年龄感、身高气质、校服结构、表情可动画性，以及是否会生成文字、气泡或水印。",
        "",
        "## 源漫画素材",
        "",
        f"![源漫画素材]({local(output_root / 'source_manga_contact_sheet.jpg')})",
        "",
        "## 总览",
        "",
        f"![全部条件总览]({local(output_root / 'all_conditions_contact_sheet.jpg')})",
        "",
        "## 工作流与参数",
        "",
        "| 工作流 | 用途 | 尺寸 | steps | cfg | sampler | scheduler |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for variant in result["workflow_variants"]:
        size = f"{variant['width']}x{variant['height']}"
        lines.append(
            f"| `{variant['variant_id']}` / {variant['label']} | {variant['purpose']} | `{size}` | {variant['steps']} | {variant['cfg']} | `{variant['sampler']}` | `{variant['scheduler']}` |"
        )
    lines.extend(["", "## 按模型分组", ""])
    for checkpoint in result["checkpoints"]:
        label = short_checkpoint(checkpoint)
        sheet = output_root / "by_checkpoint" / f"{label}.jpg"
        if sheet.exists():
            lines.append(f"### {label}")
            lines.append("")
            lines.append(f"![{label}]({local(sheet)})")
            lines.append("")
    lines.extend(["## 按工作流分组", ""])
    for variant in result["workflow_variants"]:
        sheet = output_root / "by_workflow" / f"{safe_name(variant['variant_id'])}.jpg"
        if sheet.exists():
            lines.append(f"### {variant['variant_id']} / {variant['label']}")
            lines.append("")
            lines.append(f"![{variant['variant_id']}]({local(sheet)})")
            lines.append("")
    lines.extend(["## 单图参数表", ""])
    lines.append("| 模型 | 工作流 | 角色 | seed | 尺寸 | steps/cfg | 输出图 | provenance | 观察记录 |")
    lines.append("|---|---|---|---:|---|---|---|---|---|")
    for task in result["tasks"]:
        variant = task.get("workflow_variant") or {}
        image = task["output_files"][0] if task.get("output_files") else ""
        sidecar = task["provenance_files"][0] if task.get("provenance_files") else ""
        size = f"{task['size'][0]}x{task['size'][1]}"
        lines.append(
            "| "
            f"`{task['checkpoint_label']}` | `{variant.get('variant_id', '')}` | {task['display_name']} | {task['seed']} | `{size}` | "
            f"{task['steps']} / {task['cfg']} | `{image}` | `{sidecar}` |  |"
        )
    lines.extend(["", "## 提示词索引", ""])
    for task in result["tasks"]:
        variant = task.get("workflow_variant") or {}
        title = f"{task['checkpoint_label']} / {variant.get('variant_id', '')} / {task['display_name']}"
        lines.append(f"<details><summary>{title}</summary>")
        lines.append("")
        lines.append(f"- prompt_id: `{task['prompt_id']}`")
        lines.append(f"- positive: {task['positive_prompt']}")
        lines.append(f"- negative: {task['negative_prompt']}")
        lines.append("")
        lines.append("</details>")
        lines.append("")
    (output_root / "video_reference_design_matrix_summary.md").write_text("\n".join(lines), encoding="utf-8")


def source_image_paths(source_dir: Path) -> list[Path]:
    return sorted(path for path in source_dir.glob("*") if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})


def available_checkpoints(object_info: dict[str, Any], requested: list[str]) -> list[CheckpointCase]:
    ckpt_values = object_info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
    available = set(ckpt_values)
    requested_names = requested or [case.ckpt_name for case in CHECKPOINT_CASES]
    cases = []
    for name in requested_names:
        if name in available:
            cases.append(CheckpointCase(name, short_checkpoint(name)))
    return cases


def available_variants(requested: list[str]) -> list[WorkflowVariant]:
    selected = requested or [variant.variant_id for variant in WORKFLOW_VARIANTS]
    by_id = {variant.variant_id: variant for variant in WORKFLOW_VARIANTS}
    return [by_id[variant_id] for variant_id in selected if variant_id in by_id]


def validate_nodes(object_info: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_NODES - set(object_info))
    if missing:
        raise RuntimeError("ComfyUI missing required nodes: " + ", ".join(missing))


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def first_existing(paths: list[str]) -> Path | None:
    for rel_path in paths:
        path = PROJECT_ROOT / rel_path
        if path.exists():
            return path
    return None


def join_prompt(parts: list[str]) -> str:
    clauses: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for clause in str(part or "").replace("，", ",").split(","):
            text = clause.strip()
            if not text:
                continue
            key = text.lower()
            if key not in seen:
                clauses.append(text)
                seen.add(key)
    return ", ".join(clauses)


def variant_to_record(variant: WorkflowVariant) -> dict[str, Any]:
    return {
        "variant_id": variant.variant_id,
        "label": variant.label,
        "purpose": variant.purpose,
        "width": variant.width,
        "height": variant.height,
        "steps": variant.steps,
        "cfg": variant.cfg,
        "sampler": variant.sampler,
        "scheduler": variant.scheduler,
        "positive_suffix": variant.positive_suffix,
        "negative_suffix": variant.negative_suffix,
    }


def group_value(task: dict[str, Any], key: str) -> str:
    value: Any = task
    for part in key.split("."):
        value = value.get(part, {}) if isinstance(value, dict) else {}
    return str(value or "unknown")


def draw_multiline(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    max_width: int,
    font: ImageFont.ImageFont,
    fill: str,
) -> None:
    x, y = xy
    for line in text.splitlines():
        current = ""
        for char in line:
            candidate = current + char
            if draw.textlength(candidate, font=font) <= max_width or not current:
                current = candidate
            else:
                draw.text((x, y), current, font=font, fill=fill)
                y += font.size + 4
                current = char
        if current:
            draw.text((x, y), current, font=font, fill=fill)
            y += font.size + 4


def fonts_for_sheet() -> dict[str, ImageFont.FreeTypeFont]:
    font_path = font_path_for_sheet()
    return {
        "title": ImageFont.truetype(font_path, 30),
        "small": ImageFont.truetype(font_path, 17),
    }


def font_path_for_sheet() -> str:
    for path in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/simsun.ttc")]:
        if path.exists():
            return str(path)
    raise FileNotFoundError("No Chinese-capable Windows font found")


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value)[:80]


def rel(path: Path) -> str:
    return str(Path(path).resolve().relative_to(PROJECT_ROOT))


def short_checkpoint(name: str) -> str:
    stem = Path(name).stem
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:4]
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in stem)[:52] + "_" + digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a video-oriented character reference design matrix")
    parser.add_argument("--prompt-pack", type=Path, default=DEFAULT_PROMPT_PACK)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--seed", type=int, default=2026051501)
    parser.add_argument("--checkpoints", nargs="*", default=[])
    parser.add_argument("--workflow-variants", nargs="*", default=[])
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-attempts", type=int, default=240)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())