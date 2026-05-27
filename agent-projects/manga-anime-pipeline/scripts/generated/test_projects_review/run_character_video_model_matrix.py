from __future__ import annotations

import argparse
import json
import shutil
import subprocess
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

from pipeline.comfy.client import ComfyClient, ComfyClientConfig
from pipeline.comfy.provenance import write_output_provenance_files
from pipeline.common.io import write_json


RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "2026-05-15_test_projects_short_manga"
REVIEW_DIR = RUNTIME_ROOT / "review"
DEFAULT_INPUT_DIR = REVIEW_DIR / "comfy_character_design"
DEFAULT_OUTPUT_ROOT = REVIEW_DIR / "video_model_matrix"
COMFY_INPUT_ROOT = WORKSPACE_ROOT / "ComfyUI" / "input"
COMFY_OUTPUT_ROOT = WORKSPACE_ROOT / "ComfyUI" / "output"

CHARACTER_IMAGES = {
    "char_dark_ponytail": "char_dark_ponytail_01.png",
    "char_silver_longhair": "char_silver_longhair_01.png",
}


@dataclass(frozen=True)
class VideoModelCase:
    model_id: str
    label: str
    builder: str
    width: int
    height: int
    length: int
    fps: float
    steps: int
    cfg: float
    high_unet: str = ""
    low_unet: str = ""
    unet: str = ""
    high_lora: str = ""
    low_lora: str = ""
    lora: str = ""
    shift: float = 5.0
    scheduler: str = "simple"
    sampler_name: str = "euler"
    notes: str = ""


VIDEO_MODELS = [
    VideoModelCase(
        model_id="wan22_i2v_lightx2v",
        label="Wan 2.2 I2V Lightx2v 官方双模型",
        builder="wan22_dual",
        width=512,
        height=768,
        length=25,
        fps=16.0,
        steps=4,
        cfg=1.0,
        high_unet="wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
        low_unet="wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
        high_lora="wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
        low_lora="wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
        notes="快速基准，适合看轻动作和身份保持。",
    ),
    VideoModelCase(
        model_id="wan21_i2v_480p",
        label="Wan 2.1 I2V 14B 480P",
        builder="wan_single",
        width=512,
        height=768,
        length=25,
        fps=16.0,
        steps=8,
        cfg=4.0,
        unet="Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors",
        shift=5.0,
        notes="较传统的 Wan 2.1 图生视频基线。",
    ),
    VideoModelCase(
        model_id="wan22_i2v_dasiwa_lightspeed",
        label="Wan 2.2 I2V Dasiwa Lightspeed High + Base Low",
        builder="wan22_dual",
        width=512,
        height=768,
        length=25,
        fps=16.0,
        steps=4,
        cfg=1.0,
        high_unet="DasiwaWAN22I2V14BLightspeed_boundbiteHighV10.safetensors",
        low_unet="wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
        shift=5.0,
        notes="本地 Wan 2.2 派生高噪模型，不挂成人向 LoRA，只用安全负面词约束。",
    ),
]


