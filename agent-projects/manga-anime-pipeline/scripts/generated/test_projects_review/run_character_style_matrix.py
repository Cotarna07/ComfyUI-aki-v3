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
DEFAULT_OUTPUT_ROOT = REVIEW_DIR / "style_matrix"
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
class StyleProfile:
    profile_id: str
    label: str
    positive_suffix: str
    negative_suffix: str
    cfg: float = 6.5
    steps: int = 24
    width: int = 832
    height: int = 1216


CHECKPOINT_CASES = [
    CheckpointCase("waiIllustriousSDXL_v170.safetensors", "waiIllustriousSDXL_v170"),
    CheckpointCase("animagineXLV31_v31.safetensors", "animagineXLV31_v31"),
    CheckpointCase("hassakuXLIllustrious_v34.safetensors", "hassakuXLIllustrious_v34"),
]

STYLE_PROFILES = [
    StyleProfile(
        profile_id="balanced_reference",
        label="均衡角色设定",
        positive_suffix=(
            "anime character reference, clean full body, neutral standing pose, balanced head-to-body ratio, "
            "age-appropriate high school character, polished TV anime style, clean line art, soft cel shading"
        ),
        negative_suffix=(
            "childlike proportions, toddler face, oversized head, chibi, super deformed, baby face, "
            "kindergarten style, doll-like body, childish costume"
        ),
    ),
    StyleProfile(
        profile_id="mature_shoujo",
        label="成熟少女漫画比例",
        positive_suffix=(
            "elegant shoujo anime proportions, refined face, longer limbs, smaller head, graceful posture, "
            "confident high school senior impression, fashion design sheet, calm mature expression, clean adult-like draftsmanship"
        ),
        negative_suffix=(
            "low age impression, childlike face, loli style, chibi, big baby eyes, round toddler cheeks, "
            "short child body, toy-like proportions, childish mood"
        ),
        cfg=7.0,
    ),
    StyleProfile(
        profile_id="source_faithful",
        label="原漫画轻喜剧还原",
        positive_suffix=(
            "faithful to the source short manga, light comedy school romance tone, expressive but not childish, "
            "clean manga-to-anime adaptation, preserve height contrast, natural teenage proportions, bright but restrained colors"
        ),
        negative_suffix=(
            "too young, preschool look, chibi, mascot style, childish redesign, excessive moe simplification, "
            "overly round face, toy-like body"
        ),
        cfg=6.2,
    ),
]

BASE_NEGATIVE = (
    "worst quality, low quality, lowres, blurry, jpeg artifacts, bad anatomy, bad hands, extra fingers, "
    "missing fingers, fused fingers, deformed face, cropped head, cropped body, text, letters, kanji, "
    "chinese characters, labels, callout boxes, watermark, logo, speech bubble, blank speech bubble, "
    "empty bubble, white oval, floating icon, duplicate body, multiple girls, two girls, group, split screen, "
    "identity drift, wrong school uniform, inconsistent hairstyle, inconsistent eye color, photorealistic, 3D render"
)


