from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from comfyui_skill_utils import (
    extract_models_from_workflow_file,
    get_pack_models,
    get_skill,
    has_negative_hint,
    load_registry,
    model_file_path,
    relative_to_root,
    workspace_path,
)


SERVER_URL = "http://127.0.0.1:8188"
DEFAULT_ANALYSIS_MODEL = "gemini-2.5-pro"
DEFAULT_IMAGE_CAPTION_PROMPT = "请详细描述这张图片，突出主体、风格、构图、光线和可复用的提示词线索。"
DEFAULT_VIDEO_CAPTION_PROMPT = "请详细描述这段视频，突出镜头语言、主体动作、场景变化、光线和节奏。"
DEFAULT_PROMPT_ENHANCE_SYSTEM_PROMPT = (
    "你是一个用于图像和视频生成的提示词优化器。"
    "在保留用户核心意图的前提下，把原始提示词扩写为更具体、更清晰、更利于生成模型理解的版本。"
    "只输出优化后的提示词正文，不要解释。"
)
DEFAULT_NEGATIVE = (
    "Bright tones, overexposed, static, blurred details, subtitles, style, works, paintings, "
    "images, still, overall gray, worst quality, low quality, JPEG artifacts, ugly, incomplete, "
    "extra fingers, poorly drawn hands, poorly drawn faces, deformed, disfigured, misshapen limbs, "
    "fused fingers, still picture, messy background, three legs, crowded background, walking backwards, nudity, NSFW"
)
POLL_SECONDS = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ComfyUI video workflows")
    parser.add_argument("--registry", default=None, help="Path to agent-skills/comfyui/registry.json")
    parser.add_argument("--server", default=SERVER_URL, help="ComfyUI server URL")
    parser.add_argument("--skill", default="wan22_t2v_fast", help="Named skill from the registry")
    parser.add_argument("--workflow-api", default=None, help="Run a specific API workflow JSON path")
    parser.add_argument("--list-skills", action="store_true", help="List registry skills and exit")
    parser.add_argument("--prompt", default="", help="Positive prompt override")
    parser.add_argument("--negative", default=DEFAULT_NEGATIVE, help="Negative prompt override")
    parser.add_argument("--image", default=None, help="Reference image to upload and inject into the workflow")
    parser.add_argument("--video", default=None, help="Reference video file for built-in or API workflows")
    parser.add_argument("--video2", default=None, help="Second reference video file for stitching-style workflows")
    parser.add_argument("--width", type=int, default=832, help="Target width for built-in workflows")
    parser.add_argument("--height", type=int, default=480, help="Target height for built-in workflows")
    parser.add_argument("--length", type=int, default=81, help="Frame count for built-in workflows")
    parser.add_argument("--fps", type=float, default=16.0, help="Output FPS for built-in workflows")
    parser.add_argument("--seed", type=int, default=None, help="Optional fixed seed")
    parser.add_argument("--model-name", default="RealESRGAN_x4plus.safetensors", help="Model override for skills that expose a model selector")
    parser.add_argument("--analysis-model", default=DEFAULT_ANALYSIS_MODEL, help="Model name for Gemini-backed analysis skills")
    parser.add_argument("--system-prompt", default="", help="Optional system prompt override for Gemini-backed skills")
    parser.add_argument("--direction", default="right", choices=["right", "down", "left", "up"], help="Stitch direction for stitching skills")
    parser.add_argument("--match-image-size", action="store_true", default=True, help="Resize secondary input when stitching images or videos")
    parser.add_argument("--no-match-image-size", dest="match_image_size", action="store_false", help="Do not resize secondary input when stitching images or videos")
    parser.add_argument("--spacing-width", type=int, default=0, help="Spacing width for stitch-style workflows")
    parser.add_argument("--spacing-color", default="white", choices=["white", "black", "red", "green", "blue"], help="Spacing color for stitch-style workflows")
    parser.add_argument("--video-start-time", type=float, default=0.0, help="Start time in seconds for video post-processing skills")
    parser.add_argument("--video-duration", type=float, default=2.0, help="Duration in seconds for video post-processing skills; use 0 for the full clip")
    parser.add_argument("--timeout", type=int, default=1800, help="Overall timeout in seconds")
    parser.add_argument("--output-root", default=None, help="Override output directory")
    parser.add_argument("--model-root", default=None, help="Override model root for preflight checks")
    parser.add_argument("--save-workflow", default=None, help="Write the final API workflow to this path before execution")
    parser.add_argument("--check-models", action="store_true", help="Only check model availability")
    return parser.parse_args()