def main() -> int:
    args = parse_args()
    object_info = get_json(args.server.rstrip("/") + "/object_info")
    validate_required_nodes(object_info)
    requested = set(args.models or [case.model_id for case in VIDEO_MODELS])
    model_cases = [case for case in VIDEO_MODELS if case.model_id in requested]
    validate_models_available(object_info, model_cases)

    run_id = args.run_id or time.strftime("%Y%m%d_%H%M%S")
    output_root = args.output_root / run_id
    output_root.mkdir(parents=True, exist_ok=True)

    input_assets = prepare_input_assets(args.input_dir, run_id)
    client = ComfyClient(ComfyClientConfig(server=args.server, timeout_seconds=args.timeout_seconds))
    client.check_server()

    tasks: list[dict[str, Any]] = []
    for model_index, model_case in enumerate(model_cases):
        for character_index, (character_id, image_name) in enumerate(CHARACTER_IMAGES.items()):
            seed = args.seed + model_index * 1000 + character_index * 101
            task = run_one_case(
                client=client,
                model_case=model_case,
                character_id=character_id,
                input_image=input_assets[image_name],
                run_id=run_id,
                seed=seed,
                output_root=output_root,
                poll_attempts=args.poll_attempts,
                poll_interval_seconds=args.poll_interval_seconds,
            )
            tasks.append(task)
            write_json(output_root / "video_matrix_tasks.partial.json", build_result(args, run_id, output_root, tasks))

    result = build_result(args, run_id, output_root, tasks)
    review_sheet = write_video_review_sheet(result, output_root)
    write_review_index(result, output_root, review_sheet)
    write_json(output_root / "video_matrix_tasks.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_one_case(
    *,
    client: ComfyClient,
    model_case: VideoModelCase,
    character_id: str,
    input_image: str,
    run_id: str,
    seed: int,
    output_root: Path,
    poll_attempts: int,
    poll_interval_seconds: float,
) -> dict[str, Any]:
    prompt = build_prompt(character_id)
    negative = build_negative_prompt(character_id)
    prefix = f"manga_anime_pipeline/test_projects_short_manga/video_model_matrix/{run_id}/{model_case.model_id}/{character_id}"
    if model_case.builder == "wan22_dual":
        workflow = build_wan22_dual_workflow(model_case, input_image, prompt, negative, seed, prefix)
    elif model_case.builder == "wan_single":
        workflow = build_wan_single_workflow(model_case, input_image, prompt, negative, seed, prefix)
    else:
        raise ValueError(f"Unsupported builder: {model_case.builder}")

    client_id = f"agent:codex|workflow:character_video_model_matrix|run:{run_id}"
    extra_data = {
        "agent": "codex",
        "workflow_name": "character_video_model_matrix",
        "source": "manga-anime-pipeline",
        "character_id": character_id,
        "model_id": model_case.model_id,
        "seed": seed,
        "notes": (
            f"model={model_case.label}; input_image={input_image}; size={model_case.width}x{model_case.height}; "
            f"length={model_case.length}; fps={model_case.fps}; steps={model_case.steps}; cfg={model_case.cfg}; "
            f"{model_case.notes}"
        ),
    }
    payload = {
        "prompt": workflow,
        "client_id": client_id,
        "extra_data": extra_data,
    }
    task = {
        "model_id": model_case.model_id,
        "model_label": model_case.label,
        "builder": model_case.builder,
        "character_id": character_id,
        "input_image": input_image,
        "seed": seed,
        "size": [model_case.width, model_case.height],
        "length": model_case.length,
        "fps": model_case.fps,
        "steps": model_case.steps,
        "cfg": model_case.cfg,
        "positive_prompt": prompt,
        "negative_prompt": negative,
        "status": "pending",
        "prompt_id": "",
        "output_files": [],
        "provenance_files": [],
        "error_message": "",
    }
    try:
        response = client.submit_prompt(payload)
        prompt_id = str(response.get("prompt_id") or "")
        task["prompt_id"] = prompt_id
        if not prompt_id:
            raise RuntimeError(f"ComfyUI submit response missing prompt_id: {response}")
        entry = wait_for_history(client, prompt_id, poll_attempts, poll_interval_seconds)
        copied = copy_history_outputs(entry, output_root / "by_model" / model_case.model_id, character_id)
        task["output_files"] = [str(path.relative_to(PROJECT_ROOT)) for path in copied]
        provenance_files = write_output_provenance_files(
            copied,
            project_root=PROJECT_ROOT,
            workflow=workflow,
            workflow_name="character_video_model_matrix",
            prompt_id=prompt_id,
            client_id=client_id,
            extra_data=extra_data,
            task_context={key: value for key, value in task.items() if key not in {"output_files", "provenance_files"}},
            history_status=entry.get("status") if isinstance(entry.get("status"), dict) else {},
        )
        task["provenance_files"] = [str(path.relative_to(PROJECT_ROOT)) for path in provenance_files]
        task["status"] = "finished" if copied else "finished_without_outputs"
    except Exception as error:
        task["status"] = "failed"
        task["error_message"] = str(error)
    return task


