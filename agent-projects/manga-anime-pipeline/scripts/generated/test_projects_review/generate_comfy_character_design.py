from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import urllib.request
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
DEFAULT_OPTIMIZED = REVIEW_DIR / "optimized_prompt_pack.json"
DEFAULT_FALLBACK = REVIEW_DIR / "video_prompt_pack.json"
DEFAULT_OUTPUT_DIR = REVIEW_DIR / "comfy_character_design"
COMFY_OUTPUT_ROOT = WORKSPACE_ROOT / "ComfyUI" / "output"
REQUIRED_NODES = {
    "CheckpointLoaderSimple",
    "CLIPTextEncode",
    "EmptyLatentImage",
    "KSampler",
    "VAEDecode",
    "SaveImage",
}
BASE_NEGATIVE = (
    "worst quality, low quality, lowres, blurry, jpeg artifacts, bad anatomy, bad hands, "
    "extra fingers, missing fingers, fused fingers, deformed face, cropped head, cropped body, "
    "text, letters, kanji, chinese characters, labels, callout boxes, watermark, logo, speech bubble, "
    "blank speech bubble, empty bubble, white oval, blank circle, floating icon, signature, duplicate body, "
    "multiple girls, two girls, group, split screen, identity drift"
)


def main() -> int:
    args = _parse_args()
    prompt_pack_path = args.prompt_pack if args.prompt_pack.exists() else DEFAULT_FALLBACK
    prompt_pack = read_json(prompt_pack_path)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    _validate_comfy(args.server, args.checkpoint)
    client = ComfyClient(ComfyClientConfig(server=args.server, timeout_seconds=args.timeout_seconds))
    client.check_server()

    run_id = hashlib.sha1(str(time.time()).encode("utf-8")).hexdigest()[:8]
    tasks = []
    for index, character in enumerate(prompt_pack.get("characters", [])):
        seed = args.seed + index * 101
        task = submit_character(
            client=client,
            character=character,
            checkpoint=args.checkpoint,
            width=args.width,
            height=args.height,
            steps=args.steps,
            cfg=args.cfg,
            seed=seed,
            run_id=run_id,
            output_dir=args.output_dir,
            poll_attempts=args.poll_attempts,
            poll_interval_seconds=args.poll_interval_seconds,
            prompt_source=str(prompt_pack_path.relative_to(PROJECT_ROOT)),
        )
        tasks.append(task)

    result = {
        "workflow_name": "character_design_sdxl",
        "server": args.server,
        "checkpoint": args.checkpoint,
        "prompt_pack": str(prompt_pack_path.relative_to(PROJECT_ROOT)),
        "output_dir": str(args.output_dir.relative_to(PROJECT_ROOT)),
        "tasks": tasks,
    }
    sheet_path = args.output_dir / "comfy_character_design_sheet.png"
    render_result_sheet(tasks, sheet_path)
    result["sheet_path"] = str(sheet_path.relative_to(PROJECT_ROOT))
    write_json(args.output_dir / "comfy_character_design_tasks.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def submit_character(
    *,
    client: ComfyClient,
    character: dict[str, Any],
    checkpoint: str,
    width: int,
    height: int,
    steps: int,
    cfg: float,
    seed: int,
    run_id: str,
    output_dir: Path,
    poll_attempts: int,
    poll_interval_seconds: float,
    prompt_source: str,
) -> dict[str, Any]:
    character_id = str(character.get("character_id") or "character")
    positive = build_character_prompt(character)
    negative = build_negative_prompt(character)
    prefix = f"manga_anime_pipeline/test_projects_short_manga/character_design/{character_id}_{run_id}"
    workflow = build_sdxl_workflow(
        checkpoint=checkpoint,
        positive=positive,
        negative=negative,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        seed=seed,
        filename_prefix=prefix,
    )
    client_id = f"agent:codex|workflow:character_design_sdxl|run:{run_id}"
    extra_data = {
        "agent": "codex",
        "workflow_name": "character_design_sdxl",
        "source": "manga-anime-pipeline",
        "character_id": character_id,
        "seed": seed,
        "notes": (
            f"checkpoint={checkpoint}; size={width}x{height}; steps={steps}; cfg={cfg}; "
            f"prompt_source={prompt_source}; generated for test_projects short manga role sheet"
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
    copied = copy_history_images(entry, output_dir, character_id)
    task_context = {
        "character_id": character_id,
        "display_name": character.get("display_name"),
        "seed": seed,
        "checkpoint": checkpoint,
        "size": [width, height],
        "steps": steps,
        "cfg": cfg,
        "positive_prompt": positive,
        "negative_prompt": negative,
    }
    provenance_files = write_output_provenance_files(
        copied,
        project_root=PROJECT_ROOT,
        workflow=workflow,
        workflow_name="character_design_sdxl",
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


def build_character_prompt(character: dict[str, Any]) -> str:
    traits = character.get("visual_traits") or {}
    character_id = str(character.get("character_id") or "")
    role_prompt = _role_specific_prompt(character_id)
    descriptors = [
        "masterpiece, best quality, anime style, polished key visual quality",
        "(solo:1.45), (single girl only:1.45), one full body character, centered composition",
        "clean character reference illustration, front view, standing pose, simple relaxed arms",
        "plain warm gray studio background, clean empty background, uncluttered composition",
        "crisp line art, delicate cel shading, soft studio lighting, detailed eyes, clean silhouette",
        "Japanese navy-and-white sailor school uniform, bow tie, pleated skirt, loafers",
        role_prompt,
        _traits_prompt(traits),
    ]
    return ", ".join(part for part in descriptors if part)


def build_negative_prompt(character: dict[str, Any]) -> str:
    parts = [
        BASE_NEGATIVE,
        _role_specific_negative(str(character.get("character_id") or "")),
        str(character.get("optimized_negative_prompt") or character.get("negative_prompt") or ""),
    ]
    clauses: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for clause in part.split(","):
            text = clause.strip()
            key = text.lower()
            if text and key not in seen:
                clauses.append(text)
                seen.add(key)
    return ", ".join(clauses)


def _role_specific_prompt(character_id: str) -> str:
    if character_id == "char_dark_ponytail":
        return (
            "tall slender high school girl, approximately 172cm impression, dark purple hair, "
            "high ponytail tied with a simple ribbon, long side locks, purple eyes, lively mischievous smile, "
            "confident playful posture"
        )
    if character_id == "char_silver_longhair":
        return (
            "petite high school girl, approximately 142cm impression, silver white long straight hair, "
            "black hairband, green eyes, gentle soft smile, cute calm posture"
        )
    return ""


def _role_specific_negative(character_id: str) -> str:
    if character_id == "char_dark_ponytail":
        return "silver hair, white hair, green eyes, second girl, extra character, pale-haired girl"
    if character_id == "char_silver_longhair":
        return "purple hair, high ponytail, purple eyes, second girl, extra character, dark-haired girl"
    return ""


def _traits_prompt(traits: dict[str, Any]) -> str:
    parts = [
        str(traits.get("hair_color") or ""),
        str(traits.get("hair_style") or ""),
        str(traits.get("eye_color") or ""),
        str(traits.get("outfit") or ""),
        str(traits.get("height") or ""),
    ]
    return ", ".join(part for part in parts if part)


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
        outputs = entry.get("outputs") or {}
        if outputs:
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


def render_result_sheet(tasks: list[dict[str, Any]], output_path: Path) -> None:
    width = 1700
    card_h = 820
    margin = 44
    header_h = 96
    height = header_h + len(tasks) * (card_h + 28) + margin
    sheet = Image.new("RGB", (width, height), "#f6f5f1")
    draw = ImageDraw.Draw(sheet)
    fonts = _fonts()
    draw.text((margin, 26), "ComfyUI 角色设定图重绘结果", font=fonts["title"], fill="#191816")
    draw.text((margin, 66), "SDXL 文生图输出；提示词已随任务 JSON 保留，便于继续调参。", font=fonts["small"], fill="#5a554d")
    y = header_h
    for task in tasks:
        draw.rounded_rectangle((margin, y, width - margin, y + card_h), radius=14, fill="#ffffff", outline="#d5d1c8", width=2)
        image_path = _first_existing(task.get("output_files", []))
        if image_path:
            with Image.open(image_path) as generated:
                generated = generated.convert("RGB")
                generated.thumbnail((520, 740), Image.Resampling.LANCZOS)
                frame = Image.new("RGB", (560, 760), "#ebe8df")
                frame.paste(generated, ((frame.width - generated.width) // 2, (frame.height - generated.height) // 2))
                sheet.paste(frame, (margin + 24, y + 30))
        text_x = margin + 620
        draw.text((text_x, y + 34), f"{task.get('display_name')} / {task.get('character_id')}", font=fonts["heading"], fill="#1e1c19")
        draw.text((text_x, y + 76), f"seed={task.get('seed')}  prompt_id={task.get('prompt_id')}", font=fonts["small"], fill="#61584f")
        draw.text((text_x, y + 126), "正向提示词", font=fonts["label"], fill="#4d4038")
        _draw_wrapped(draw, str(task.get("positive_prompt") or ""), (text_x, y + 164), 980, fonts["body"], "#292621", 7)
        draw.text((text_x, y + 560), "负向提示词", font=fonts["label"], fill="#4d4038")
        _draw_wrapped(draw, str(task.get("negative_prompt") or ""), (text_x, y + 598), 980, fonts["small"], "#292621", 6)
        y += card_h + 28
    sheet.save(output_path)


def _validate_comfy(server: str, checkpoint: str) -> None:
    object_info = _get_json(server.rstrip("/") + "/object_info")
    missing = sorted(REQUIRED_NODES - set(object_info))
    if missing:
        raise RuntimeError("ComfyUI missing required nodes: " + ", ".join(missing))
    ckpt_info = object_info.get("CheckpointLoaderSimple", {})
    ckpt_values = ckpt_info.get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
    if checkpoint not in ckpt_values:
        raise RuntimeError(f"Checkpoint not available in ComfyUI: {checkpoint}")


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _first_existing(paths: list[str]) -> Path | None:
    for rel_path in paths:
        path = PROJECT_ROOT / rel_path
        if path.exists():
            return path
    return None


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    max_width: int,
    font: ImageFont.ImageFont,
    fill: str,
    line_gap: int,
) -> None:
    x, y = xy
    for paragraph in str(text or "").splitlines() or [""]:
        line = ""
        for char in paragraph:
            candidate = line + char
            if draw.textlength(candidate, font=font) <= max_width or not line:
                line = candidate
            else:
                draw.text((x, y), line, font=font, fill=fill)
                y += font.size + line_gap
                line = char
        if line:
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + line_gap


def _fonts() -> dict[str, ImageFont.FreeTypeFont]:
    font_path = _font_path()
    return {
        "title": ImageFont.truetype(font_path, 31),
        "heading": ImageFont.truetype(font_path, 25),
        "label": ImageFont.truetype(font_path, 21),
        "body": ImageFont.truetype(font_path, 19),
        "small": ImageFont.truetype(font_path, 17),
    }


def _font_path() -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    raise FileNotFoundError("No Chinese-capable Windows font found")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ComfyUI-redrawn character design images")
    parser.add_argument("--prompt-pack", type=Path, default=DEFAULT_OPTIMIZED)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--checkpoint", default="waiIllustriousSDXL_v170.safetensors")
    parser.add_argument("--width", type=int, default=832)
    parser.add_argument("--height", type=int, default=1216)
    parser.add_argument("--steps", type=int, default=24)
    parser.add_argument("--cfg", type=float, default=6.5)
    parser.add_argument("--seed", type=int, default=2026051501)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-attempts", type=int, default=180)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
