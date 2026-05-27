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

from PIL import Image, ImageDraw, ImageFont, ImageOps

from pipeline.comfy.client import ComfyClient, ComfyClientConfig
from pipeline.comfy.provenance import write_output_provenance_files
from pipeline.common.io import read_json, write_json


RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "2026-05-15_pose_freed_design_6cases"
DEFAULT_PROMPT_PACK = PROJECT_ROOT / "runtime" / "2026-05-15_test_projects_short_manga" / "review" / "optimized_prompt_pack.json"
COMFY_INPUT_ROOT = WORKSPACE_ROOT / "ComfyUI" / "input"
COMFY_OUTPUT_ROOT = WORKSPACE_ROOT / "ComfyUI" / "output"
COMFY_INPUT_SUBDIR = "agent_manga_pose_freed_design"
OUTPUT_SIZE = (1216, 768)

REQUIRED_NODES = {
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
    "LoadImage",
    "IPAdapterModelLoader",
    "IPAdapterAdvanced",
    "CLIPVisionLoader",
    "ControlNetLoader",
    "ControlNetApplyAdvanced",
    "LoraLoader",
}

IDENTITY_CROPS = {
    "char_dark_ponytail": {
        "source": "tests/Test_projects/QQ20260515-145053.png",
        "box": [220, 0, 560, 560],
    },
    "char_silver_longhair": {
        "source": "tests/Test_projects/QQ20260515-145001.png",
        "box": [530, 250, 790, 850],
    },
}


@dataclass(frozen=True)
class CheckpointCase:
    ckpt_name: str
    label: str


@dataclass(frozen=True)
class LoraCase:
    lora_id: str
    label: str
    lora_name: str = ""
    strength_model: float = 0.0
    strength_clip: float = 0.0
    prompt_hint: str = ""


@dataclass(frozen=True)
class DesignCase:
    case_id: str
    character_id: str
    checkpoint: CheckpointCase
    condition_label: str
    use_ipadapter: bool
    ipadapter_weight: float
    use_layout_control: bool
    control_strength: float
    lora: LoraCase
    seed_offset: int
    cfg: float = 6.6
    steps: int = 24


CHECKPOINTS = {
    "wai": CheckpointCase("waiIllustriousSDXL_v170.safetensors", "waiIllustriousSDXL_v170"),
    "hassaku": CheckpointCase("hassakuXLIllustrious_v34.safetensors", "hassakuXLIllustrious_v34"),
}

LORAS = {
    "none": LoraCase("none", "无 LoRA"),
    "huespark": LoraCase(
        "huespark_illust",
        "HueSpark 插画光感",
        "HueSpark1llust.safetensors",
        0.45,
        0.35,
        "polished anime illustration lighting, clean luminous color, soft highlights",
    ),
    "etching": LoraCase(
        "etching_line",
        "蚀刻线稿质感",
        "etching_print_v3-4-850.safetensors",
        0.36,
        0.28,
        "crisp hand-drawn ink line weight, refined line texture, production drawing feel",
    ),
}


def main() -> int:
    args = parse_args()
    prompt_pack = read_json(args.prompt_pack)
    object_info = get_json(args.server.rstrip("/") + "/object_info")
    validate_nodes(object_info)
    validate_models(object_info)

    run_id = args.run_id or time.strftime("%Y%m%d_%H%M%S")
    output_root = args.output_root / run_id
    output_root.mkdir(parents=True, exist_ok=True)
    references = prepare_references(prompt_pack, output_root, run_id)
    cases = build_cases(prompt_pack, seed=args.seed, max_cases=args.max_cases)

    client = ComfyClient(ComfyClientConfig(server=args.server, timeout_seconds=args.timeout_seconds))
    client.check_server()

    tasks: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case.case_id}", flush=True)
        task = submit_case(
            client=client,
            case=case,
            character=character_by_id(prompt_pack, case.character_id),
            references=references,
            run_id=run_id,
            output_root=output_root,
            prompt_pack_path=args.prompt_pack,
            poll_attempts=args.poll_attempts,
            poll_interval_seconds=args.poll_interval_seconds,
        )
        tasks.append(task)
        write_json(output_root / "pose_freed_design_tasks.partial.json", result_record(args, run_id, output_root, references, tasks))

    result = result_record(args, run_id, output_root, references, tasks)
    render_contact_sheet(tasks, output_root / "pose_freed_6cases_contact_sheet.jpg")
    render_reference_sheet(references, output_root / "identity_references_sheet.jpg")
    write_json(output_root / "pose_freed_design_tasks.json", result)
    write_summary_markdown(result, output_root)
    print(json.dumps({"run_id": run_id, "output_root": rel(output_root), "tasks": len(tasks), "finished": sum(1 for task in tasks if task.get("status") == "finished")}, ensure_ascii=False, indent=2))
    return 0