def build_wan22_dual_workflow(
    case: VideoModelCase,
    input_image: str,
    positive: str,
    negative: str,
    seed: int,
    filename_prefix: str,
) -> dict[str, Any]:
    half_step = max(1, case.steps // 2)
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": input_image}, "_meta": {"title": "Start Image"}},
        "84": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "90": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "95": {"class_type": "UNETLoader", "inputs": {"unet_name": case.high_unet, "weight_dtype": "default"}},
        "96": {"class_type": "UNETLoader", "inputs": {"unet_name": case.low_unet, "weight_dtype": "default"}},
        "89": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": negative}, "_meta": {"title": "Negative Prompt"}},
        "93": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": positive}, "_meta": {"title": "Positive Prompt"}},
        "98": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["93", 0],
                "negative": ["89", 0],
                "vae": ["90", 0],
                "start_image": ["1", 0],
                "width": case.width,
                "height": case.height,
                "length": case.length,
                "batch_size": 1,
            },
        },
        "86": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["104", 0],
                "positive": ["98", 0],
                "negative": ["98", 1],
                "latent_image": ["98", 2],
                "add_noise": "enable",
                "noise_seed": seed,
                "steps": case.steps,
                "cfg": case.cfg,
                "sampler_name": case.sampler_name,
                "scheduler": case.scheduler,
                "start_at_step": 0,
                "end_at_step": half_step,
                "return_with_leftover_noise": "enable",
            },
        },
        "85": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["103", 0],
                "positive": ["98", 0],
                "negative": ["98", 1],
                "latent_image": ["86", 0],
                "add_noise": "disable",
                "noise_seed": seed,
                "steps": case.steps,
                "cfg": case.cfg,
                "sampler_name": case.sampler_name,
                "scheduler": case.scheduler,
                "start_at_step": half_step,
                "end_at_step": case.steps,
                "return_with_leftover_noise": "disable",
            },
        },
        "87": {"class_type": "VAEDecode", "inputs": {"samples": ["85", 0], "vae": ["90", 0]}},
        "117": {"class_type": "CreateVideo", "inputs": {"images": ["87", 0], "fps": case.fps}},
        "118": {"class_type": "SaveVideo", "inputs": {"video": ["117", 0], "filename_prefix": filename_prefix, "format": "mp4", "codec": "h264"}},
    }
    high_model_ref = ["95", 0]
    low_model_ref = ["96", 0]
    if case.high_lora:
        workflow["101"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"model": high_model_ref, "lora_name": case.high_lora, "strength_model": 1.0},
        }
        high_model_ref = ["101", 0]
    if case.low_lora:
        workflow["102"] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {"model": low_model_ref, "lora_name": case.low_lora, "strength_model": 1.0},
        }
        low_model_ref = ["102", 0]
    workflow["103"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": low_model_ref, "shift": case.shift}}
    workflow["104"] = {"class_type": "ModelSamplingSD3", "inputs": {"model": high_model_ref, "shift": case.shift}}
    return workflow


def build_wan_single_workflow(
    case: VideoModelCase,
    input_image: str,
    positive: str,
    negative: str,
    seed: int,
    filename_prefix: str,
) -> dict[str, Any]:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": input_image}, "_meta": {"title": "Start Image"}},
        "84": {"class_type": "CLIPLoader", "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}},
        "90": {"class_type": "VAELoader", "inputs": {"vae_name": "wan_2.1_vae.safetensors"}},
        "95": {"class_type": "UNETLoader", "inputs": {"unet_name": case.unet, "weight_dtype": "default"}},
        "103": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["95", 0], "shift": case.shift}},
        "89": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": negative}, "_meta": {"title": "Negative Prompt"}},
        "93": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["84", 0], "text": positive}, "_meta": {"title": "Positive Prompt"}},
        "98": {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["93", 0],
                "negative": ["89", 0],
                "vae": ["90", 0],
                "start_image": ["1", 0],
                "width": case.width,
                "height": case.height,
                "length": case.length,
                "batch_size": 1,
            },
        },
        "85": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["103", 0],
                "positive": ["98", 0],
                "negative": ["98", 1],
                "latent_image": ["98", 2],
                "add_noise": "enable",
                "noise_seed": seed,
                "steps": case.steps,
                "cfg": case.cfg,
                "sampler_name": case.sampler_name,
                "scheduler": case.scheduler,
                "start_at_step": 0,
                "end_at_step": case.steps,
                "return_with_leftover_noise": "disable",
            },
        },
        "87": {"class_type": "VAEDecode", "inputs": {"samples": ["85", 0], "vae": ["90", 0]}},
        "117": {"class_type": "CreateVideo", "inputs": {"images": ["87", 0], "fps": case.fps}},
        "118": {"class_type": "SaveVideo", "inputs": {"video": ["117", 0], "filename_prefix": filename_prefix, "format": "mp4", "codec": "h264"}},
    }


