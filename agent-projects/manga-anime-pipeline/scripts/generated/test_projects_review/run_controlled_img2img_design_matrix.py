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

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from pipeline.comfy.client import ComfyClient, ComfyClientConfig
from pipeline.comfy.provenance import write_output_provenance_files
from pipeline.common.io import read_json, write_json


RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "2026-05-15_controlled_character_design_matrix"
SOURCE_RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "2026-05-15_test_projects_short_manga"
DEFAULT_PROMPT_PACK = SOURCE_RUNTIME_ROOT / "review" / "optimized_prompt_pack.json"
COMFY_INPUT_ROOT = WORKSPACE_ROOT / "ComfyUI" / "input"
COMFY_OUTPUT_ROOT = WORKSPACE_ROOT / "ComfyUI" / "output"
COMFY_INPUT_SUBDIR = "agent_manga_controlled_design"

REQUIRED_BASE_NODES = {
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "LoadImage",
    "VAEEncode",
    "KSampler",
    "VAEDecode",
    "SaveImage",
}
LINEART_NODES = {"ControlNetLoader", "ControlNetApplyAdvanced"}
IPADAPTER_NODES = {"IPAdapterModelLoader", "IPAdapterAdvanced", "CLIPVisionLoader"}

OUTPUT_SIZE = (768, 1152)

CHARACTER_CROPS = {
    "char_dark_ponytail": {
        "body": ("tests/Test_projects/QQ20260515-145001.png", [80, 40, 585, 1190]),
        "closeup": ("tests/Test_projects/QQ20260515-145053.png", [0, 0, 560, 900]),
    },
    "char_silver_longhair": {
        "body": ("tests/Test_projects/QQ20260515-145001.png", [500, 250, 970, 1230]),
        "closeup": ("tests/Test_projects/QQ20260515-145053.png", [420, 0, 1000, 900]),
    },
}


@dataclass(frozen=True)
class CheckpointCase:
    ckpt_name: str
    label: str


@dataclass(frozen=True)
class ControlMode:
    mode_id: str
    label: str
    use_lineart: bool = False
    use_ipadapter: bool = False
    control_strength: float = 0.65
    ipadapter_weight: float = 0.55
    description: str = ""


@dataclass(frozen=True)
class StyleProfile:
    profile_id: str
    label: str
    positive: str
    negative: str
    cfg: float
    steps: int


@dataclass(frozen=True)
class LoraCase:
    lora_id: str
    label: str
    lora_name: str
    strength_model: float = 0.0
    strength_clip: float = 0.0
    positive_hint: str = ""
    negative_hint: str = ""


CHECKPOINT_CASES = [
    CheckpointCase("waiIllustriousSDXL_v170.safetensors", "waiIllustriousSDXL_v170"),
    CheckpointCase("hassakuXLIllustrious_v34.safetensors", "hassakuXLIllustrious_v34"),
]

CONTROL_MODES = [
    ControlMode("img2img", "仅 img2img", description="只用原漫画角色 crop 作为 VAE latent，观察 denoise 对身份和风格迁移的影响。"),
    ControlMode("lineart", "img2img + 线稿 ControlNet", use_lineart=True, control_strength=0.62, description="在 img2img 基础上加漫画线稿结构控制，测试姿态和轮廓保持。"),
    ControlMode("ipadapter", "img2img + IPAdapter", use_ipadapter=True, ipadapter_weight=0.55, description="在 img2img 基础上加近景参考图身份控制，测试脸和发型保持。"),
    ControlMode(
        "lineart_ipadapter",
        "img2img + 线稿 ControlNet + IPAdapter",
        use_lineart=True,
        use_ipadapter=True,
        control_strength=0.52,
        ipadapter_weight=0.45,
        description="同时测试结构控制和身份控制，作为后续视频首帧候选强控制方案。",
    ),
]

STYLE_PROFILES = [
    StyleProfile(
        "source_faithful_tv",
        "原作忠实 TV 动画",
        (
            "source faithful TV anime adaptation, clean modern anime key visual, preserve the manga character identity, "
            "readable school uniform, natural teenage proportions, clear silhouette, soft cel shading, no text"
        ),
        "over-stylized redesign, different character, childlike body, fake typography, speech bubble, watermark",
        cfg=6.4,
        steps=22,
    ),
    StyleProfile(
        "mature_shoujo",
        "成熟少女漫画动画",
        (
            "mature shoujo anime character design, elegant proportions, refined face, long graceful limbs, "
            "delicate line art, emotional eyes, gentle cinematic lighting, polished production reference"
        ),
        "toddler face, chibi, mascot, overly round childish face, toy-like body, comedy deformation",
        cfg=6.9,
        steps=24,
    ),
    StyleProfile(
        "soft_watercolor_manga",
        "柔和水彩漫画感",
        (
            "soft watercolor manga illustration, airy pastel color, translucent shading, gentle paper texture, "
            "romantic school comedy tone, clean facial features, stable identity"
        ),
        "muddy colors, washed out face, overexposed, text, labels, extra characters, low contrast anatomy",
        cfg=6.2,
        steps=22,
    ),
    StyleProfile(
        "graphic_poster",
        "平面海报强风格",
        (
            "graphic anime poster style, bold clean shapes, high contrast color blocking, crisp inked outline, "
            "expressive character pose, modern promotional illustration, no words or symbols"
        ),
        "messy poster text, logo, typography, pop words, cluttered layout, extra body, split screen",
        cfg=7.0,
        steps=24,
    ),
]