def build_cases(prompt_pack: dict[str, Any], *, seed: int, max_cases: int) -> list[DesignCase]:
    character_ids = [str(character.get("character_id") or "") for character in prompt_pack.get("characters", [])]
    cases: list[DesignCase] = []
    for character_index, character_id in enumerate(character_ids):
        cases.extend(
            [
                DesignCase(
                    case_id=f"{character_id}__prompt_only_turnaround_wai",
                    character_id=character_id,
                    checkpoint=CHECKPOINTS["wai"],
                    condition_label="纯提示词三视图设定稿",
                    use_ipadapter=False,
                    ipadapter_weight=0.0,
                    use_layout_control=False,
                    control_strength=0.0,
                    lora=LORAS["none"],
                    seed_offset=character_index * 1000 + 11,
                    cfg=6.8,
                    steps=24,
                ),
                DesignCase(
                    case_id=f"{character_id}__ipadapter_ultralight_huespark_wai",
                    character_id=character_id,
                    checkpoint=CHECKPOINTS["wai"],
                    condition_label="极低权重 IPAdapter 身份参考 + HueSpark",
                    use_ipadapter=True,
                    ipadapter_weight=0.12,
                    use_layout_control=False,
                    control_strength=0.0,
                    lora=LORAS["huespark"],
                    seed_offset=character_index * 1000 + 22,
                    cfg=6.5,
                    steps=24,
                ),
                DesignCase(
                    case_id=f"{character_id}__generic_layout_etching_hassaku",
                    character_id=character_id,
                    checkpoint=CHECKPOINTS["hassaku"],
                    condition_label="通用三视图线稿布局 + etching",
                    use_ipadapter=False,
                    ipadapter_weight=0.0,
                    use_layout_control=True,
                    control_strength=0.62,
                    lora=LORAS["etching"],
                    seed_offset=character_index * 1000 + 33,
                    cfg=6.4,
                    steps=24,
                ),
            ]
        )
    if max_cases:
        return cases[:max_cases]
    return cases


def prepare_references(prompt_pack: dict[str, Any], output_root: Path, run_id: str) -> dict[str, Any]:
    references: dict[str, Any] = {"characters": {}, "layout": {}}
    prepared_dir = output_root / "references" / "prepared"
    crop_dir = output_root / "references" / "crops"
    comfy_dir = COMFY_INPUT_ROOT / COMFY_INPUT_SUBDIR / run_id
    prepared_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.mkdir(parents=True, exist_ok=True)
    comfy_dir.mkdir(parents=True, exist_ok=True)

    for character in prompt_pack.get("characters", []):
        character_id = str(character.get("character_id") or "")
        crop_info = IDENTITY_CROPS.get(character_id)
        if not crop_info:
            continue
        source_path = PROJECT_ROOT / str(crop_info["source"])
        crop = crop_image(source_path, list(crop_info["box"]))
        crop_path = crop_dir / f"{character_id}_identity_crop.png"
        prepared_path = prepared_dir / f"{character_id}_identity_reference.png"
        comfy_path = comfy_dir / prepared_path.name
        crop.save(crop_path)
        fit_to_canvas(crop, (512, 768), background="#f8f5f0").save(prepared_path)
        shutil.copy2(prepared_path, comfy_path)
        references["characters"][character_id] = {
            "source_image": crop_info["source"],
            "source_box": crop_info["box"],
            "crop_file": rel(crop_path),
            "prepared_file": rel(prepared_path),
            "comfy_image": f"{COMFY_INPUT_SUBDIR}/{run_id}/{prepared_path.name}",
        }

    layout_path = prepared_dir / f"generic_three_view_layout_{OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}.png"
    layout_comfy_path = comfy_dir / layout_path.name
    create_generic_three_view_layout(OUTPUT_SIZE).save(layout_path)
    shutil.copy2(layout_path, layout_comfy_path)
    references["layout"] = {
        "description": "本地生成的无文字三视图布局线稿，只约束三个站姿位置，不使用原漫画姿势。",
        "prepared_file": rel(layout_path),
        "comfy_image": f"{COMFY_INPUT_SUBDIR}/{run_id}/{layout_path.name}",
    }
    return references