def api_url(server: str, endpoint: str) -> str:
    return f"{server.rstrip('/')}{endpoint}"


def api_json(server: str, endpoint: str, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    response = requests.request(method, api_url(server, endpoint), json=payload, timeout=60)
    response.raise_for_status()
    if not response.content:
        return {}
    return response.json()


def check_server(server: str) -> dict[str, Any]:
    stats = api_json(server, "/system_stats")
    device = (stats.get("devices") or [{}])[0]
    print(f"ComfyUI: {stats.get('system', {}).get('comfyui_version', 'unknown')}")
    print(f"GPU: {device.get('name', 'unknown')}")
    if device.get("vram_total"):
        free_gb = device["vram_free"] / 1024 ** 3
        total_gb = device["vram_total"] / 1024 ** 3
        print(f"VRAM: {free_gb:.2f} / {total_gb:.2f} GB free")
    return stats


def normalize_length(length: int) -> int:
    return ((length - 1) // 4) * 4 + 1 if (length - 1) % 4 else length


def build_wan22_t2v_workflow(args: argparse.Namespace) -> dict[str, Any]:
    seed = args.seed if args.seed is not None else random.randint(0, 2**32 - 1)
    width = (args.width // 16) * 16
    height = (args.height // 16) * 16
    length = normalize_length(args.length)
    workflow = {
        "71": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "type": "wan"
            }
        },
        "73": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "wan_2.1_vae.safetensors"
            }
        },
        "75": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default"
            }
        },
        "76": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors",
                "weight_dtype": "default"
            }
        },
        "83": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["75", 0],
                "lora_name": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors",
                "strength_model": 1.0
            }
        },
        "85": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["76", 0],
                "lora_name": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors",
                "strength_model": 1.0
            }
        },
        "82": {
            "class_type": "ModelSamplingSD3",
            "inputs": {
                "model": ["83", 0],
                "shift": 5.0
            }
        },
        "86": {
            "class_type": "ModelSamplingSD3",
            "inputs": {
                "model": ["85", 0],
                "shift": 5.0
            }
        },
        "72": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["71", 0],
                "text": args.negative
            }
        },
        "89": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["71", 0],
                "text": args.prompt
            }
        },
        "74": {
            "class_type": "EmptyHunyuanLatentVideo",
            "inputs": {
                "width": width,
                "height": height,
                "length": length,
                "batch_size": 1
            }
        },
        "81": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["82", 0],
                "add_noise": "enable",
                "noise_seed": seed,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": ["89", 0],
                "negative": ["72", 0],
                "latent_image": ["74", 0],
                "start_at_step": 0,
                "end_at_step": 2,
                "return_with_leftover_noise": "enable"
            }
        },
        "78": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["86", 0],
                "add_noise": "disable",
                "noise_seed": seed,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": ["89", 0],
                "negative": ["72", 0],
                "latent_image": ["81", 0],
                "start_at_step": 2,
                "end_at_step": 4,
                "return_with_leftover_noise": "disable"
            }
        },
        "87": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["78", 0],
                "vae": ["73", 0]
            }
        },
        "114": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["87", 0],
                "fps": args.fps
            }
        },
        "115": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["114", 0],
                "filename_prefix": "wan22_t2v_fast/ComfyUI",
                "format": "mp4",
                "codec": "h264"
            }
        }
    }
    print(f"Built wan22_t2v_fast at {width}x{height}, {length} frames, fps={args.fps}, seed={seed}")
    return workflow