def build_prompt(character_id: str) -> str:
    base = (
        "safe for work anime image-to-video, preserve the exact character identity from the reference image, "
        "subtle breathing, one natural blink, very small head tilt, gentle hair sway, slight clothing sway, "
        "slow calm camera push-in, stable face, stable hands, stable school uniform, no scene cut, no new character"
    )
    if character_id == "char_dark_ponytail":
        return base + ", tall dark purple high ponytail girl, purple eyes, lively but restrained expression"
    if character_id == "char_silver_longhair":
        return base + ", petite silver white long hair girl with black hairband, green eyes, gentle soft smile"
    return base


def build_negative_prompt(character_id: str) -> str:
    negative = (
        "NSFW, nudity, explicit sexual content, erotic, revealing clothes, underwear, swimsuit, "
        "childlike proportions, chibi, toddler face, low age impression, big baby eyes, "
        "identity drift, face melting, hand distortion, extra fingers, missing fingers, extra limbs, "
        "changed hairstyle, changed eye color, wrong school uniform, new character, duplicate body, "
        "fast action, large mouth movement, dancing, jumping, camera shake, subtitles, watermark, text, logo, blurry details"
    )
    if character_id == "char_dark_ponytail":
        return negative + ", silver hair, white hair, green eyes"
    if character_id == "char_silver_longhair":
        return negative + ", purple hair, high ponytail, purple eyes"
    return negative


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
            raise RuntimeError(f"ComfyUI history failed for {prompt_id}: {status_info}")
        if entry.get("outputs"):
            return entry
    raise TimeoutError(f"ComfyUI history did not finish for {prompt_id}")