def submit_case(
    *,
    client: ComfyClient,
    case: DesignCase,
    character: dict[str, Any],
    references: dict[str, Any],
    run_id: str,
    output_root: Path,
    prompt_pack_path: Path,
    poll_attempts: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    case_dir = output_root / "results" / safe_name(case.case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    positive = build_positive_prompt(case, character)
    negative = build_negative_prompt(case)
    workflow = build_workflow(case, references, positive, negative, run_id)
    client_id = f"agent:copilot|workflow:pose_freed_design_6cases|run:{run_id}"
    seed = 2026051500 + case.seed_offset
    extra_data = {
        "agent": "copilot",
        "workflow_name": "pose_freed_design_6cases",
        "source": "manga-anime-pipeline",
        "character_id": case.character_id,
        "checkpoint": case.checkpoint.ckpt_name,
        "condition": case.condition_label,
        "lora": case.lora.lora_name or "none",
        "seed": seed,
        "notes": (
            f"pose-freed design test; case={case.case_id}; empty_latent=true; size={OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}; "
            f"ipadapter={case.use_ipadapter}; ip_weight={case.ipadapter_weight}; generic_layout_control={case.use_layout_control}; "
            f"control_strength={case.control_strength}; lora={case.lora.lora_name or 'none'}; prompt_pack={rel(prompt_pack_path)}"
        ),
    }
    response = client.submit_prompt({"prompt": workflow, "client_id": client_id, "extra_data": extra_data})
    prompt_id = str(response.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI submit response missing prompt_id: {response}")
    entry = wait_for_history(client, prompt_id, poll_attempts, poll_interval_seconds)
    copied = copy_history_images(entry, case_dir, case.case_id)
    task_context = task_record(case, character, prompt_id, seed, positive, negative, references, [rel(path) for path in copied], [])
    provenance_files = write_output_provenance_files(
        copied,
        project_root=PROJECT_ROOT,
        workflow=workflow,
        workflow_name="pose_freed_design_6cases",
        prompt_id=prompt_id,
        client_id=client_id,
        extra_data=extra_data,
        task_context=task_context,
        history_status=entry.get("status") if isinstance(entry.get("status"), dict) else {},
    )
    task_context["provenance_files"] = [rel(path) for path in provenance_files]
    task_context["status"] = "finished" if copied else "finished_without_images"
    return task_context


def build_workflow(case: DesignCase, references: dict[str, Any], positive: str, negative: str, run_id: str) -> dict[str, Any]:
    workflow: dict[str, Any] = {}
    next_id = 1
    seed = 2026051500 + case.seed_offset
    filename_prefix = f"manga_anime_pipeline/pose_freed_design_6cases/{run_id}/{safe_name(case.case_id)}/{case.character_id}"

    def add(class_type: str, inputs: dict[str, Any]) -> str:
        nonlocal next_id
        node_id = str(next_id)
        next_id += 1
        workflow[node_id] = {"class_type": class_type, "inputs": inputs}
        return node_id

    checkpoint_node = add("CheckpointLoaderSimple", {"ckpt_name": case.checkpoint.ckpt_name})
    model_ref: list[Any] = [checkpoint_node, 0]
    clip_ref: list[Any] = [checkpoint_node, 1]
    vae_ref: list[Any] = [checkpoint_node, 2]

    if case.lora.lora_name:
        lora_node = add(
            "LoraLoader",
            {
                "model": model_ref,
                "clip": clip_ref,
                "lora_name": case.lora.lora_name,
                "strength_model": case.lora.strength_model,
                "strength_clip": case.lora.strength_clip,
            },
        )
        model_ref = [lora_node, 0]
        clip_ref = [lora_node, 1]

    if case.use_ipadapter:
        image_node = add("LoadImage", {"image": references["characters"][case.character_id]["comfy_image"]})
        ip_model = add("IPAdapterModelLoader", {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"})
        clip_vision = add("CLIPVisionLoader", {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"})
        ip_node = add(
            "IPAdapterAdvanced",
            {
                "model": model_ref,
                "ipadapter": [ip_model, 0],
                "image": [image_node, 0],
                "weight": case.ipadapter_weight,
                "weight_type": "linear",
                "combine_embeds": "average",
                "start_at": 0.0,
                "end_at": 0.35,
                "embeds_scaling": "V only",
                "clip_vision": [clip_vision, 0],
            },
        )
        model_ref = [ip_node, 0]

    positive_node = add("CLIPTextEncode", {"clip": clip_ref, "text": positive})
    negative_node = add("CLIPTextEncode", {"clip": clip_ref, "text": negative})
    positive_ref: list[Any] = [positive_node, 0]
    negative_ref: list[Any] = [negative_node, 0]

    if case.use_layout_control:
        layout_node = add("LoadImage", {"image": references["layout"]["comfy_image"]})
        controlnet = add("ControlNetLoader", {"control_net_name": "mistoLine_rank256.safetensors"})
        control_node = add(
            "ControlNetApplyAdvanced",
            {
                "positive": positive_ref,
                "negative": negative_ref,
                "control_net": [controlnet, 0],
                "image": [layout_node, 0],
                "strength": case.control_strength,
                "start_percent": 0.0,
                "end_percent": 0.55,
            },
        )
        positive_ref = [control_node, 0]
        negative_ref = [control_node, 1]

    latent = add("EmptyLatentImage", {"width": OUTPUT_SIZE[0], "height": OUTPUT_SIZE[1], "batch_size": 1})
    sampler = add(
        "KSampler",
        {
            "model": model_ref,
            "positive": positive_ref,
            "negative": negative_ref,
            "latent_image": [latent, 0],
            "seed": seed,
            "steps": case.steps,
            "cfg": case.cfg,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
        },
    )
    decoded = add("VAEDecode", {"samples": [sampler, 0], "vae": vae_ref})
    add("SaveImage", {"images": [decoded, 0], "filename_prefix": filename_prefix})
    return workflow


def build_positive_prompt(case: DesignCase, character: dict[str, Any]) -> str:
    parts = [
        "masterpiece, best quality, clean anime production design sheet",
        "unlabeled character turnaround sheet, exactly three full-body views only, front view, side view, back view",
        "same single girl repeated three times, neutral standing orthographic views, arms relaxed slightly away from body, feet visible",
        "all three views fully clothed in the same school uniform, plain white studio background, no labels, no text, no speech bubbles, no manga panel layout",
        "consistent school uniform, consistent face, consistent hair style, accurate age impression, video production reference, clean spacing between three standing figures",
        role_prompt(case.character_id),
        case.lora.prompt_hint,
    ]
    return join_prompt(parts)


def build_negative_prompt(case: DesignCase) -> str:
    parts = [
        "worst quality, low quality, lowres, blurry, jpeg artifacts, bad anatomy, bad hands, extra fingers, missing fingers, fused fingers",
        "text, labels, captions, signature, watermark, speech bubble, dialogue bubble, black text balloon, white oval speech bubble",
        "Japanese text, Chinese text, kanji, kana, comic sound effects, typography, annotation arrows, UI panels",
        "manga panel composition, copied source pose, leaning forward like source panel, cropped panel, background from source image",
        "two interacting characters, extra unrelated person, strawberry, chopsticks, classroom props, busy background",
        "portrait sheet, expression sheet, headshot collage, bust callouts, face closeups, four views, five views, more than three figures",
        "nude reference body, underwear, swimsuit, bare torso, bare chest, bare hips, naked side view, mannequin body without clothes",
        "different identity across views, inconsistent hairstyle, inconsistent eye color, wrong school uniform, changed age, chibi, toddler face",
        role_negative(case.character_id),
    ]
    return join_prompt(parts)


def role_prompt(character_id: str) -> str:
    if character_id == "char_dark_ponytail":
        return "tall slender high school girl, dark purple high ponytail tied with black ribbon, long side locks, purple eyes, lively mischievous smile, navy and white sailor school uniform with red tie, pleated skirt, about 172cm impression"
    if character_id == "char_silver_longhair":
        return "petite but age-appropriate high school girl, silver white long straight hair, black hairband, green eyes, gentle soft smile, navy and white sailor school uniform with red bow, pleated skirt, about 142cm impression"
    return "anime high school girl, sailor school uniform"


def role_negative(character_id: str) -> str:
    if character_id == "char_dark_ponytail":
        return "silver hair, white hair, green eyes, short hair, child body"
    if character_id == "char_silver_longhair":
        return "purple hair, high ponytail, purple eyes, dark-haired girl, child body"
    return ""


def create_generic_three_view_layout(size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    centers = [size[0] * 0.22, size[0] * 0.50, size[0] * 0.78]
    for index, center in enumerate(centers):
        draw_silhouette(draw, int(center), 100, 570, variant=index)
    return image


def draw_silhouette(draw: ImageDraw.ImageDraw, center_x: int, top_y: int, height: int, variant: int) -> None:
    line_width = 5
    head_width = 82 if variant != 1 else 66
    head_height = 96
    head_box = (center_x - head_width // 2, top_y, center_x + head_width // 2, top_y + head_height)
    draw.ellipse(head_box, outline="black", width=line_width)
    neck_y = top_y + head_height
    draw.line((center_x, neck_y, center_x, neck_y + 42), fill="black", width=line_width)
    shoulder_y = neck_y + 42
    hip_y = top_y + 330
    skirt_y = top_y + 390
    foot_y = top_y + height
    shoulder_half = 85 if variant != 1 else 50
    waist_half = 48 if variant != 1 else 30
    hip_half = 70 if variant != 1 else 36
    draw.line((center_x - shoulder_half, shoulder_y, center_x + shoulder_half, shoulder_y), fill="black", width=line_width)
    draw.line((center_x - shoulder_half, shoulder_y, center_x - waist_half, hip_y), fill="black", width=line_width)
    draw.line((center_x + shoulder_half, shoulder_y, center_x + waist_half, hip_y), fill="black", width=line_width)
    draw.line((center_x - waist_half, hip_y, center_x + waist_half, hip_y), fill="black", width=line_width)
    draw.polygon([(center_x - hip_half, skirt_y), (center_x + hip_half, skirt_y), (center_x + 45, hip_y), (center_x - 45, hip_y)], outline="black")
    arm_left_x = center_x - shoulder_half - 28
    arm_right_x = center_x + shoulder_half + 28
    hand_y = top_y + 365
    draw.line((center_x - shoulder_half, shoulder_y + 10, arm_left_x, hand_y), fill="black", width=line_width)
    draw.line((center_x + shoulder_half, shoulder_y + 10, arm_right_x, hand_y), fill="black", width=line_width)
    leg_gap = 28 if variant != 1 else 18
    draw.line((center_x - leg_gap, skirt_y, center_x - leg_gap - 20, foot_y), fill="black", width=line_width)
    draw.line((center_x + leg_gap, skirt_y, center_x + leg_gap + 20, foot_y), fill="black", width=line_width)
    draw.line((center_x - leg_gap - 34, foot_y, center_x - leg_gap + 18, foot_y), fill="black", width=line_width)
    draw.line((center_x + leg_gap - 18, foot_y, center_x + leg_gap + 34, foot_y), fill="black", width=line_width)
    if variant == 2:
        draw.arc((center_x - 60, top_y + 88, center_x + 60, top_y + 235), 0, 180, fill="black", width=line_width)
    if variant == 1:
        draw.line((center_x + 32, top_y + 40, center_x + 62, top_y + 58), fill="black", width=line_width)


def task_record(
    case: DesignCase,
    character: dict[str, Any],
    prompt_id: str,
    seed: int,
    positive: str,
    negative: str,
    references: dict[str, Any],
    output_files: list[str],
    provenance_files: list[str],
) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "status": "pending",
        "prompt_id": prompt_id,
        "condition_label": case.condition_label,
        "checkpoint": case.checkpoint.ckpt_name,
        "checkpoint_label": case.checkpoint.label,
        "character_id": case.character_id,
        "display_name": character.get("display_name"),
        "seed": seed,
        "size": list(OUTPUT_SIZE),
        "steps": case.steps,
        "cfg": case.cfg,
        "sampler": "euler",
        "scheduler": "normal",
        "empty_latent": True,
        "use_ipadapter": case.use_ipadapter,
        "ipadapter_weight": case.ipadapter_weight,
        "use_layout_control": case.use_layout_control,
        "control_strength": case.control_strength,
        "lora_id": case.lora.lora_id,
        "lora_name": case.lora.lora_name or "none",
        "lora_strength_model": case.lora.strength_model,
        "lora_strength_clip": case.lora.strength_clip,
        "identity_reference": references["characters"].get(case.character_id, {}),
        "layout_reference": references.get("layout", {}) if case.use_layout_control else {},
        "positive_prompt": positive,
        "negative_prompt": negative,
        "output_files": output_files,
        "provenance_files": provenance_files,
    }


def result_record(args: argparse.Namespace, run_id: str, output_root: Path, references: dict[str, Any], tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "workflow_name": "pose_freed_design_6cases",
        "run_id": run_id,
        "server": args.server,
        "prompt_pack": rel(args.prompt_pack),
        "output_root": rel(output_root),
        "output_size": list(OUTPUT_SIZE),
        "references": references,
        "tasks": tasks,
    }


def wait_for_history(client: ComfyClient, prompt_id: str, poll_attempts: int, poll_interval_seconds: float) -> dict[str, Any]:
    for attempt in range(max(1, poll_attempts)):
        if attempt:
            time.sleep(max(0.0, poll_interval_seconds))
        history = client.get_history(prompt_id)
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        if not entry:
            continue
        status_info = entry.get("status") if isinstance(entry.get("status"), dict) else {}
        if str(status_info.get("status_str", "")).lower() in {"error", "failed"}:
            raise RuntimeError(json.dumps(status_info.get("messages") or status_info, ensure_ascii=False)[:2000])
        if entry.get("outputs"):
            return entry
    raise TimeoutError(f"ComfyUI history did not finish for {prompt_id}")


def copy_history_images(entry: dict[str, Any], output_dir: Path, case_id: str) -> list[Path]:
    copied: list[Path] = []
    for node_output in (entry.get("outputs") or {}).values():
        for image_info in node_output.get("images", []) or []:
            filename = str(image_info.get("filename") or "")
            if not filename:
                continue
            subfolder = str(image_info.get("subfolder") or "")
            source = COMFY_OUTPUT_ROOT / subfolder / filename
            if not source.exists():
                continue
            target = output_dir / f"{safe_name(case_id)}_{len(copied) + 1:02d}{source.suffix}"
            shutil.copy2(source, target)
            copied.append(target)
    return copied


def crop_image(path: Path, box: list[int]) -> Image.Image:
    with Image.open(path) as image:
        image = image.convert("RGB")
        x1, y1, x2, y2 = clamp_box(box, image.width, image.height)
        return image.crop((x1, y1, x2, y2))


def clamp_box(box: list[int], width: int, height: int) -> list[int]:
    x1 = max(0, min(width - 1, int(box[0])))
    y1 = max(0, min(height - 1, int(box[1])))
    x2 = max(x1 + 1, min(width, int(box[2])))
    y2 = max(y1 + 1, min(height, int(box[3])))
    return [x1, y1, x2, y2]


def fit_to_canvas(image: Image.Image, size: tuple[int, int], *, background: str) -> Image.Image:
    fitted = ImageOps.contain(image.convert("RGB"), size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, background)
    canvas.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    return canvas


def render_contact_sheet(tasks: list[dict[str, Any]], output_path: Path) -> None:
    shown = [task for task in tasks if task.get("output_files")]
    if not shown:
        return
    thumb_w, thumb_h = 280, 178
    label_h = 118
    margin = 26
    cols = 3
    rows = (len(shown) + cols - 1) // cols
    width = margin * 2 + cols * thumb_w + (cols - 1) * 20
    height = margin * 2 + 56 + rows * (thumb_h + label_h + 18)
    sheet = Image.new("RGB", (width, height), "#f6f5f1")
    draw = ImageDraw.Draw(sheet)
    fonts = fonts_for_sheet()
    draw.text((margin, margin), "姿势松绑角色设定稿 6 案例", font=fonts["title"], fill="#1d1c19")
    for index, task in enumerate(shown):
        row, col = divmod(index, cols)
        left = margin + col * (thumb_w + 20)
        top = margin + 56 + row * (thumb_h + label_h + 18)
        draw.rounded_rectangle((left - 8, top - 8, left + thumb_w + 8, top + thumb_h + label_h + 8), radius=8, fill="#ffffff", outline="#d5d1c8")
        paste_image(sheet, PROJECT_ROOT / task["output_files"][0], (left, top), (thumb_w, thumb_h))
        label = f"{task['display_name']}\n{task['condition_label']}\n{task['checkpoint_label']} / {task['lora_id']}"
        draw_multiline(draw, label, (left, top + thumb_h + 8), thumb_w, fonts["small"], "#292621")
    sheet.save(output_path, quality=92)


def render_reference_sheet(references: dict[str, Any], output_path: Path) -> None:
    items: list[tuple[str, Path]] = []
    for character_id, ref in references.get("characters", {}).items():
        items.append((f"{character_id} identity", PROJECT_ROOT / ref["prepared_file"]))
    if references.get("layout"):
        items.append(("generic three-view layout", PROJECT_ROOT / references["layout"]["prepared_file"]))
    thumb_w, thumb_h = 220, 150
    label_h = 58
    margin = 24
    cols = min(3, len(items))
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (margin * 2 + cols * thumb_w + (cols - 1) * 18, margin * 2 + 52 + rows * (thumb_h + label_h + 18)), "#f6f5f1")
    draw = ImageDraw.Draw(sheet)
    fonts = fonts_for_sheet()
    draw.text((margin, margin), "本轮参考输入", font=fonts["title"], fill="#1d1c19")
    for index, (label, path) in enumerate(items):
        row, col = divmod(index, cols)
        left = margin + col * (thumb_w + 18)
        top = margin + 52 + row * (thumb_h + label_h + 18)
        paste_image(sheet, path, (left, top), (thumb_w, thumb_h))
        draw_multiline(draw, label, (left, top + thumb_h + 8), thumb_w, fonts["small"], "#292621")
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

    finished = [task for task in result["tasks"] if task.get("status") == "finished"]
    lines = [
        "# 姿势松绑角色设定稿 6 案例测试",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- 输出目录: `{result['output_root']}`",
        f"- 成功/总数: `{len(finished)} / {len(result['tasks'])}`",
        f"- 任务 JSON: `{rel(output_root / 'pose_freed_design_tasks.json')}`",
        f"- 总览拼图: `{rel(output_root / 'pose_freed_6cases_contact_sheet.jpg')}`",
        f"- 参考图拼图: `{rel(output_root / 'identity_references_sheet.jpg')}`",
        "",
        "## 为什么上轮像把文字翻成中文",
        "",
        "那不是可靠 OCR 翻译，而是扩散模型在图生图条件下对文字区域的重绘。原漫画 crop 里有气泡、竖排文字和拟声字，ControlNet/IPAdapter 会把这些区域当作重要结构保留下来；同时提示词和角色资料里含有中文姓名、中文描述和 `Chinese text` 这类负面词，模型会受到 CJK 字形和语义的共同偏置，生成看似中文、甚至像短句的文字。它有时会碰巧像翻译，但本质是生成式补全，不能当作稳定翻译链路。正式流程应先 OCR/翻译/排版，或先清理气泡再生成角色设计图。",
        "",
        "## 本轮优化思路",
        "",
        "- 不再用原漫画 crop 做 VAEEncode 起点，避免姿势和对白框被锁死。",
        "- 采用 `EmptyLatentImage` 起图，只把裁干净的身份 crop 以低权重 IPAdapter 输入。",
        "- 对三视图需求，只使用本地生成的无文字通用三视图线稿布局，不使用原漫画线稿。",
        "- `Pop-Art-6000.safetensors` 已知与本链路不兼容，本轮只用 `none`、`HueSpark1llust`、`etching_print`。",
        "",
        "## 参考输入",
        "",
        f"![references]({local(output_root / 'identity_references_sheet.jpg')})",
        "",
        "## 6 案例总览",
        "",
        f"![six cases]({local(output_root / 'pose_freed_6cases_contact_sheet.jpg')})",
        "",
        "## 单图结果表",
        "",
        "| 状态 | 角色 | 条件 | 模型 | LoRA | IPAdapter | 布局 ControlNet | 输出图 | provenance |",
        "|---|---|---|---|---|---:|---:|---|---|",
    ]
    for task in result["tasks"]:
        image = task["output_files"][0] if task.get("output_files") else ""
        sidecar = task["provenance_files"][0] if task.get("provenance_files") else ""
        lines.append(
            "| "
            f"`{task['status']}` | {task['display_name']} | {task['condition_label']} | `{task['checkpoint_label']}` | `{task['lora_id']}` | "
            f"{task['ipadapter_weight']} | {task['control_strength']} | `{image}` | `{sidecar}` |"
        )
    lines.extend(["", "## 参数与提示词", ""])
    for task in result["tasks"]:
        lines.append(f"<details><summary>{task['case_id']}</summary>")
        lines.append("")
        lines.append(f"- prompt_id: `{task['prompt_id']}`")
        lines.append(f"- seed: `{task['seed']}`")
        lines.append(f"- positive: {task['positive_prompt']}")
        lines.append(f"- negative: {task['negative_prompt']}")
        lines.append("")
        lines.append("</details>")
        lines.append("")
    (output_root / "pose_freed_design_6cases_summary.md").write_text("\n".join(lines), encoding="utf-8")


def validate_nodes(object_info: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_NODES - set(object_info))
    if missing:
        raise RuntimeError("ComfyUI missing required nodes: " + ", ".join(missing))


def validate_models(object_info: dict[str, Any]) -> None:
    checkpoints = set(object_info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0])
    loras = set(object_info.get("LoraLoader", {}).get("input", {}).get("required", {}).get("lora_name", [[]])[0])
    controlnets = set(object_info.get("ControlNetLoader", {}).get("input", {}).get("required", {}).get("control_net_name", [[]])[0])
    ip_models = set(object_info.get("IPAdapterModelLoader", {}).get("input", {}).get("required", {}).get("ipadapter_file", [[]])[0])
    clip_visions = set(object_info.get("CLIPVisionLoader", {}).get("input", {}).get("required", {}).get("clip_name", [[]])[0])
    required_checkpoints = {case.ckpt_name for case in CHECKPOINTS.values()}
    required_loras = {case.lora_name for case in LORAS.values() if case.lora_name}
    missing = sorted(required_checkpoints - checkpoints)
    missing += sorted(required_loras - loras)
    if "mistoLine_rank256.safetensors" not in controlnets:
        missing.append("mistoLine_rank256.safetensors")
    if "ip-adapter-plus_sdxl_vit-h.safetensors" not in ip_models:
        missing.append("ip-adapter-plus_sdxl_vit-h.safetensors")
    if "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors" not in clip_visions:
        missing.append("CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors")
    if missing:
        raise RuntimeError("ComfyUI missing required models: " + ", ".join(missing))


def character_by_id(prompt_pack: dict[str, Any], character_id: str) -> dict[str, Any]:
    for character in prompt_pack.get("characters", []):
        if str(character.get("character_id") or "") == character_id:
            return character
    raise KeyError(character_id)


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


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


def draw_multiline(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], max_width: int, font: ImageFont.ImageFont, fill: str) -> None:
    left, top = xy
    for line in str(text or "").splitlines():
        current = ""
        for char in line:
            candidate = current + char
            if draw.textlength(candidate, font=font) <= max_width or not current:
                current = candidate
            else:
                draw.text((left, top), current, font=font, fill=fill)
                top += font.size + 4
                current = char
        if current:
            draw.text((left, top), current, font=font, fill=fill)
            top += font.size + 4


def fonts_for_sheet() -> dict[str, ImageFont.FreeTypeFont]:
    font_path = font_path_for_sheet()
    return {"title": ImageFont.truetype(font_path, 28), "small": ImageFont.truetype(font_path, 15)}


def font_path_for_sheet() -> str:
    for path in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/simsun.ttc")]:
        if path.exists():
            return str(path)
    raise FileNotFoundError("No Chinese-capable Windows font found")


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in str(value))[:96]


def rel(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(PROJECT_ROOT))


def short_checkpoint(name: str) -> str:
    stem = Path(name).stem
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:4]
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in stem)[:52] + "_" + digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run six pose-freed character turnaround design tests")
    parser.add_argument("--prompt-pack", type=Path, default=DEFAULT_PROMPT_PACK)
    parser.add_argument("--output-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--seed", type=int, default=2026051500)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-attempts", type=int, default=360)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())