def stage_input_file(file_path: str | Path) -> str:
    resolved = workspace_path(file_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Input file does not exist: {resolved}")

    input_dir = workspace_path("ComfyUI/input")
    input_dir.mkdir(parents=True, exist_ok=True)
    staged_name = f"{resolved.stem}_{uuid.uuid4().hex[:8]}{resolved.suffix}"
    shutil.copy2(resolved, input_dir / staged_name)
    return staged_name


def gemini_seed(args: argparse.Namespace) -> int:
    return args.seed if args.seed is not None else random.randint(0, 2**32 - 1)


def build_image_caption_workflow(args: argparse.Namespace) -> dict[str, Any]:
    if not args.image:
        raise RuntimeError("--image is required for image_caption_gemini_api")

    staged_image = stage_input_file(args.image)
    prompt_text = args.prompt or DEFAULT_IMAGE_CAPTION_PROMPT
    workflow = {
        "1": {
            "class_type": "LoadImage",
            "inputs": {
                "image": staged_image,
            },
        },
        "2": {
            "class_type": "GeminiNode",
            "inputs": {
                "prompt": prompt_text,
                "model": args.analysis_model,
                "seed": gemini_seed(args),
                "images": ["1", 0],
                "system_prompt": args.system_prompt,
            },
        },
        "3": {
            "class_type": "PreviewAny",
            "inputs": {
                "source": ["2", 0],
            },
        },
    }
    print(f"Built image_caption_gemini_api for {Path(args.image).name} using {args.analysis_model}")
    return workflow


def build_prompt_enhance_workflow(args: argparse.Namespace) -> dict[str, Any]:
    if not args.prompt:
        raise RuntimeError("--prompt is required for prompt_enhance_api")

    system_prompt = args.system_prompt or DEFAULT_PROMPT_ENHANCE_SYSTEM_PROMPT
    gemini_inputs: dict[str, Any] = {
        "prompt": args.prompt,
        "model": args.analysis_model,
        "seed": gemini_seed(args),
        "system_prompt": system_prompt,
    }

    workflow: dict[str, Any]
    if args.image:
        staged_image = stage_input_file(args.image)
        workflow = {
            "1": {
                "class_type": "LoadImage",
                "inputs": {
                    "image": staged_image,
                },
            },
            "2": {
                "class_type": "GeminiNode",
                "inputs": {
                    **gemini_inputs,
                    "images": ["1", 0],
                },
            },
            "3": {
                "class_type": "PreviewAny",
                "inputs": {
                    "source": ["2", 0],
                },
            },
        }
    else:
        workflow = {
            "1": {
                "class_type": "GeminiNode",
                "inputs": gemini_inputs,
            },
            "2": {
                "class_type": "PreviewAny",
                "inputs": {
                    "source": ["1", 0],
                },
            },
        }

    print(f"Built prompt_enhance_api using {args.analysis_model}")
    return workflow


def build_video_caption_workflow(args: argparse.Namespace) -> dict[str, Any]:
    if not args.video:
        raise RuntimeError("--video is required for video_caption_gemini_api")

    staged_video = stage_input_file(args.video)
    prompt_text = args.prompt or DEFAULT_VIDEO_CAPTION_PROMPT
    workflow: dict[str, Any] = {
        "1": {
            "class_type": "LoadVideo",
            "inputs": {
                "file": staged_video,
            },
        },
    }

    video_input = ["1", 0]
    next_node_id = "2"
    if args.video_start_time > 0.0 or args.video_duration > 0.0:
        workflow[next_node_id] = {
            "class_type": "Video Slice",
            "inputs": {
                "video": ["1", 0],
                "start_time": args.video_start_time,
                "duration": args.video_duration,
                "strict_duration": False,
            },
        }
        video_input = [next_node_id, 0]
        next_node_id = "3"

    workflow[next_node_id] = {
        "class_type": "GeminiNode",
        "inputs": {
            "prompt": prompt_text,
            "model": args.analysis_model,
            "seed": gemini_seed(args),
            "video": video_input,
            "system_prompt": args.system_prompt,
        },
    }
    preview_node_id = str(int(next_node_id) + 1)
    workflow[preview_node_id] = {
        "class_type": "PreviewAny",
        "inputs": {
            "source": [next_node_id, 0],
        },
    }
    print(
        f"Built video_caption_gemini_api for {Path(args.video).name} using {args.analysis_model}, "
        f"start={args.video_start_time}s, duration={args.video_duration}s"
    )
    return workflow


def build_video_upscale_workflow(args: argparse.Namespace) -> dict[str, Any]:
    if not args.video:
        raise RuntimeError("--video is required for video_upscale_gan_api")

    staged_video = stage_input_file(args.video)
    workflow = {
        "1": {
            "class_type": "LoadVideo",
            "inputs": {
                "file": staged_video,
            },
        },
        "2": {
            "class_type": "Video Slice",
            "inputs": {
                "video": ["1", 0],
                "start_time": args.video_start_time,
                "duration": args.video_duration,
                "strict_duration": False,
            },
        },
        "3": {
            "class_type": "UpscaleModelLoader",
            "inputs": {
                "model_name": args.model_name,
            },
        },
        "4": {
            "class_type": "GetVideoComponents",
            "inputs": {
                "video": ["2", 0],
            },
        },
        "5": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": ["3", 0],
                "image": ["4", 0],
            },
        },
        "6": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["5", 0],
                "fps": ["4", 2],
                "audio": ["4", 1],
            },
        },
        "7": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["6", 0],
                "filename_prefix": "video_upscale_gan/ComfyUI",
                "format": "mp4",
                "codec": "h264",
            },
        },
    }
    print(
        f"Built video_upscale_gan_api for {Path(args.video).name} using {args.model_name}, "
        f"start={args.video_start_time}s, duration={args.video_duration}s"
    )
    return workflow