def main() -> int:
    args = parse_args()
    prompt_pack = read_json(args.prompt_pack)
    object_info = get_json(args.server.rstrip("/") + "/object_info")
    validate_nodes(object_info)
    checkpoint_cases = available_checkpoints(object_info, args.checkpoints)
    if not checkpoint_cases:
        raise RuntimeError("No requested checkpoints are available in ComfyUI")

    run_id = args.run_id or time.strftime("%Y%m%d_%H%M%S")
    output_root = args.output_root / run_id
    output_root.mkdir(parents=True, exist_ok=True)

    client = ComfyClient(ComfyClientConfig(server=args.server, timeout_seconds=args.timeout_seconds))
    client.check_server()

    tasks: list[dict[str, Any]] = []
    characters = list(prompt_pack.get("characters", []))
    for checkpoint_index, checkpoint in enumerate(checkpoint_cases):
        for profile_index, profile in enumerate(STYLE_PROFILES):
            for character_index, character in enumerate(characters):
                seed = args.seed + checkpoint_index * 10000 + profile_index * 1000 + character_index * 101
                task = submit_case(
                    client=client,
                    checkpoint=checkpoint,
                    profile=profile,
                    character=character,
                    run_id=run_id,
                    seed=seed,
                    output_root=output_root,
                    poll_attempts=args.poll_attempts,
                    poll_interval_seconds=args.poll_interval_seconds,
                )
                tasks.append(task)

    result = {
        "workflow_name": "character_style_matrix_sdxl",
        "run_id": run_id,
        "server": args.server,
        "prompt_pack": str(args.prompt_pack.relative_to(PROJECT_ROOT)),
        "output_root": str(output_root.relative_to(PROJECT_ROOT)),
        "checkpoints": [case.ckpt_name for case in checkpoint_cases],
        "profiles": [profile.profile_id for profile in STYLE_PROFILES],
        "tasks": tasks,
    }
    render_contact_sheets(tasks, output_root)
    write_review_index(result, output_root)
    write_json(output_root / "matrix_tasks.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def submit_case(
    *,
    client: ComfyClient,
    checkpoint: CheckpointCase,
    profile: StyleProfile,
    character: dict[str, Any],
    run_id: str,
    seed: int,
    output_root: Path,
    poll_attempts: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    character_id = str(character.get("character_id") or "character")
    condition_id = f"{checkpoint.label}__{profile.profile_id}"
    case_dir = output_root / "by_condition" / condition_id
    case_dir.mkdir(parents=True, exist_ok=True)
    positive = build_positive_prompt(character, profile)
    negative = build_negative_prompt(character, profile)
    filename_prefix = f"manga_anime_pipeline/test_projects_short_manga/style_matrix/{run_id}/{condition_id}/{character_id}"
    workflow = build_sdxl_workflow(
        checkpoint=checkpoint.ckpt_name,
        positive=positive,
        negative=negative,
        width=profile.width,
        height=profile.height,
        steps=profile.steps,
        cfg=profile.cfg,
        seed=seed,
        filename_prefix=filename_prefix,
    )
    client_id = f"agent:codex|workflow:character_style_matrix_sdxl|run:{run_id}"
    extra_data = {
        "agent": "codex",
        "workflow_name": "character_style_matrix_sdxl",
        "source": "manga-anime-pipeline",
        "character_id": character_id,
        "checkpoint": checkpoint.ckpt_name,
        "profile": profile.profile_id,
        "seed": seed,
        "notes": (
            f"matrix test; checkpoint={checkpoint.ckpt_name}; profile={profile.profile_id}; "
            f"size={profile.width}x{profile.height}; steps={profile.steps}; cfg={profile.cfg}"
        ),
    }
    payload = {
        "prompt": workflow,
        "client_id": client_id,
        "extra_data": extra_data,
    }
    response = client.submit_prompt(payload)
    prompt_id = str(response.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI submit response missing prompt_id: {response}")
    entry = wait_for_history(client, prompt_id, poll_attempts, poll_interval_seconds)
    copied = copy_history_images(entry, case_dir, character_id)
    task_context = {
        "condition_id": condition_id,
        "checkpoint": checkpoint.ckpt_name,
        "checkpoint_label": checkpoint.label,
        "profile_id": profile.profile_id,
        "profile_label": profile.label,
        "character_id": character_id,
        "display_name": character.get("display_name"),
        "seed": seed,
        "cfg": profile.cfg,
        "steps": profile.steps,
        "size": [profile.width, profile.height],
        "positive_prompt": positive,
        "negative_prompt": negative,
    }
    provenance_files = write_output_provenance_files(
        copied,
        project_root=PROJECT_ROOT,
        workflow=workflow,
        workflow_name="character_style_matrix_sdxl",
        prompt_id=prompt_id,
        client_id=client_id,
        extra_data=extra_data,
        task_context=task_context,
        history_status=entry.get("status") if isinstance(entry.get("status"), dict) else {},
    )
    return {
        **task_context,
        "prompt_id": prompt_id,
        "output_files": [str(path.relative_to(PROJECT_ROOT)) for path in copied],
        "provenance_files": [str(path.relative_to(PROJECT_ROOT)) for path in provenance_files],
        "status": "finished" if copied else "finished_without_images",
    }


def build_positive_prompt(character: dict[str, Any], profile: StyleProfile) -> str:
    character_id = str(character.get("character_id") or "")
    parts = [
        "masterpiece, best quality, anime style, polished key visual quality",
        "(solo:1.5), (single character only:1.5), one full body character, centered composition",
        "clean character reference illustration, front view, standing pose, simple relaxed arms",
        "plain warm gray studio background, clean empty background, uncluttered composition",
        "crisp line art, delicate cel shading, soft studio lighting, detailed eyes, clean silhouette",
        "Japanese navy-and-white sailor school uniform, bow tie, pleated skirt, loafers",
        role_prompt(character_id),
        traits_prompt(character),
        profile.positive_suffix,
    ]
    return join_prompt(parts)


def build_negative_prompt(character: dict[str, Any], profile: StyleProfile) -> str:
    parts = [
        BASE_NEGATIVE,
        role_negative(str(character.get("character_id") or "")),
        profile.negative_suffix,
        str(character.get("optimized_negative_prompt") or character.get("negative_prompt") or ""),
    ]
    return join_prompt(parts)


def role_prompt(character_id: str) -> str:
    if character_id == "char_dark_ponytail":
        return (
            "tall slender high school girl, approximately 172cm impression, dark purple hair, "
            "high ponytail tied with a simple ribbon, long side locks, purple eyes, lively mischievous smile, "
            "confident playful posture"
        )
    if character_id == "char_silver_longhair":
        return (
            "petite but age-appropriate high school girl, approximately 142cm impression, silver white long straight hair, "
            "black hairband, green eyes, gentle soft smile, calm posture"
        )
    return ""


def role_negative(character_id: str) -> str:
    if character_id == "char_dark_ponytail":
        return "silver hair, white hair, green eyes, second girl, extra character, pale-haired girl"
    if character_id == "char_silver_longhair":
        return "purple hair, high ponytail, purple eyes, second girl, extra character, dark-haired girl"
    return ""


def traits_prompt(character: dict[str, Any]) -> str:
    traits = character.get("visual_traits") or {}
    parts = [
        str(traits.get("hair_color") or ""),
        str(traits.get("hair_style") or ""),
        str(traits.get("eye_color") or ""),
        str(traits.get("outfit") or ""),
        str(traits.get("height") or ""),
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
                "sampler_name": "euler",
                "scheduler": "normal",
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
    render_sheet(tasks, output_root / "all_conditions_contact_sheet.png", "全部条件横向对比")
    by_checkpoint_dir = output_root / "by_checkpoint"
    by_profile_dir = output_root / "by_profile"
    by_checkpoint_dir.mkdir(exist_ok=True)
    by_profile_dir.mkdir(exist_ok=True)
    for checkpoint in sorted({task["checkpoint_label"] for task in tasks}):
        render_sheet(
            [task for task in tasks if task["checkpoint_label"] == checkpoint],
            by_checkpoint_dir / f"{checkpoint}.png",
            f"按模型查看：{checkpoint}",
        )
    for profile in sorted({task["profile_id"] for task in tasks}):
        label = next(task["profile_label"] for task in tasks if task["profile_id"] == profile)
        render_sheet(
            [task for task in tasks if task["profile_id"] == profile],
            by_profile_dir / f"{profile}.png",
            f"按风格查看：{label}",
        )


def render_sheet(tasks: list[dict[str, Any]], output_path: Path, title: str) -> None:
    thumb_w, thumb_h = 260, 380
    label_h = 96
    margin = 28
    cols = 6 if len(tasks) >= 6 else max(1, len(tasks))
    rows = (len(tasks) + cols - 1) // cols
    width = margin * 2 + cols * thumb_w + (cols - 1) * 18
    height = margin * 2 + 56 + rows * (thumb_h + label_h + 18)
    sheet = Image.new("RGB", (width, height), "#f6f5f1")
    draw = ImageDraw.Draw(sheet)
    fonts = fonts_for_sheet()
    draw.text((margin, margin), title, font=fonts["title"], fill="#1d1c19")
    for index, task in enumerate(tasks):
        row, col = divmod(index, cols)
        x = margin + col * (thumb_w + 18)
        y = margin + 56 + row * (thumb_h + label_h + 18)
        draw.rounded_rectangle((x - 8, y - 8, x + thumb_w + 8, y + thumb_h + label_h + 8), radius=10, fill="#ffffff", outline="#d5d1c8")
        image_path = first_existing(task.get("output_files", []))
        if image_path:
            with Image.open(image_path) as image:
                image = image.convert("RGB")
                image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                frame = Image.new("RGB", (thumb_w, thumb_h), "#e1dfd8")
                frame.paste(image, ((thumb_w - image.width) // 2, (thumb_h - image.height) // 2))
                sheet.paste(frame, (x, y))
        text = f"{task['checkpoint_label']}\n{task['profile_label']}\n{task['display_name']}"
        draw_multiline(draw, text, (x, y + thumb_h + 10), thumb_w, fonts["small"], "#292621")
    sheet.save(output_path)


def write_review_index(result: dict[str, Any], output_root: Path) -> None:
    lines = [
        "# 角色风格矩阵人工审核表",
        "",
        f"- run_id：`{result['run_id']}`",
        f"- 总览拼图：`{rel(output_root / 'all_conditions_contact_sheet.png')}`",
        f"- 任务 JSON：`{rel(output_root / 'matrix_tasks.json')}`",
        "",
        "## 初步判断维度",
        "",
        "- 如果同一个 prompt profile 在不同 checkpoint 下年龄感差异很大，主要是模型默认审美问题。",
        "- 如果所有 checkpoint 在 `balanced_reference` 都偏低幼，但 `mature_shoujo` 改善明显，主要是提示词/角色设计 skill 问题。",
        "- 如果 `source_faithful` 更接近漫画但仍低幼，后续应引入参考图/IPAdapter/角色 LoRA，而不是只靠文生图。",
        "",
        "## 按模型分组",
        "",
    ]
    for checkpoint in result["checkpoints"]:
        label = short_checkpoint(checkpoint)
        lines.append(f"- `{label}`：`{rel(output_root / 'by_checkpoint' / (label + '.png'))}`")
    lines.extend(["", "## 按风格分组", ""])
    for profile in STYLE_PROFILES:
        lines.append(f"- `{profile.profile_id}` / {profile.label}：`{rel(output_root / 'by_profile' / (profile.profile_id + '.png'))}`")
    lines.extend(["", "## 单张结果审核", ""])
    lines.append("| 模型 | 风格 | 角色 | 图片 | 年龄感 | 还原度 | 可用性 | 备注 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for task in result["tasks"]:
        image = task["output_files"][0] if task["output_files"] else ""
        lines.append(
            "| "
            f"`{task['checkpoint_label']}` | `{task['profile_id']}` | {task['display_name']} | `{image}` |  |  |  |  |"
        )
    (output_root / "review_index.md").write_text("\n".join(lines), encoding="utf-8")


def available_checkpoints(object_info: dict[str, Any], requested: list[str]) -> list[CheckpointCase]:
    ckpt_values = object_info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
    available = set(ckpt_values)
    requested_names = requested or [case.ckpt_name for case in CHECKPOINT_CASES]
    cases = []
    for name in requested_names:
        if name in available:
            cases.append(CheckpointCase(name, short_checkpoint(name)))
    return cases


def validate_nodes(object_info: dict[str, Any]) -> None:
    missing = sorted(REQUIRED_NODES - set(object_info))
    if missing:
        raise RuntimeError("ComfyUI missing required nodes: " + ", ".join(missing))


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
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


def rel(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT))


def short_checkpoint(name: str) -> str:
    stem = Path(name).stem
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:4]
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in stem)[:52] + "_" + digest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a checkpoint/prompt-profile matrix for character design review")
    parser.add_argument("--prompt-pack", type=Path, default=DEFAULT_PROMPT_PACK)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--seed", type=int, default=2026051901)
    parser.add_argument("--checkpoints", nargs="*", default=[])
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-attempts", type=int, default=180)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