def copy_history_outputs(entry: dict[str, Any], output_dir: Path, character_id: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for node_output in (entry.get("outputs") or {}).values():
        for media_key in ("videos", "images", "gifs"):
            for item in node_output.get(media_key, []) or []:
                filename = str(item.get("filename") or "")
                if not filename:
                    continue
                subfolder = str(item.get("subfolder") or "")
                source = COMFY_OUTPUT_ROOT / subfolder / filename
                if not source.exists():
                    continue
                target = output_dir / f"{character_id}_{len(copied) + 1:02d}{source.suffix}"
                shutil.copy2(source, target)
                copied.append(target)
    return copied


def prepare_input_assets(input_dir: Path, run_id: str) -> dict[str, str]:
    target_dir = COMFY_INPUT_ROOT / "manga_anime_pipeline" / "test_projects_short_manga" / "video_model_matrix" / run_id
    target_dir.mkdir(parents=True, exist_ok=True)
    assets: dict[str, str] = {}
    for image_name in CHARACTER_IMAGES.values():
        source = input_dir / image_name
        if not source.exists():
            raise FileNotFoundError(f"Missing character design image: {source}")
        target = target_dir / image_name
        shutil.copy2(source, target)
        assets[image_name] = str(target.relative_to(COMFY_INPUT_ROOT)).replace("\\", "/")
    return assets


def validate_required_nodes(object_info: dict[str, Any]) -> None:
    required = {
        "LoadImage",
        "CLIPLoader",
        "CLIPTextEncode",
        "VAELoader",
        "UNETLoader",
        "ModelSamplingSD3",
        "WanImageToVideo",
        "KSamplerAdvanced",
        "VAEDecode",
        "CreateVideo",
        "SaveVideo",
    }
    missing = sorted(required - set(object_info))
    if missing:
        raise RuntimeError("ComfyUI missing required nodes: " + ", ".join(missing))


def validate_models_available(object_info: dict[str, Any], model_cases: list[VideoModelCase]) -> None:
    unets = set(object_info["UNETLoader"]["input"]["required"]["unet_name"][0])
    loras = set(object_info["LoraLoaderModelOnly"]["input"]["required"]["lora_name"][0])
    missing: list[str] = []
    for case in model_cases:
        for name in [case.high_unet, case.low_unet, case.unet]:
            if name and name not in unets:
                missing.append(f"UNET:{name}")
        for name in [case.high_lora, case.low_lora, case.lora]:
            if name and name not in loras:
                missing.append(f"LoRA:{name}")
    if missing:
        raise RuntimeError("Missing required model files in ComfyUI object_info: " + ", ".join(missing))


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def build_result(args: argparse.Namespace, run_id: str, output_root: Path, tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "workflow_name": "character_video_model_matrix",
        "run_id": run_id,
        "server": args.server,
        "input_dir": str(args.input_dir.relative_to(PROJECT_ROOT)),
        "output_root": str(output_root.relative_to(PROJECT_ROOT)),
        "models": [case.model_id for case in VIDEO_MODELS if not args.models or case.model_id in set(args.models)],
        "tasks": tasks,
    }


def write_review_index(result: dict[str, Any], output_root: Path, review_sheet: str = "") -> None:
    lines = [
        "# 角色图生视频模型横评",
        "",
        f"- run_id：`{result['run_id']}`",
        f"- 任务 JSON：`{result['output_root']}\\video_matrix_tasks.json`",
        "",
        "## 输出目录",
        "",
    ]
    if review_sheet:
        lines.append(f"- 首中尾帧审核图：`{review_sheet}`")
    for model_id in result["models"]:
        lines.append(f"- `{model_id}`：`{result['output_root']}\\by_model\\{model_id}`")
    lines.extend(["", "## 人工审核表", ""])
    lines.append("| 模型 | 角色 | 视频 | 状态 | 身份保持 | 动作自然度 | 问题备注 |")
    lines.append("|---|---|---|---|---|---|---|")
    for task in result["tasks"]:
        video = task["output_files"][0] if task["output_files"] else ""
        lines.append(
            f"| `{task['model_id']}` | `{task['character_id']}` | `{video}` | `{task['status']}` |  |  | {task.get('error_message', '')} |"
        )
    (output_root / "review_index.md").write_text("\n".join(lines), encoding="utf-8")


def write_video_review_sheet(result: dict[str, Any], output_root: Path) -> str:
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return ""

    frame_root = output_root / "review_frames"
    frame_root.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, list[Path]]] = []
    for task in result["tasks"]:
        if not task.get("output_files"):
            continue
        video_path = PROJECT_ROOT / task["output_files"][0]
        if not video_path.exists():
            continue
        frame_paths = extract_review_frames(video_path, frame_root, task["model_id"], task["character_id"])
        if frame_paths:
            label = f"{task['model_id']} / {task['character_id']}"
            rows.append((label, frame_paths))
    if not rows:
        return ""

    label_width = 330
    thumb_width = 160
    thumb_height = 240
    padding = 18
    gap = 10
    header_height = 40
    row_height = thumb_height + padding
    sheet_width = label_width + padding * 2 + thumb_width * 3 + gap * 2
    sheet_height = header_height + row_height * len(rows) + padding
    sheet = Image.new("RGB", (sheet_width, sheet_height), (248, 248, 246))
    draw = ImageDraw.Draw(sheet)
    draw.text((padding, 12), "video review frames: start / middle / end", fill=(32, 32, 32))
    for row_index, (label, frame_paths) in enumerate(rows):
        top = header_height + row_index * row_height
        draw.text((padding, top + 8), label, fill=(20, 20, 20))
        for frame_index, frame_path in enumerate(frame_paths[:3]):
            with Image.open(frame_path) as frame:
                frame = frame.convert("RGB")
                frame.thumbnail((thumb_width, thumb_height))
                x = label_width + frame_index * (thumb_width + gap)
                y = top + (thumb_height - frame.height) // 2
                sheet.paste(frame, (x, y))
                draw.rectangle((x, y, x + frame.width - 1, y + frame.height - 1), outline=(180, 180, 176))

    sheet_path = output_root / "video_review_contact_sheet.jpg"
    sheet.save(sheet_path, quality=92)
    return str(sheet_path.relative_to(PROJECT_ROOT))


def extract_review_frames(video_path: Path, frame_root: Path, model_id: str, character_id: str) -> list[Path]:
    frame_paths: list[Path] = []
    for label, frame_number in [("start", 0), ("middle", 12), ("end", 24)]:
        target = frame_root / f"{model_id}_{character_id}_{label}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"select=eq(n\\,{frame_number}),scale=512:768",
            "-frames:v",
            "1",
            str(target),
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        except Exception:
            continue
        if target.exists():
            frame_paths.append(target)
    return frame_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run several local video models with the character design images")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--models", nargs="*", default=[])
    parser.add_argument("--seed", type=int, default=2026052101)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--poll-attempts", type=int, default=300)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