def build_video_stitch_workflow(args: argparse.Namespace) -> dict[str, Any]:
    if not args.video or not args.video2:
        raise RuntimeError("--video and --video2 are required for video_stitch_api")

    staged_video_1 = stage_input_file(args.video)
    staged_video_2 = stage_input_file(args.video2)
    workflow = {
        "1": {
            "class_type": "LoadVideo",
            "inputs": {
                "file": staged_video_1,
            },
        },
        "2": {
            "class_type": "LoadVideo",
            "inputs": {
                "file": staged_video_2,
            },
        },
        "3": {
            "class_type": "Video Slice",
            "inputs": {
                "video": ["1", 0],
                "start_time": args.video_start_time,
                "duration": args.video_duration,
                "strict_duration": False,
            },
        },
        "4": {
            "class_type": "Video Slice",
            "inputs": {
                "video": ["2", 0],
                "start_time": args.video_start_time,
                "duration": args.video_duration,
                "strict_duration": False,
            },
        },
        "5": {
            "class_type": "GetVideoComponents",
            "inputs": {
                "video": ["3", 0],
            },
        },
        "6": {
            "class_type": "GetVideoComponents",
            "inputs": {
                "video": ["4", 0],
            },
        },
        "7": {
            "class_type": "ImageStitch",
            "inputs": {
                "image1": ["5", 0],
                "image2": ["6", 0],
                "direction": args.direction,
                "match_image_size": args.match_image_size,
                "spacing_width": args.spacing_width,
                "spacing_color": args.spacing_color,
            },
        },
        "8": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["7", 0],
                "fps": ["5", 2],
                "audio": ["5", 1],
            },
        },
        "9": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["8", 0],
                "filename_prefix": "video_stitch/ComfyUI",
                "format": "mp4",
                "codec": "h264",
            },
        },
    }
    print(
        f"Built video_stitch_api for {Path(args.video).name} + {Path(args.video2).name} "
        f"direction={args.direction}, start={args.video_start_time}s, duration={args.video_duration}s"
    )
    return workflow


def load_api_workflow(path: str | Path) -> dict[str, Any]:
    workflow_path = workspace_path(path)
    with workflow_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def select_model_entries(registry: dict[str, Any], skill: dict[str, Any] | None, workflow_api_path: str | None) -> list[dict[str, Any]]:
    if skill and skill.get("model_pack"):
        return get_pack_models(registry, [skill["model_pack"]])
    if skill and skill.get("source_workflow"):
        return extract_models_from_workflow_file(skill["source_workflow"])
    if workflow_api_path:
        return extract_models_from_workflow_file(workflow_api_path)
    return []


def print_model_check(entries: list[dict[str, Any]], model_root: Path) -> list[str]:
    missing: list[str] = []
    for entry in entries:
        file_path = model_file_path(model_root, entry)
        if file_path.exists():
            print(f"READY   {file_path}")
        else:
            print(f"MISSING {entry['directory']}/{entry['name']}")
            missing.append(f"{entry['directory']}/{entry['name']}")
    return missing


def upload_image(server: str, image_path: str | Path) -> str:
    resolved = workspace_path(image_path)
    with resolved.open("rb") as handle:
        response = requests.post(
            api_url(server, "/upload/image"),
            data={"type": "input", "overwrite": "true"},
            files={"image": (resolved.name, handle, "application/octet-stream")},
            timeout=120,
        )
    response.raise_for_status()
    payload = response.json()
    return payload["name"]