LORA_CASES = [
    LoraCase("none", "无 LoRA", ""),
    LoraCase("huespark_illust", "HueSpark 插画光感", "HueSpark1llust.safetensors", 0.55, 0.45, "vivid polished illustration lighting, sparkling clean color accents"),
    LoraCase("etching_line", "蚀刻线稿质感", "etching_print_v3-4-850.safetensors", 0.45, 0.35, "etched manga line texture, crisp hand-drawn line weight"),
    LoraCase("pop_art", "Pop-Art 平面海报", "Pop-Art-6000.safetensors", 0.35, 0.25, "bold pop art color design, graphic poster feeling"),
]

BASE_NEGATIVE = (
    "worst quality, low quality, lowres, blurry, jpeg artifacts, bad anatomy, bad hands, extra fingers, missing fingers, "
    "fused fingers, deformed face, asymmetrical eyes, cropped head, out of frame, text, letters, kanji, chinese characters, "
    "random text, unreadable text, labels, logo, watermark, signature, speech bubble, blank speech bubble, duplicate character, "
    "multiple girls, two girls, group, split screen, identity drift, inconsistent hairstyle, inconsistent eye color, wrong school uniform, "
    "changed age, changed body proportions, photorealistic, 3D render"
)


def main() -> int:
    args = parse_args()
    prompt_pack = read_json(args.prompt_pack)
    object_info = get_json(args.server.rstrip("/") + "/object_info")
    validate_base_nodes(object_info)

    checkpoint_cases = available_checkpoints(object_info, args.checkpoints)
    control_modes = available_control_modes(object_info, args.control_modes)
    lora_cases = available_loras(object_info, args.loras)
    style_profiles = available_styles(args.styles)
    if not checkpoint_cases:
        raise RuntimeError("No requested checkpoints are available in ComfyUI")
    if not control_modes:
        raise RuntimeError("No usable control modes are available in ComfyUI")

    run_id = args.run_id or time.strftime("%Y%m%d_%H%M%S")
    output_root = args.output_root / run_id
    output_root.mkdir(parents=True, exist_ok=True)

    references = prepare_references(prompt_pack, output_root, run_id)
    render_reference_sheet(references, output_root / "reference_crops_sheet.jpg")

    cases = build_cases(
        characters=list(prompt_pack.get("characters", [])),
        checkpoints=checkpoint_cases,
        control_modes=control_modes,
        style_profiles=style_profiles,
        lora_cases=lora_cases,
        references=references,
        seed=args.seed,
        max_cases=args.max_cases,
    )

    client = ComfyClient(ComfyClientConfig(server=args.server, timeout_seconds=args.timeout_seconds))
    client.check_server()

    tasks: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case_id(case)}", flush=True)
        try:
            task = submit_case(
                client=client,
                case=case,
                run_id=run_id,
                output_root=output_root,
                prompt_pack_path=args.prompt_pack,
                poll_attempts=args.poll_attempts,
                poll_interval_seconds=args.poll_interval_seconds,
            )
        except Exception as error:
            task = failed_task_record(case, str(error))
        tasks.append(task)
        write_json(output_root / "controlled_design_tasks.partial.json", result_record(args, run_id, output_root, references, checkpoint_cases, control_modes, style_profiles, lora_cases, tasks))

    result = result_record(args, run_id, output_root, references, checkpoint_cases, control_modes, style_profiles, lora_cases, tasks)
    render_contact_sheets(tasks, output_root)
    write_json(output_root / "controlled_design_tasks.json", result)
    write_summary_markdown(result, output_root)
    print(json.dumps({"run_id": run_id, "output_root": rel(output_root), "tasks": len(tasks), "finished": sum(1 for task in tasks if task.get("status") == "finished")}, ensure_ascii=False, indent=2))
    return 0