def is_negative_node(node_id: str, node: dict[str, Any], current_text: str) -> bool:
    meta = node.get("_meta") or {}
    title = (meta.get("title") or "").lower()
    class_type = (node.get("class_type") or "").lower()
    lowered = current_text.lower()
    if "negative" in title or "neg" == title:
        return True
    if has_negative_hint(lowered):
        return True
    return class_type.endswith("textencode") and node_id.endswith("2") and has_negative_hint(lowered)


def patch_api_workflow(workflow: dict[str, Any], prompt: str, negative: str, seed: int | None, image_name: str | None) -> dict[str, Any]:
    prompt_patched = False
    image_patched = False
    seed_value = seed if seed is not None else random.randint(0, 2**32 - 1)

    ordered_items = sorted(workflow.items(), key=lambda item: int(item[0]) if item[0].isdigit() else item[0])
    for node_id, node in ordered_items:
        inputs = node.get("inputs") or {}

        if isinstance(inputs.get("text"), str):
            current_text = inputs.get("text", "")
            if negative and is_negative_node(node_id, node, current_text):
                inputs["text"] = negative
            elif prompt and not prompt_patched:
                inputs["text"] = prompt
                prompt_patched = True

        if image_name:
            for key in ("image", "start_image"):
                if isinstance(inputs.get(key), str) and not image_patched:
                    inputs[key] = image_name
                    image_patched = True

        for key in ("seed", "noise_seed", "random_seed"):
            if key in inputs:
                inputs[key] = seed_value

    if prompt and not prompt_patched:
        raise RuntimeError("Prompt override was requested, but no text input was patched in the API workflow.")
    if image_name and not image_patched:
        raise RuntimeError("An image was uploaded, but no image input field was found in the API workflow.")
    return workflow


def queue_prompt(server: str, workflow: dict[str, Any]) -> str:
    payload = {
        "client_id": f"copilot-{uuid.uuid4()}",
        "prompt": workflow,
    }
    response = api_json(server, "/prompt", method="POST", payload=payload)
    return response["prompt_id"]


def wait_for_completion(server: str, prompt_id: str, timeout: int) -> dict[str, Any]:
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > timeout:
            raise TimeoutError(f"Timed out after {timeout} seconds")

        history = api_json(server, f"/history/{prompt_id}")
        if prompt_id in history:
            item = history[prompt_id]
            status = item.get("status") or {}
            if status.get("completed"):
                print()
                return item
            status_message = status.get("status_str") or "running"
        else:
            status_message = "queued"

        print(f"\rWaiting for prompt {prompt_id} ... {int(elapsed)}s [{status_message}]", end="", flush=True)
        time.sleep(POLL_SECONDS)


def download_outputs(server: str, history_item: dict[str, Any], output_root: Path, prefix: str) -> list[Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[Path] = []
    outputs = history_item.get("outputs") or {}

    for node_id, node_output in outputs.items():
        for key in ("videos", "images", "gifs"):
            for asset in node_output.get(key, []):
                params = urlencode(
                    {
                        "filename": asset["filename"],
                        "subfolder": asset.get("subfolder", ""),
                        "type": asset.get("type", "output"),
                    }
                )
                response = requests.get(api_url(server, f"/view?{params}"), timeout=300)
                response.raise_for_status()
                save_path = output_root / f"{prefix}_{asset['filename']}"
                with save_path.open("wb") as handle:
                    handle.write(response.content)
                results.append(save_path)

        text_fragments: list[str] = []
        for key in ("text", "string", "strings", "STRING"):
            value = node_output.get(key)
            if isinstance(value, list):
                text_fragments.extend(str(item) for item in value)
            elif value is not None:
                text_fragments.append(str(value))

        if text_fragments:
            save_path = output_root / f"{prefix}_node{node_id}.txt"
            with save_path.open("w", encoding="utf-8") as handle:
                handle.write("\n\n".join(fragment.strip() for fragment in text_fragments if fragment is not None))
            results.append(save_path)
    return results


def skill_status(skill: dict[str, Any]) -> str:
    if skill.get("type") == "builtin":
        return "ready"

    api_workflow_path = skill.get("api_workflow_path")
    if api_workflow_path:
        return "ready" if workspace_path(api_workflow_path).exists() else "export-needed"

    if skill.get("source_workflow"):
        return "blueprint-registered"

    return "registered"


def list_skills(registry: dict[str, Any]) -> None:
    learning_tracks = registry.get("learning_tracks") or {}
    if learning_tracks:
        print("Learning tracks:")
        for track_name, track in learning_tracks.items():
            focus = track.get("focus", "")
            skills = ", ".join(track.get("skills") or [])
            print(f"- {track_name}: {focus}")
            if skills:
                print(f"  skills: {skills}")
        print()

    for name, skill in registry.get("skills", {}).items():
        status = skill_status(skill)
        print(f"{name}: {skill.get('mode', 'unknown')} [{skill.get('automation', 'unknown')}] <{status}>")
        required_inputs = skill.get("required_inputs") or []
        optional_inputs = skill.get("optional_inputs") or []
        if required_inputs:
            print(f"  required: {', '.join(required_inputs)}")
        if optional_inputs:
            print(f"  optional: {', '.join(optional_inputs)}")
        source = skill.get("source_workflow")
        if source:
            print(f"  source: {source}")
        api_workflow_path = skill.get("api_workflow_path")
        if api_workflow_path:
            print(f"  api: {api_workflow_path}")
        if skill.get("notes"):
            for note in skill["notes"]:
                print(f"  note: {note}")


def resolve_workflow(args: argparse.Namespace, registry: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, str | None, bool]:
    if args.workflow_api:
        workflow = load_api_workflow(args.workflow_api)
        return workflow, None, args.workflow_api, True

    skill = get_skill(registry, args.skill)
    if skill.get("type") == "builtin":
        builder = skill.get("builder")
        if builder == "wan22_t2v_fast":
            if not args.prompt:
                raise RuntimeError("--prompt is required for wan22_t2v_fast")
            return build_wan22_t2v_workflow(args), skill, None, False
        if builder == "video_upscale_gan_direct":
            return build_video_upscale_workflow(args), skill, None, False
        if builder == "video_stitch_direct":
            return build_video_stitch_workflow(args), skill, None, False
        if builder == "image_caption_gemini_direct":
            return build_image_caption_workflow(args), skill, None, False
        if builder == "prompt_enhance_gemini_direct":
            return build_prompt_enhance_workflow(args), skill, None, False
        if builder == "video_caption_gemini_direct":
            return build_video_caption_workflow(args), skill, None, False
        raise RuntimeError(f"Unsupported built-in builder: {builder}")

    api_workflow_path = skill.get("api_workflow_path")
    if not api_workflow_path:
        raise RuntimeError(f"Skill {args.skill} does not define an executable API workflow path.")

    resolved = workspace_path(api_workflow_path)
    if not resolved.exists():
        raise RuntimeError(
            f"Skill {args.skill} expects {relative_to_root(resolved)}. Export the source workflow to API JSON first."
        )

    workflow = load_api_workflow(resolved)
    return workflow, skill, resolved.as_posix(), True


def save_workflow(path: str | Path, workflow: dict[str, Any]) -> None:
    destination = workspace_path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(workflow, handle, indent=2, ensure_ascii=False)


def main() -> int:
    args = parse_args()
    registry = load_registry(args.registry)

    if args.list_skills:
        list_skills(registry)
        return 0

    server = args.server.rstrip("/")
    output_root = workspace_path(args.output_root or registry.get("output_root", "ComfyUI/output"))
    model_root = workspace_path(args.model_root or registry.get("model_root", "ComfyUI/models"))

    check_server(server)

    workflow, skill, workflow_api_path, needs_patch = resolve_workflow(args, registry)
    image_name = upload_image(server, args.image) if args.image and needs_patch else None
    if needs_patch:
        workflow = patch_api_workflow(workflow, args.prompt, args.negative, args.seed, image_name)

    model_entries = select_model_entries(registry, skill, workflow_api_path)
    missing = print_model_check(model_entries, model_root)
    if args.check_models:
        return 0 if not missing else 2

    if args.save_workflow:
        save_workflow(args.save_workflow, workflow)

    prompt_id = queue_prompt(server, workflow)
    print(f"Queued prompt: {prompt_id}")
    history_item = wait_for_completion(server, prompt_id, args.timeout)
    saved_files = download_outputs(server, history_item, output_root, prompt_id[:8])

    if not saved_files:
        print("No output assets were returned by ComfyUI.")
        return 1

    print("Saved files:")
    for file_path in saved_files:
        print(f"- {file_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