def prepare_references(prompt_pack: dict[str, Any], output_root: Path, run_id: str) -> dict[str, dict[str, dict[str, str]]]:
    refs: dict[str, dict[str, dict[str, str]]] = {}
    crop_dir = output_root / "references" / "crops"
    prepared_dir = output_root / "references" / "prepared"
    comfy_dir = COMFY_INPUT_ROOT / COMFY_INPUT_SUBDIR / run_id
    crop_dir.mkdir(parents=True, exist_ok=True)
    prepared_dir.mkdir(parents=True, exist_ok=True)
    comfy_dir.mkdir(parents=True, exist_ok=True)

    for character in prompt_pack.get("characters", []):
        character_id = str(character.get("character_id") or "character")
        refs[character_id] = {}
        for ref_type, (source_rel, box) in CHARACTER_CROPS.get(character_id, {}).items():
            source_path = PROJECT_ROOT / source_rel
            crop = crop_image(source_path, box)
            crop_path = crop_dir / f"{character_id}_{ref_type}_crop.png"
            prepared_path = prepared_dir / f"{character_id}_{ref_type}_{OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}.png"
            comfy_path = comfy_dir / prepared_path.name
            crop.save(crop_path)
            prepared = fit_to_canvas(crop, OUTPUT_SIZE)
            prepared.save(prepared_path)
            shutil.copy2(prepared_path, comfy_path)
            refs[character_id][ref_type] = {
                "source_image": source_rel,
                "source_box": box,
                "crop_file": rel(crop_path),
                "prepared_file": rel(prepared_path),
                "comfy_image": f"{COMFY_INPUT_SUBDIR}/{run_id}/{prepared_path.name}",
            }
        body_ref = refs[character_id].get("body")
        if body_ref:
            prepared_path = PROJECT_ROOT / body_ref["prepared_file"]
            lineart_name = f"{character_id}_body_lineart_{OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}.png"
            lineart_path = prepared_dir / lineart_name
            comfy_path = comfy_dir / lineart_name
            with Image.open(prepared_path) as prepared_image:
                create_lineart_control(prepared_image).save(lineart_path)
            shutil.copy2(lineart_path, comfy_path)
            body_ref["lineart_file"] = rel(lineart_path)
            body_ref["lineart_comfy_image"] = f"{COMFY_INPUT_SUBDIR}/{run_id}/{lineart_name}"
    return refs


def build_cases(
    *,
    characters: list[dict[str, Any]],
    checkpoints: list[CheckpointCase],
    control_modes: list[ControlMode],
    style_profiles: list[StyleProfile],
    lora_cases: list[LoraCase],
    references: dict[str, dict[str, dict[str, str]]],
    seed: int,
    max_cases: int,
) -> list[dict[str, Any]]:
    characters = [character for character in characters if str(character.get("character_id") or "") in references]
    source_style = next(profile for profile in STYLE_PROFILES if profile.profile_id == "source_faithful_tv")
    no_lora = next(lora for lora in LORA_CASES if lora.lora_id == "none")
    best_control = next((mode for mode in control_modes if mode.mode_id == "lineart_ipadapter"), control_modes[-1])
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_case(phase: str, checkpoint: CheckpointCase, character: dict[str, Any], control: ControlMode, style: StyleProfile, lora: LoraCase, denoise: float, seed_offset: int) -> None:
        character_id = str(character.get("character_id") or "")
        if character_id not in references:
            return
        record = {
            "phase": phase,
            "checkpoint": checkpoint,
            "character": character,
            "control": control,
            "style": style,
            "lora": lora,
            "denoise": denoise,
            "seed": seed + seed_offset,
            "body_reference": references[character_id]["body"],
            "ip_reference": references[character_id].get("closeup", references[character_id]["body"]),
            "lineart_reference": references[character_id]["body"],
        }
        key = case_id(record)
        if key in seen:
            return
        seen.add(key)
        cases.append(record)

    for checkpoint_index, checkpoint in enumerate(checkpoints):
        for character_index, character in enumerate(characters):
            for denoise_index, denoise in enumerate([0.30, 0.45, 0.60]):
                for control_index, control in enumerate(control_modes):
                    add_case("denoise_control", checkpoint, character, control, source_style, no_lora, denoise, checkpoint_index * 100000 + character_index * 10000 + denoise_index * 1000 + control_index * 100)

    for checkpoint_index, checkpoint in enumerate(checkpoints):
        for character_index, character in enumerate(characters):
            for style_index, style in enumerate(style_profiles):
                for lora_index, lora in enumerate(lora_cases):
                    add_case("style_lora", checkpoint, character, best_control, style, lora, 0.45, 500000 + checkpoint_index * 100000 + character_index * 10000 + style_index * 1000 + lora_index * 100)

    if max_cases:
        return cases[:max_cases]
    return cases


def submit_case(
    *,
    client: ComfyClient,
    case: dict[str, Any],
    run_id: str,
    output_root: Path,
    prompt_pack_path: Path,
    poll_attempts: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    workflow = build_workflow(case, run_id)
    cid = case_id(case)
    control: ControlMode = case["control"]
    style: StyleProfile = case["style"]
    lora: LoraCase = case["lora"]
    checkpoint: CheckpointCase = case["checkpoint"]
    character = case["character"]
    character_id = str(character.get("character_id") or "character")
    case_dir = output_root / "results" / safe_name(case["phase"]) / safe_name(control.mode_id) / safe_name(style.profile_id) / safe_name(lora.lora_id) / safe_name(checkpoint.label)
    case_dir.mkdir(parents=True, exist_ok=True)
    client_id = f"agent:copilot|workflow:controlled_img2img_design_matrix|run:{run_id}"
    extra_data = {
        "agent": "copilot",
        "workflow_name": "controlled_img2img_design_matrix",
        "source": "manga-anime-pipeline",
        "phase": case["phase"],
        "character_id": character_id,
        "checkpoint": checkpoint.ckpt_name,
        "control_mode": control.mode_id,
        "style_profile": style.profile_id,
        "lora": lora.lora_name or "none",
        "denoise": case["denoise"],
        "seed": case["seed"],
        "notes": (
            f"controlled matrix; phase={case['phase']}; checkpoint={checkpoint.ckpt_name}; character={character_id}; "
            f"denoise={case['denoise']}; control={control.mode_id}; style={style.profile_id}; lora={lora.lora_name or 'none'}; "
            f"prompt_pack={rel(prompt_pack_path)}; body_ref={case['body_reference']['prepared_file']}; "
            f"lineart_ref={case['lineart_reference'].get('lineart_file', '')}; ip_ref={case['ip_reference']['prepared_file']}"
        ),
    }
    response = client.submit_prompt({"prompt": workflow, "client_id": client_id, "extra_data": extra_data})
    prompt_id = str(response.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI submit response missing prompt_id: {response}")
    entry = wait_for_history(client, prompt_id, poll_attempts, poll_interval_seconds)
    copied = copy_history_images(entry, case_dir, character_id, cid)
    task_context = task_record(case, prompt_id=prompt_id, output_files=[rel(path) for path in copied], provenance_files=[], status="finished" if copied else "finished_without_images")
    provenance_files = write_output_provenance_files(
        copied,
        project_root=PROJECT_ROOT,
        workflow=workflow,
        workflow_name="controlled_img2img_design_matrix",
        prompt_id=prompt_id,
        client_id=client_id,
        extra_data=extra_data,
        task_context=task_context,
        history_status=entry.get("status") if isinstance(entry.get("status"), dict) else {},
    )
    task_context["provenance_files"] = [rel(path) for path in provenance_files]
    return task_context


def build_workflow(case: dict[str, Any], run_id: str) -> dict[str, Any]:
    checkpoint: CheckpointCase = case["checkpoint"]
    control: ControlMode = case["control"]
    lora: LoraCase = case["lora"]
    character = case["character"]
    character_id = str(character.get("character_id") or "character")
    positive = build_positive_prompt(case)
    negative = build_negative_prompt(case)
    filename_prefix = f"manga_anime_pipeline/controlled_character_design/{run_id}/{safe_name(case_id(case))}/{character_id}"
    workflow: dict[str, Any] = {}
    next_id = 1

    def add(class_type: str, inputs: dict[str, Any]) -> str:
        nonlocal next_id
        node_id = str(next_id)
        next_id += 1
        workflow[node_id] = {"class_type": class_type, "inputs": inputs}
        return node_id

    ckpt = add("CheckpointLoaderSimple", {"ckpt_name": checkpoint.ckpt_name})
    model_ref: list[Any] = [ckpt, 0]
    clip_ref: list[Any] = [ckpt, 1]
    vae_ref: list[Any] = [ckpt, 2]

    if lora.lora_name:
        lora_node = add(
            "LoraLoader",
            {
                "model": model_ref,
                "clip": clip_ref,
                "lora_name": lora.lora_name,
                "strength_model": lora.strength_model,
                "strength_clip": lora.strength_clip,
            },
        )
        model_ref = [lora_node, 0]
        clip_ref = [lora_node, 1]

    body_image = add("LoadImage", {"image": case["body_reference"]["comfy_image"]})
    ip_image = body_image
    if control.use_ipadapter:
        ip_image = add("LoadImage", {"image": case["ip_reference"]["comfy_image"]})
        ip_model = add("IPAdapterModelLoader", {"ipadapter_file": "ip-adapter-plus_sdxl_vit-h.safetensors"})
        clip_vision = add("CLIPVisionLoader", {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"})
        ip_node = add(
            "IPAdapterAdvanced",
            {
                "model": model_ref,
                "ipadapter": [ip_model, 0],
                "image": [ip_image, 0],
                "weight": control.ipadapter_weight,
                "weight_type": "style and composition",
                "combine_embeds": "average",
                "start_at": 0.0,
                "end_at": 0.85,
                "embeds_scaling": "V only",
                "clip_vision": [clip_vision, 0],
            },
        )
        model_ref = [ip_node, 0]

    positive_node = add("CLIPTextEncode", {"clip": clip_ref, "text": positive})
    negative_node = add("CLIPTextEncode", {"clip": clip_ref, "text": negative})
    positive_ref: list[Any] = [positive_node, 0]
    negative_ref: list[Any] = [negative_node, 0]

    if control.use_lineart:
        lineart = add("LoadImage", {"image": case["lineart_reference"]["lineart_comfy_image"]})
        controlnet = add("ControlNetLoader", {"control_net_name": "mistoLine_rank256.safetensors"})
        apply_control = add(
            "ControlNetApplyAdvanced",
            {
                "positive": positive_ref,
                "negative": negative_ref,
                "control_net": [controlnet, 0],
                "image": [lineart, 0],
                "strength": control.control_strength,
                "start_percent": 0.0,
                "end_percent": 0.75,
            },
        )
        positive_ref = [apply_control, 0]
        negative_ref = [apply_control, 1]

    latent = add("VAEEncode", {"pixels": [body_image, 0], "vae": vae_ref})
    sampler = add(
        "KSampler",
        {
            "model": model_ref,
            "positive": positive_ref,
            "negative": negative_ref,
            "latent_image": [latent, 0],
            "seed": case["seed"],
            "steps": case["style"].steps,
            "cfg": case["style"].cfg,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": case["denoise"],
        },
    )
    decoded = add("VAEDecode", {"samples": [sampler, 0], "vae": vae_ref})
    add("SaveImage", {"images": [decoded, 0], "filename_prefix": filename_prefix})
    return workflow


def build_positive_prompt(case: dict[str, Any]) -> str:
    character = case["character"]
    style: StyleProfile = case["style"]
    lora: LoraCase = case["lora"]
    character_id = str(character.get("character_id") or "")
    parts = [
        "masterpiece, best quality, clean anime image-to-video reference, single character only, no text, no speech bubble",
        "use the source manga crop as identity and structure reference, preserve hairstyle, eye color, school uniform, age impression",
        role_prompt(character_id),
        traits_prompt(character),
        str(character.get("continuity_prompt") or ""),
        style.positive,
        lora.positive_hint,
    ]
    return join_prompt(parts)


def build_negative_prompt(case: dict[str, Any]) -> str:
    character = case["character"]
    style: StyleProfile = case["style"]
    lora: LoraCase = case["lora"]
    parts = [BASE_NEGATIVE, role_negative(str(character.get("character_id") or "")), style.negative, lora.negative_hint, str(character.get("negative_prompt") or "")]
    return join_prompt(parts)


def role_prompt(character_id: str) -> str:
    if character_id == "char_dark_ponytail":
        return "tall slender high school girl, dark purple high ponytail, purple eyes, lively teasing smile, confident but cute, about 172cm impression"
    if character_id == "char_silver_longhair":
        return "petite high school girl, silver white long hair, black hairband, green eyes, gentle smile, soft playful mood, about 142cm impression"
    return ""


def role_negative(character_id: str) -> str:
    if character_id == "char_dark_ponytail":
        return "silver hair, white hair, green eyes, extra pale-haired girl, short child body"
    if character_id == "char_silver_longhair":
        return "purple hair, high ponytail, purple eyes, extra dark-haired girl, toddler face"
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
            raise RuntimeError(history_error_message(status_info))
        if entry.get("outputs"):
            return entry
    raise TimeoutError(f"ComfyUI history did not finish for {prompt_id}")


def copy_history_images(entry: dict[str, Any], output_dir: Path, character_id: str, cid: str) -> list[Path]:
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
            target = output_dir / f"{safe_name(cid)}__{character_id}_{len(copied) + 1:02d}{source.suffix}"
            shutil.copy2(source, target)
            copied.append(target)
    return copied


def render_contact_sheets(tasks: list[dict[str, Any]], output_root: Path) -> None:
    render_sheet(tasks, output_root / "all_success_contact_sheet.jpg", "全部成功结果")
    for key, folder, prefix in [
        ("phase", "by_phase", "阶段"),
        ("character_id", "by_character", "角色"),
        ("checkpoint_label", "by_checkpoint", "模型"),
        ("control_mode", "by_control", "控制方式"),
        ("style_profile", "by_style", "风格提示词"),
        ("lora_id", "by_lora", "LoRA"),
    ]:
        values = sorted({str(task.get(key) or "unknown") for task in tasks})
        target_dir = output_root / folder
        target_dir.mkdir(exist_ok=True)
        for value in values:
            render_sheet([task for task in tasks if str(task.get(key) or "unknown") == value], target_dir / f"{safe_name(value)}.jpg", f"{prefix}: {value}")


def render_sheet(tasks: list[dict[str, Any]], output_path: Path, title: str) -> None:
    shown = [task for task in tasks if task.get("output_files")]
    if not shown:
        return
    thumb_w, thumb_h = 210, 315
    label_h = 118
    margin = 28
    cols = min(6, max(1, len(shown)))
    rows = (len(shown) + cols - 1) // cols
    width = margin * 2 + cols * thumb_w + (cols - 1) * 18
    height = margin * 2 + 58 + rows * (thumb_h + label_h + 18)
    sheet = Image.new("RGB", (width, height), "#f6f5f1")
    draw = ImageDraw.Draw(sheet)
    fonts = fonts_for_sheet()
    draw.text((margin, margin), title, font=fonts["title"], fill="#1d1c19")
    for index, task in enumerate(shown):
        row, col = divmod(index, cols)
        x = margin + col * (thumb_w + 18)
        y = margin + 58 + row * (thumb_h + label_h + 18)
        draw.rounded_rectangle((x - 8, y - 8, x + thumb_w + 8, y + thumb_h + label_h + 8), radius=8, fill="#ffffff", outline="#d5d1c8")
        image_path = PROJECT_ROOT / task["output_files"][0]
        paste_image(sheet, image_path, (x, y), (thumb_w, thumb_h))
        text = f"{task['checkpoint_label']}\n{task['control_mode']} / d={task['denoise']}\n{task['style_profile']} / {task['lora_id']}\n{task['display_name']}"
        draw_multiline(draw, text, (x, y + thumb_h + 8), thumb_w, fonts["small"], "#292621")
    sheet.save(output_path, quality=92)


def render_reference_sheet(references: dict[str, dict[str, dict[str, str]]], output_path: Path) -> None:
    items: list[tuple[str, str, Path]] = []
    for character_id, refs in references.items():
        for ref_type, ref in refs.items():
            items.append((character_id, ref_type, PROJECT_ROOT / ref["prepared_file"]))
    if not items:
        return
    thumb_w, thumb_h = 210, 315
    label_h = 54
    margin = 24
    cols = min(4, len(items))
    rows = (len(items) + cols - 1) // cols
    width = margin * 2 + cols * thumb_w + (cols - 1) * 18
    height = margin * 2 + 52 + rows * (thumb_h + label_h + 18)
    sheet = Image.new("RGB", (width, height), "#f6f5f1")
    draw = ImageDraw.Draw(sheet)
    fonts = fonts_for_sheet()
    draw.text((margin, margin), "角色 crop 与 ComfyUI 输入图", font=fonts["title"], fill="#1d1c19")
    for index, (character_id, ref_type, path) in enumerate(items):
        row, col = divmod(index, cols)
        x = margin + col * (thumb_w + 18)
        y = margin + 52 + row * (thumb_h + label_h + 18)
        paste_image(sheet, path, (x, y), (thumb_w, thumb_h))
        draw_multiline(draw, f"{character_id}\n{ref_type}", (x, y + thumb_h + 8), thumb_w, fonts["small"], "#292621")
    sheet.save(output_path, quality=92)


def write_summary_markdown(result: dict[str, Any], output_root: Path) -> None:
    def local(path: Path) -> str:
        return str(path.relative_to(output_root)).replace("\\", "/")

    finished = [task for task in result["tasks"] if task.get("status") == "finished"]
    failed = [task for task in result["tasks"] if task.get("status") != "finished"]
    lines = [
        "# 受控角色设计图矩阵测试结果",
        "",
        f"- run_id: `{result['run_id']}`",
        f"- 输出目录: `{result['output_root']}`",
        f"- 任务 JSON: `{rel(output_root / 'controlled_design_tasks.json')}`",
        f"- 成功/总数: `{len(finished)} / {len(result['tasks'])}`",
        f"- crop 总览: `{rel(output_root / 'reference_crops_sheet.jpg')}`",
        f"- 成功结果总览: `{rel(output_root / 'all_success_contact_sheet.jpg')}`",
        "",
        "## 参考 crop",
        "",
        f"![reference crops]({local(output_root / 'reference_crops_sheet.jpg')})",
        "",
    ]
    if (output_root / "all_success_contact_sheet.jpg").exists():
        lines.extend(["## 成功结果总览", "", f"![all success]({local(output_root / 'all_success_contact_sheet.jpg')})", ""])
    lines.extend(
        [
            "## 本轮覆盖的可控项",
            "",
            "| 类别 | 测试内容 |",
            "|---|---|",
            f"| checkpoint | {', '.join('`' + item + '`' for item in result['checkpoints'])} |",
            f"| control | {', '.join('`' + item['mode_id'] + '`' for item in result['control_modes'])} |",
            f"| denoise | `0.30`, `0.45`, `0.60`；style/LoRA 组合固定用 `0.45` |",
            f"| style profile | {', '.join('`' + item['profile_id'] + '`' for item in result['style_profiles'])} |",
            f"| LoRA | {', '.join('`' + item['lora_id'] + '`' for item in result['lora_cases'])} |",
            "",
            "## 推荐观察方式",
            "",
            "- 先看 `by_control/`：判断线稿 ControlNet 与 IPAdapter 是否真的提升了身份保持。",
            "- 再看 `by_style/`：判断只是换提示词时，风格能拉开多少。",
            "- 最后看 `by_lora/`：判断风格 LoRA 是增强风格，还是破坏角色身份或模型兼容性。",
            "- 真正适合后续 I2V 的候选，要同时满足：发型/发色/身高气质稳定，画面无伪文字，动作起点明确，脸和手没有明显崩坏。",
            "",
            "## 分组拼图索引",
            "",
        ]
    )
    for folder, label in [("by_phase", "阶段"), ("by_character", "角色"), ("by_checkpoint", "模型"), ("by_control", "控制方式"), ("by_style", "风格"), ("by_lora", "LoRA")]:
        target_dir = output_root / folder
        if not target_dir.exists():
            continue
        lines.append(f"### {label}")
        lines.append("")
        for sheet in sorted(target_dir.glob("*.jpg")):
            lines.append(f"- `{sheet.stem}`: `{rel(sheet)}`")
        lines.append("")
    lines.extend(["## 单图结果表", ""])
    lines.append("| 状态 | 阶段 | 模型 | 角色 | denoise | 控制 | 风格 | LoRA | 输出图 | provenance | 备注 |")
    lines.append("|---|---|---|---|---:|---|---|---|---|---|---|")
    for task in result["tasks"]:
        image = task["output_files"][0] if task.get("output_files") else ""
        sidecar = task["provenance_files"][0] if task.get("provenance_files") else ""
        note = task.get("error_message", "")
        lines.append(
            "| "
            f"`{task['status']}` | `{task['phase']}` | `{task['checkpoint_label']}` | {task['display_name']} | {task['denoise']} | "
            f"`{task['control_mode']}` | `{task['style_profile']}` | `{task['lora_id']}` | `{image}` | `{sidecar}` | {note} |"
        )
    if failed:
        lines.extend(["", "## 失败记录", ""])
        for task in failed:
            lines.append(f"- `{task['checkpoint_label']} / {task['control_mode']} / {task['style_profile']} / {task['lora_id']} / {task['character_id']}`: {task.get('error_message')}")
    (output_root / "controlled_design_matrix_summary.md").write_text("\n".join(lines), encoding="utf-8")


def task_record(case: dict[str, Any], *, prompt_id: str, output_files: list[str], provenance_files: list[str], status: str, error_message: str = "") -> dict[str, Any]:
    checkpoint: CheckpointCase = case["checkpoint"]
    control: ControlMode = case["control"]
    style: StyleProfile = case["style"]
    lora: LoraCase = case["lora"]
    character = case["character"]
    return {
        "case_id": case_id(case),
        "phase": case["phase"],
        "status": status,
        "error_message": error_message,
        "prompt_id": prompt_id,
        "checkpoint": checkpoint.ckpt_name,
        "checkpoint_label": checkpoint.label,
        "character_id": str(character.get("character_id") or ""),
        "display_name": character.get("display_name"),
        "denoise": case["denoise"],
        "seed": case["seed"],
        "control_mode": control.mode_id,
        "control_label": control.label,
        "control_strength": control.control_strength if control.use_lineart else 0.0,
        "ipadapter_weight": control.ipadapter_weight if control.use_ipadapter else 0.0,
        "style_profile": style.profile_id,
        "style_label": style.label,
        "cfg": style.cfg,
        "steps": style.steps,
        "lora_id": lora.lora_id,
        "lora_label": lora.label,
        "lora_name": lora.lora_name or "none",
        "lora_strength_model": lora.strength_model,
        "lora_strength_clip": lora.strength_clip,
        "body_reference": case["body_reference"],
        "lineart_reference": case["lineart_reference"],
        "ip_reference": case["ip_reference"],
        "positive_prompt": build_positive_prompt(case),
        "negative_prompt": build_negative_prompt(case),
        "output_files": output_files,
        "provenance_files": provenance_files,
    }


def failed_task_record(case: dict[str, Any], error_message: str) -> dict[str, Any]:
    return task_record(case, prompt_id="", output_files=[], provenance_files=[], status="failed", error_message=error_message)


def result_record(
    args: argparse.Namespace,
    run_id: str,
    output_root: Path,
    references: dict[str, dict[str, dict[str, str]]],
    checkpoints: list[CheckpointCase],
    control_modes: list[ControlMode],
    style_profiles: list[StyleProfile],
    lora_cases: list[LoraCase],
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "workflow_name": "controlled_img2img_design_matrix",
        "run_id": run_id,
        "server": args.server,
        "prompt_pack": rel(args.prompt_pack),
        "output_root": rel(output_root),
        "output_size": list(OUTPUT_SIZE),
        "references": references,
        "checkpoints": [case.ckpt_name for case in checkpoints],
        "control_modes": [control.__dict__ for control in control_modes],
        "style_profiles": [style.__dict__ for style in style_profiles],
        "lora_cases": [lora.__dict__ for lora in lora_cases],
        "tasks": tasks,
    }


def available_checkpoints(object_info: dict[str, Any], requested: list[str]) -> list[CheckpointCase]:
    ckpt_values = object_info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
    available = set(ckpt_values)
    names = requested or [case.ckpt_name for case in CHECKPOINT_CASES]
    return [CheckpointCase(name, short_checkpoint(name)) for name in names if name in available]


def available_control_modes(object_info: dict[str, Any], requested: list[str]) -> list[ControlMode]:
    selected = requested or [mode.mode_id for mode in CONTROL_MODES]
    by_id = {mode.mode_id: mode for mode in CONTROL_MODES}
    controlnet_values = object_info.get("ControlNetLoader", {}).get("input", {}).get("required", {}).get("control_net_name", [[]])[0]
    ipadapter_values = object_info.get("IPAdapterModelLoader", {}).get("input", {}).get("required", {}).get("ipadapter_file", [[]])[0]
    clip_values = object_info.get("CLIPVisionLoader", {}).get("input", {}).get("required", {}).get("clip_name", [[]])[0]
    modes: list[ControlMode] = []
    for mode_id in selected:
        mode = by_id.get(mode_id)
        if not mode:
            continue
        if mode.use_lineart and (not LINEART_NODES.issubset(set(object_info)) or "mistoLine_rank256.safetensors" not in controlnet_values):
            continue
        if mode.use_ipadapter and (not IPADAPTER_NODES.issubset(set(object_info)) or "ip-adapter-plus_sdxl_vit-h.safetensors" not in ipadapter_values or "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors" not in clip_values):
            continue
        modes.append(mode)
    return modes


def available_loras(object_info: dict[str, Any], requested: list[str]) -> list[LoraCase]:
    lora_values = object_info.get("LoraLoader", {}).get("input", {}).get("required", {}).get("lora_name", [[]])[0]
    available = set(lora_values)
    selected = requested or [case.lora_id for case in LORA_CASES]
    by_id = {case.lora_id: case for case in LORA_CASES}
    cases: list[LoraCase] = []
    for lora_id in selected:
        case = by_id.get(lora_id)
        if not case:
            continue
        if not case.lora_name or case.lora_name in available:
            cases.append(case)
    return cases


def available_styles(requested: list[str]) -> list[StyleProfile]:
    selected = requested or [style.profile_id for style in STYLE_PROFILES]
    by_id = {style.profile_id: style for style in STYLE_PROFILES}
    return [by_id[style_id] for style_id in selected if style_id in by_id]


def validate_base_nodes(object_info: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_BASE_NODES - set(object_info))
    if missing:
        raise RuntimeError("ComfyUI missing required base nodes: " + ", ".join(missing))


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


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


def fit_to_canvas(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = image.convert("RGB")
    fitted = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "#f8f5f0")
    canvas.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    return canvas


def create_lineart_control(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image.convert("RGB"))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    edges = ImageOps.autocontrast(edges)
    lineart = edges.point(lambda value: 0 if value > 28 else 255)
    lineart = lineart.filter(ImageFilter.MinFilter(3))
    return lineart.convert("RGB")


def paste_image(sheet: Image.Image, image_path: Path, xy: tuple[int, int], size: tuple[int, int]) -> None:
    with Image.open(image_path) as image:
        image = image.convert("RGB")
        image.thumbnail(size, Image.Resampling.LANCZOS)
        frame = Image.new("RGB", size, "#e1dfd8")
        frame.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
        sheet.paste(frame, xy)


def draw_multiline(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int], max_width: int, font: ImageFont.ImageFont, fill: str) -> None:
    x, y = xy
    for line in str(text or "").splitlines():
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
    return {"title": ImageFont.truetype(font_path, 28), "small": ImageFont.truetype(font_path, 15)}


def font_path_for_sheet() -> str:
    for path in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf"), Path("C:/Windows/Fonts/simsun.ttc")]:
        if path.exists():
            return str(path)
    raise FileNotFoundError("No Chinese-capable Windows font found")


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


def case_id(case: dict[str, Any]) -> str:
    checkpoint: CheckpointCase = case["checkpoint"]
    control: ControlMode = case["control"]
    style: StyleProfile = case["style"]
    lora: LoraCase = case["lora"]
    character = case["character"]
    return "__".join(
        [
            str(case["phase"]),
            checkpoint.label,
            str(character.get("character_id") or "character"),
            f"d{str(case['denoise']).replace('.', '')}",
            control.mode_id,
            style.profile_id,
            lora.lora_id,
        ]
    )


def history_error_message(status_info: dict[str, Any]) -> str:
    messages = status_info.get("messages") if isinstance(status_info, dict) else None
    return json.dumps(messages or status_info, ensure_ascii=False)[:2000]


def short_checkpoint(name: str) -> str:
    stem = Path(name).stem
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:4]
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in stem)[:52] + "_" + digest


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in str(value))[:96]


def rel(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run controlled img2img/IPAdapter/ControlNet/LoRA character design matrix")
    parser.add_argument("--prompt-pack", type=Path, default=DEFAULT_PROMPT_PACK)
    parser.add_argument("--output-root", type=Path, default=RUNTIME_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--seed", type=int, default=2026051511)
    parser.add_argument("--checkpoints", nargs="*", default=[])
    parser.add_argument("--control-modes", nargs="*", default=[])
    parser.add_argument("--styles", nargs="*", default=[])
    parser.add_argument("--loras", nargs="*", default=[])
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-attempts", type=int, default=240)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())