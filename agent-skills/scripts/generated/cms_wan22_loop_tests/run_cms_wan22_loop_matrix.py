from __future__ import annotations

import argparse
import copy
import csv
import html
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_WORKFLOW = (
    ROOT
    / "agent-skills"
    / "comfyui"
    / "workflows"
    / "TEST"
    / "26-5-31"
    / "CMS-26-5-31 WAN2.2_LOOP_NATIVE_UPSCALER.json"
)
DEFAULT_RUNTIME = ROOT / "agent-skills" / "comfyui" / "runtime" / "cms_wan22_loop_matrix"
DEFAULT_SERVER = "http://127.0.0.1:8188"
WORKFLOW_NAME = "cms-wan22-loop-native-upscaler"
VIDEO_OUTPUT_ROOT = ROOT / "ComfyUI" / "output" / "WAN" / "agent_tests" / "cms_wan22_loop_120"


NODE = {
    "positive": 462,
    "negative": 463,
    "duration": 426,
    "frame_rate": 490,
    "steps": 82,
    "cfg": 85,
    "speed": 157,
    "motion": 605,
    "height": 556,
    "sampler_high": 603,
    "sampler_low": 604,
    "sampler_polish": 595,
    "seed": 552,
    "nag_high": 485,
    "nag_low": 486,
    "enhance_high": 481,
    "enhance_low": 482,
    "interp_rife": 538,
    "interp_gimm": 571,
    "upscale_ratio": 421,
    "save_og": 398,
    "save_fs": 541,
    "save_in": 545,
    "save_up": 611,
    "lora_high": 416,
    "lora_low": 471,
    "unet_high": 613,
    "unet_low": 614,
}


VIDEO_OUTPUT_SUFFIX = {
    NODE["save_og"]: "OG",
    NODE["save_fs"]: "FS",
    NODE["save_in"]: "IN",
    NODE["save_up"]: "UP",
}

POSTPROCESS_NODES = {
    544,  # DownloadAndLoadGIMMVFIModel
    568,  # VHS_GetImageCount
    569,  # MathExpression
    542,  # cleanGpuUsed
    NODE["save_up"],
    610,  # ImageScaleBy
    607,  # cleanGpuUsed
    608,  # ImageUpscaleWithModel
    546,  # GIMMVFI_interpolate
    609,  # easy mathFloat ratio
    NODE["save_in"],
    570,  # GetImageRangeFromBatch
}

FRAME_SKIP_PREVIEW_NODES = {
    526,  # MathExpression a-1
    527,  # RIFE VFI
    528,  # ImageFromBatch+
    529,  # easy batchAnything
    530,  # JWImageExtractFromBatch
    531,  # MathExpression a-1
    532,  # VHS_GetImageCount
    533,  # easy batchAnything
    535,  # ImageFromBatch+
    536,  # GetImageRangeFromBatch
    537,  # MathExpression a-b-c
    NODE["interp_rife"],
    539,  # End frame
    540,  # Start frame
    NODE["save_fs"],
}

SEED_CONTROL_VALUES = {"fixed", "increment", "decrement", "randomize"}


@dataclass(frozen=True)
class Case:
    case_id: str
    description: str
    steps: int
    cfg: float
    speed: float
    motion: float
    nag_scale: float
    nag_alpha: float
    nag_tau: float
    enhance: float
    interpolation: int
    upscale_ratio: float
    crf: int
    lora_strength: float
    high_denoise: float = 1.0
    low_denoise: float = 1.0
    polish_denoise: float = 0.2


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    description: str
    high_unet: str
    low_unet: str
    high_lora: str
    low_lora: str


CASES = [
    Case(
        case_id="p01_baseline",
        description="Current prompt, fixed seed, 120-frame baseline.",
        steps=8,
        cfg=1.2,
        speed=5.0,
        motion=1.0,
        nag_scale=11.0,
        nag_alpha=0.25,
        nag_tau=2.373,
        enhance=1.0,
        interpolation=2,
        upscale_ratio=1.0,
        crf=19,
        lora_strength=0.8,
    ),
    Case(
        case_id="p02_low_guidance",
        description="Lower CFG and NAG to check whether artifacts decrease.",
        steps=8,
        cfg=0.95,
        speed=5.0,
        motion=1.0,
        nag_scale=8.5,
        nag_alpha=0.2,
        nag_tau=2.1,
        enhance=0.9,
        interpolation=2,
        upscale_ratio=1.0,
        crf=19,
        lora_strength=0.75,
    ),
    Case(
        case_id="p03_detail_push",
        description="More steps, stronger CFG, and stronger enhancement for detail.",
        steps=10,
        cfg=1.35,
        speed=5.0,
        motion=1.0,
        nag_scale=11.5,
        nag_alpha=0.25,
        nag_tau=2.6,
        enhance=1.2,
        interpolation=2,
        upscale_ratio=1.0,
        crf=18,
        lora_strength=0.85,
    ),
    Case(
        case_id="p04_motion_push",
        description="Higher sampling speed and motion amplitude for stronger movement.",
        steps=8,
        cfg=1.15,
        speed=7.0,
        motion=1.4,
        nag_scale=11.0,
        nag_alpha=0.25,
        nag_tau=2.373,
        enhance=1.0,
        interpolation=2,
        upscale_ratio=1.0,
        crf=19,
        lora_strength=0.8,
    ),
    Case(
        case_id="p05_smooth_motion",
        description="Lower speed and motion amplitude to test smoother, steadier movement.",
        steps=8,
        cfg=1.05,
        speed=4.0,
        motion=0.8,
        nag_scale=9.5,
        nag_alpha=0.22,
        nag_tau=2.2,
        enhance=1.05,
        interpolation=2,
        upscale_ratio=1.0,
        crf=18,
        lora_strength=0.8,
    ),
]


MODEL_PROFILES = [
    ModelProfile(
        profile_id="m03_q8_svi_pro",
        description="Dasiwa q8 High/Low GGUF with SVI Wan2.2 I2V A14B v2.0 Pro High/Low LoRA pair.",
        high_unet=r"WAN2.2\DasiwaWAN22I2V14BTastysinV8_q8High.gguf",
        low_unet=r"WAN2.2\DasiwaWAN22I2V14BTastysinV8_q8Low.gguf",
        high_lora=r"WAN2.2\SVI_Wan2.2-I2V-A14B_high_noise_lora_v2.0_pro.safetensors",
        low_lora=r"WAN2.2\SVI_Wan2.2-I2V-A14B_low_noise_lora_v2.0_pro.safetensors",
    ),
    ModelProfile(
        profile_id="m04_q8_cumv2",
        description="Dasiwa q8 High/Low GGUF with Wan22 CumV2 High/Low LoRA pair.",
        high_unet=r"WAN2.2\DasiwaWAN22I2V14BTastysinV8_q8High.gguf",
        low_unet=r"WAN2.2\DasiwaWAN22I2V14BTastysinV8_q8Low.gguf",
        high_lora=r"WAN2.2\Wan22_CumV2_High.safetensors",
        low_lora=r"WAN2.2\Wan22_CumV2_Low.safetensors",
    ),
    ModelProfile(
        profile_id="m05_q8_g4gg1ng",
        description="Dasiwa q8 High/Low GGUF with G4GG1NG v6 High/Low I2V LoRA pair.",
        high_unet=r"WAN2.2\DasiwaWAN22I2V14BTastysinV8_q8High.gguf",
        low_unet=r"WAN2.2\DasiwaWAN22I2V14BTastysinV8_q8Low.gguf",
        high_lora=r"WAN2.2\wan22-G4GG1NGv6-11epoc-high-i2v-k3nk.safetensors",
        low_lora=r"WAN2.2\wan22-G4GG1NGv6-11epoc-low-i2v-k3nk.safetensors",
    ),
]

LEGACY_MODEL_PROFILES = [
    ModelProfile(
        profile_id="m01_current_q8_nsfw",
        description="Legacy/source baseline: Dasiwa q8 High/Low GGUF with current NSFW-22 High/Low LoRA pair.",
        high_unet=r"WAN2.2\DasiwaWAN22I2V14BTastysinV8_q8High.gguf",
        low_unet=r"WAN2.2\DasiwaWAN22I2V14BTastysinV8_q8Low.gguf",
        high_lora=r"WAN2.2\NSFW-22-H-e8.safetensors",
        low_lora=r"WAN2.2\NSFW-22-L-e8.safetensors",
    ),
    ModelProfile(
        profile_id="m02_official_q4_lightx2v",
        description="Legacy/official comparison: Wan2.2 I2V Q4_K_S High/Low GGUF with official Lightx2v 4-step LoRA pair.",
        high_unet="Wan2.2-I2V-HighNoise-14B-Q4_K_S.gguf",
        low_unet="Wan2.2-I2V-LowNoise-14B-Q4_K_S.gguf",
        high_lora="wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
        low_lora="wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
    ),
]

KNOWN_MODEL_PROFILES = MODEL_PROFILES + LEGACY_MODEL_PROFILES
LEGACY_OUTPUT_PROFILE_IDS = {"m01_current_q8_nsfw"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and optionally submit a 5-case parameter matrix for the CMS Wan2.2 loop workflow."
    )
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW, help="UI workflow JSON path.")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="ComfyUI server URL.")
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME, help="Runtime output root.")
    parser.add_argument("--length", type=int, default=120, help="Target generated frame length.")
    parser.add_argument("--fps", type=float, default=16.0, help="Base frame rate used by the workflow.")
    parser.add_argument("--seed", type=int, default=260531120, help="Fixed seed used for all cases.")
    parser.add_argument(
        "--random-seeds",
        action="store_true",
        help="Use a different deterministic seed per case instead of the same seed.",
    )
    parser.add_argument("--run-id", default="", help="Optional run id. Defaults to timestamp.")
    parser.add_argument("--only", nargs="*", default=[], help="Only build or submit these case ids.")
    parser.add_argument(
        "--model-profiles",
        nargs="*",
        default=[],
        help="Run only these model/LoRA profile ids. Accepts comma or space separated values.",
    )
    parser.add_argument(
        "--all-model-profiles",
        action="store_true",
        help="Run all built-in model/LoRA profiles. This expands the matrix to 3 profiles x selected cases.",
    )
    parser.add_argument(
        "--list-model-profiles",
        action="store_true",
        help="Print the built-in model/LoRA profiles and exit.",
    )
    parser.add_argument(
        "--rerun-completed",
        action="store_true",
        help="Do not skip cases/profile cases that already have an OG mp4 under the shared test output root.",
    )
    parser.add_argument("--submit", action="store_true", help="Submit converted API prompts to ComfyUI.")
    parser.add_argument("--no-wait", action="store_true", help="Do not wait for submitted jobs to finish.")
    parser.add_argument("--timeout", type=int, default=7200, help="Wait timeout per prompt in seconds.")
    parser.add_argument("--poll", type=float, default=5.0, help="History polling interval in seconds.")
    parser.add_argument(
        "--skip-free-memory",
        action="store_true",
        help="Do not call /free before each submitted case.",
    )
    parser.add_argument(
        "--allow-ui-convert",
        action="store_true",
        help="Allow the built-in UI-to-API converter for submission. Dry-run always works without this.",
    )
    parser.add_argument(
        "--write-api",
        action="store_true",
        help="Write converted API prompt JSON files next to UI variants.",
    )
    parser.add_argument(
        "--artifact-mode",
        choices=("minimal", "full"),
        default="minimal",
        help="minimal writes report/manifest/logs only; full also writes UI/API/history JSON snapshots.",
    )
    parser.add_argument(
        "--keep-disabled-postprocess",
        action="store_true",
        help="Keep the source workflow's disabled interpolation/upscale output chain disabled.",
    )
    parser.add_argument(
        "--enable-postprocess",
        action="store_true",
        help="Enable the source workflow's disabled interpolation/upscale output chain. Slower and depends on GIMMVFI/CUDA headers.",
    )
    parser.add_argument(
        "--enable-frame-skip-preview",
        action="store_true",
        help="Keep the RIFE frame-skip preview/temp video chain enabled. Default disables it so only OG output runs.",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def node_by_id(workflow: dict[str, Any], node_id: int) -> dict[str, Any]:
    for node in workflow.get("nodes", []):
        if node.get("id") == node_id:
            return node
    raise KeyError(f"Node id {node_id} not found")


def set_slider(workflow: dict[str, Any], node_id: int, value: float, *, is_float: bool) -> None:
    node = node_by_id(workflow, node_id)
    widgets = node.setdefault("widgets_values", [])
    if not isinstance(widgets, list) or len(widgets) < 3:
        raise ValueError(f"Node {node_id} is not an mxSlider-like node")
    if is_float:
        widgets[0] = int(value)
        widgets[1] = float(value)
        widgets[2] = 1
    else:
        widgets[0] = int(round(value))
        widgets[1] = int(round(value))
        widgets[2] = 0
    props = node.setdefault("properties", {})
    props["value"] = float(value) if is_float else int(round(value))


def set_list_widget(workflow: dict[str, Any], node_id: int, index: int, value: Any) -> None:
    node = node_by_id(workflow, node_id)
    widgets = node.setdefault("widgets_values", [])
    if not isinstance(widgets, list) or len(widgets) <= index:
        raise ValueError(f"Node {node_id} widget index {index} not found")
    widgets[index] = value


def set_dict_widget(workflow: dict[str, Any], node_id: int, key: str, value: Any) -> None:
    node = node_by_id(workflow, node_id)
    widgets = node.setdefault("widgets_values", {})
    if not isinstance(widgets, dict):
        raise ValueError(f"Node {node_id} widgets_values is not a dict")
    widgets[key] = value


def profile_output_segment(profile: ModelProfile | None) -> str:
    return f"{profile.profile_id}/" if profile else ""


def set_video_prefixes(workflow: dict[str, Any], run_id: str, case_id: str, crf: int, profile: ModelProfile | None) -> None:
    for node_id, suffix in VIDEO_OUTPUT_SUFFIX.items():
        node = node_by_id(workflow, node_id)
        widgets = node.setdefault("widgets_values", {})
        if not isinstance(widgets, dict):
            continue
        widgets["filename_prefix"] = (
            f"WAN/agent_tests/cms_wan22_loop_120/{run_id}/"
            f"{profile_output_segment(profile)}{case_id}_{suffix}"
        )
        widgets["crf"] = int(crf)
        widgets.pop("videopreview", None)


def enable_postprocess_chain(workflow: dict[str, Any]) -> None:
    for node in workflow.get("nodes", []):
        if node.get("id") in POSTPROCESS_NODES:
            node["mode"] = 0


def disable_frame_skip_preview_chain(workflow: dict[str, Any]) -> None:
    for node in workflow.get("nodes", []):
        if node.get("id") in FRAME_SKIP_PREVIEW_NODES:
            node["mode"] = 2


def set_lora_strength(workflow: dict[str, Any], node_id: int, strength: float) -> None:
    node = node_by_id(workflow, node_id)
    widgets = node.setdefault("widgets_values", [])
    if not isinstance(widgets, list):
        raise ValueError(f"Node {node_id} widgets_values is not a list")
    for value in widgets:
        if isinstance(value, dict) and {"on", "lora", "strength"}.issubset(value):
            value["strength"] = float(strength)
            if value.get("strengthTwo") is not None:
                value["strengthTwo"] = float(strength)


def set_power_lora(workflow: dict[str, Any], node_id: int, lora_name: str, strength: float) -> None:
    node = node_by_id(workflow, node_id)
    widgets = node.setdefault("widgets_values", [])
    if not isinstance(widgets, list):
        raise ValueError(f"Node {node_id} widgets_values is not a list")
    for value in widgets:
        if isinstance(value, dict) and {"on", "lora", "strength"}.issubset(value):
            value["on"] = True
            value["lora"] = lora_name
            value["strength"] = float(strength)
            if value.get("strengthTwo") is not None:
                value["strengthTwo"] = float(strength)
            return
    raise ValueError(f"Node {node_id} has no rgthree Power LoRA slot")


def apply_model_profile(workflow: dict[str, Any], profile: ModelProfile, lora_strength: float) -> None:
    set_list_widget(workflow, NODE["unet_high"], 0, profile.high_unet)
    set_list_widget(workflow, NODE["unet_low"], 0, profile.low_unet)
    set_power_lora(workflow, NODE["lora_high"], profile.high_lora, lora_strength)
    set_power_lora(workflow, NODE["lora_low"], profile.low_lora, lora_strength)


def set_nag(workflow: dict[str, Any], node_id: int, case: Case) -> None:
    set_list_widget(workflow, node_id, 0, float(case.nag_scale))
    set_list_widget(workflow, node_id, 1, float(case.nag_alpha))
    set_list_widget(workflow, node_id, 2, float(case.nag_tau))


def set_sampler_denoise(workflow: dict[str, Any], node_id: int, denoise: float) -> None:
    # ClownsharKSampler_Beta widget order:
    # eta, sampler_name, scheduler, steps, steps_to_run, denoise, cfg, seed,
    # sampler_mode, extra_mode, bongmath.
    set_list_widget(workflow, node_id, 5, float(denoise))


def seed_for_case(base_seed: int, index: int, random_seeds: bool) -> int:
    if not random_seeds:
        return base_seed
    rng = random.Random(base_seed + index * 7919)
    return rng.randint(1, 1125899906842624)


def apply_case(
    base_workflow: dict[str, Any],
    case: Case,
    *,
    profile: ModelProfile | None,
    case_index: int,
    run_id: str,
    length: int,
    fps: float,
    seed: int,
    random_seeds: bool,
    enable_postprocess: bool,
    enable_frame_skip_preview: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    workflow = copy.deepcopy(base_workflow)
    duration = (length - 1) / fps
    case_seed = seed_for_case(seed, case_index, random_seeds)

    if enable_postprocess:
        enable_postprocess_chain(workflow)
    if not enable_frame_skip_preview:
        disable_frame_skip_preview_chain(workflow)

    if profile is not None:
        apply_model_profile(workflow, profile, case.lora_strength)

    set_slider(workflow, NODE["frame_rate"], fps, is_float=True)
    set_slider(workflow, NODE["duration"], duration, is_float=True)
    set_slider(workflow, NODE["steps"], case.steps, is_float=False)
    set_slider(workflow, NODE["cfg"], case.cfg, is_float=True)
    set_slider(workflow, NODE["speed"], case.speed, is_float=True)
    set_slider(workflow, NODE["motion"], case.motion, is_float=True)
    set_slider(workflow, NODE["interp_rife"], case.interpolation, is_float=False)
    set_slider(workflow, NODE["interp_gimm"], case.interpolation, is_float=False)
    set_slider(workflow, NODE["upscale_ratio"], case.upscale_ratio, is_float=True)

    set_list_widget(workflow, NODE["seed"], 0, case_seed)
    set_list_widget(workflow, NODE["sampler_high"], 7, case_seed)
    set_list_widget(workflow, NODE["sampler_low"], 7, case_seed)
    set_list_widget(workflow, NODE["sampler_polish"], 7, case_seed)
    set_list_widget(workflow, 546, 2, case_seed)
    set_list_widget(workflow, NODE["enhance_high"], 0, case.enhance)
    set_list_widget(workflow, NODE["enhance_low"], 0, case.enhance)
    set_nag(workflow, NODE["nag_high"], case)
    set_nag(workflow, NODE["nag_low"], case)
    set_sampler_denoise(workflow, NODE["sampler_high"], case.high_denoise)
    set_sampler_denoise(workflow, NODE["sampler_low"], case.low_denoise)
    set_sampler_denoise(workflow, NODE["sampler_polish"], case.polish_denoise)
    set_lora_strength(workflow, NODE["lora_high"], case.lora_strength)
    set_lora_strength(workflow, NODE["lora_low"], case.lora_strength)
    set_video_prefixes(workflow, run_id, case.case_id, case.crf, profile)

    metadata = {
        "profile_id": profile.profile_id if profile else "",
        "profile_description": profile.description if profile else "Source workflow model and LoRA settings.",
        "unet_high": profile.high_unet if profile else "",
        "unet_low": profile.low_unet if profile else "",
        "lora_high": profile.high_lora if profile else "",
        "lora_low": profile.low_lora if profile else "",
        "case_id": case.case_id,
        "description": case.description,
        "target_length_frames": length,
        "base_fps": fps,
        "computed_duration_seconds": duration,
        "seed": case_seed,
        "steps": case.steps,
        "cfg": case.cfg,
        "speed": case.speed,
        "motion_amplitude": case.motion,
        "nag_scale": case.nag_scale,
        "nag_alpha": case.nag_alpha,
        "nag_tau": case.nag_tau,
        "enhance": case.enhance,
        "interpolation": case.interpolation,
        "upscale_ratio": case.upscale_ratio,
        "crf": case.crf,
        "lora_strength": case.lora_strength,
        "postprocess_enabled": enable_postprocess,
        "frame_skip_preview_enabled": enable_frame_skip_preview,
    }
    return workflow, metadata


def normalize_case_ids(values: list[str]) -> list[str]:
    case_ids: list[str] = []
    for value in values:
        for part in value.split(","):
            part = part.strip()
            if part:
                case_ids.append(part)
    return case_ids


def selected_model_profiles(values: list[str], all_profiles: bool) -> list[ModelProfile | None]:
    if all_profiles:
        return list(MODEL_PROFILES)
    requested_ids = normalize_case_ids(values)
    if not requested_ids:
        return [None]
    requested = set(requested_ids)
    known = {profile.profile_id for profile in KNOWN_MODEL_PROFILES}
    missing = sorted(requested - known)
    if missing:
        raise ValueError(f"Unknown model profile id(s): {', '.join(missing)}")
    return [profile for profile in KNOWN_MODEL_PROFILES if profile.profile_id in requested]


def selected_cases(only: list[str]) -> list[Case]:
    requested_ids = normalize_case_ids(only)
    if not requested_ids:
        return CASES
    requested = set(requested_ids)
    known = {case.case_id for case in CASES}
    missing = sorted(requested - known)
    if missing:
        raise ValueError(f"Unknown case id(s): {', '.join(missing)}")
    return [case for case in CASES if case.case_id in requested]


def metadata_for_case(
    case: Case,
    *,
    profile: ModelProfile | None,
    case_index: int,
    length: int,
    fps: float,
    seed: int,
    random_seeds: bool,
    enable_postprocess: bool,
    enable_frame_skip_preview: bool,
) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id if profile else "",
        "profile_description": profile.description if profile else "Source workflow model and LoRA settings.",
        "unet_high": profile.high_unet if profile else "",
        "unet_low": profile.low_unet if profile else "",
        "lora_high": profile.high_lora if profile else "",
        "lora_low": profile.low_lora if profile else "",
        "case_id": case.case_id,
        "description": case.description,
        "target_length_frames": length,
        "base_fps": fps,
        "computed_duration_seconds": (length - 1) / fps,
        "seed": seed_for_case(seed, case_index, random_seeds),
        "steps": case.steps,
        "cfg": case.cfg,
        "speed": case.speed,
        "motion_amplitude": case.motion,
        "nag_scale": case.nag_scale,
        "nag_alpha": case.nag_alpha,
        "nag_tau": case.nag_tau,
        "enhance": case.enhance,
        "interpolation": case.interpolation,
        "upscale_ratio": case.upscale_ratio,
        "crf": case.crf,
        "lora_strength": case.lora_strength,
        "postprocess_enabled": enable_postprocess,
        "frame_skip_preview_enabled": enable_frame_skip_preview,
    }


def output_ref_from_path(path: Path) -> str:
    rel = path.relative_to(ROOT / "ComfyUI" / "output").as_posix()
    return f"output:{rel}"


def find_existing_case_outputs(case_id: str, profile: ModelProfile | None) -> list[str]:
    if not VIDEO_OUTPUT_ROOT.exists():
        return []
    patterns = []
    if profile is not None:
        patterns.append(f"*/{profile.profile_id}/{case_id}_OG_*.mp4")
        if profile.profile_id in LEGACY_OUTPUT_PROFILE_IDS:
            patterns.append(f"*/{case_id}_OG_*.mp4")
    else:
        patterns.append(f"*/{case_id}_OG_*.mp4")

    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(VIDEO_OUTPUT_ROOT.glob(pattern))
    matches = sorted(set(matches), key=lambda path: path.stat().st_mtime, reverse=True)
    return [output_ref_from_path(matches[0])] if matches else []


def fetch_json(server: str, path: str, *, timeout: float = 10.0) -> dict[str, Any]:
    url = server.rstrip("/") + path
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {path} HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {path} failed: {exc.reason}") from exc
    return json.loads(raw)


def post_json(server: str, path: str, body: dict[str, Any], *, timeout: float = 60.0) -> dict[str, Any]:
    url = server.rstrip("/") + path
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {path} HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST {path} failed: {exc.reason}") from exc
    return json.loads(raw)


def free_memory(server: str) -> None:
    url = server.rstrip("/") + "/free"
    data = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        resp.read()
    time.sleep(2.0)


def link_map(ui_workflow: dict[str, Any]) -> dict[int, list[Any]]:
    return {int(link[0]): link for link in ui_workflow.get("links", [])}


def widget_values_for_api(node: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    widgets = node.get("widgets_values", [])

    if isinstance(widgets, dict):
        for item in node.get("inputs", []):
            name = item.get("name")
            if not name:
                continue
            if "widget" in item and name in widgets:
                values[name] = widgets[name]
        for extra_key in ("pix_fmt", "crf", "save_metadata", "trim_to_audio", "lossless"):
            if extra_key in widgets:
                values[extra_key] = widgets[extra_key]
        return values

    if not isinstance(widgets, list):
        return values

    widget_index = 0
    for item in node.get("inputs", []):
        name = item.get("name")
        if not name or "widget" not in item:
            continue
        if widget_index >= len(widgets):
            break
        value = widgets[widget_index]
        widget_index += 1
        values[name] = value
        if name == "seed" and widget_index < len(widgets) and widgets[widget_index] in SEED_CONTROL_VALUES:
            widget_index += 1

    if node.get("type") == "Power Lora Loader (rgthree)":
        lora_index = 1
        for value in widgets:
            if isinstance(value, dict) and {"on", "lora", "strength"}.issubset(value):
                values[f"lora_{lora_index}"] = value
                lora_index += 1

    return values


def ui_to_api_prompt(ui_workflow: dict[str, Any]) -> dict[str, Any]:
    links = link_map(ui_workflow)
    prompt: dict[str, Any] = {}
    active_node_ids = {
        node.get("id")
        for node in ui_workflow.get("nodes", [])
        if node.get("mode", 0) not in (2, 4)
    }

    for node in ui_workflow.get("nodes", []):
        if node.get("mode", 0) in (2, 4):
            continue

        node_id = str(node.get("id"))
        class_type = node.get("type")
        if not node_id or not class_type:
            continue

        inputs = widget_values_for_api(node)
        for index, item in enumerate(node.get("inputs", [])):
            name = item.get("name")
            if not name:
                continue
            link_id = item.get("link")
            if link_id is None:
                continue
            link = links.get(int(link_id))
            if not link:
                raise ValueError(f"Link id {link_id} for node {node_id}:{name} was not found")
            _, source_id, source_slot, _, _, _ = link
            if source_id not in active_node_ids:
                continue
            inputs[name] = [str(source_id), int(source_slot)]

        prompt[node_id] = {"class_type": class_type, "inputs": inputs}

    return prompt


def collect_node_types(ui_workflow: dict[str, Any]) -> set[str]:
    return {
        str(node.get("type"))
        for node in ui_workflow.get("nodes", [])
        if node.get("type") and node.get("mode", 0) not in (2, 4)
    }


def preflight_server(server: str, ui_workflow: dict[str, Any]) -> dict[str, Any]:
    stats = fetch_json(server, "/system_stats", timeout=5)
    object_info = fetch_json(server, "/object_info", timeout=20)
    missing = sorted(collect_node_types(ui_workflow) - set(object_info))
    return {"stats": stats, "object_info": object_info, "missing_node_types": missing}


def combo_label(profile: ModelProfile | None, case_id: str) -> str:
    return f"{profile.profile_id}/{case_id}" if profile else case_id


def combo_filename_stem(profile: ModelProfile | None, case_id: str) -> str:
    return f"{profile.profile_id}.{case_id}" if profile else case_id


def combo_client_case(profile_id: str, case_id: str) -> str:
    return f"{profile_id}:{case_id}" if profile_id else case_id


def combo_queue_case(profile: ModelProfile | None, case_id: str) -> str:
    return combo_client_case(profile.profile_id if profile else "", case_id)


def object_combo_values(object_info: dict[str, Any], class_type: str, input_name: str) -> set[str]:
    spec = (
        object_info.get(class_type, {})
        .get("input", {})
        .get("required", {})
        .get(input_name)
    )
    if isinstance(spec, list) and spec and isinstance(spec[0], list):
        return {str(value) for value in spec[0]}
    return set()


def validate_model_profiles(profiles: list[ModelProfile | None], object_info: dict[str, Any]) -> None:
    selected = [profile for profile in profiles if profile is not None]
    if not selected:
        return

    unet_names = object_combo_values(object_info, "UnetLoaderGGUF", "unet_name")
    lora_names = object_combo_values(object_info, "LoraLoader", "lora_name")
    errors: list[str] = []

    for profile in selected:
        for label, value in (("high_unet", profile.high_unet), ("low_unet", profile.low_unet)):
            if value not in unet_names:
                errors.append(f"{profile.profile_id}.{label}: {value}")
        for label, value in (("high_lora", profile.high_lora), ("low_lora", profile.low_lora)):
            if value not in lora_names:
                errors.append(f"{profile.profile_id}.{label}: {value}")

    if errors:
        raise RuntimeError("Model profile file(s) not available in ComfyUI object_info: " + "; ".join(errors))


def client_id_for(run_id: str, case_id: str, profile_id: str = "") -> str:
    return f"agent:codex|workflow:{WORKFLOW_NAME}|run:{run_id[:8]}|case:{combo_client_case(profile_id, case_id)}"


def submit_prompt(server: str, prompt: dict[str, Any], run_id: str, case_meta: dict[str, Any]) -> str:
    profile_id = str(case_meta.get("profile_id", ""))
    profile_note = f"profile={profile_id}, " if profile_id else ""
    notes = (
        f"{profile_note}{case_meta['case_id']}: length={case_meta['target_length_frames']}, "
        f"fps={case_meta['base_fps']}, steps={case_meta['steps']}, cfg={case_meta['cfg']}, "
        f"speed={case_meta['speed']}, motion={case_meta['motion_amplitude']}, "
        f"nag={case_meta['nag_scale']}/{case_meta['nag_alpha']}/{case_meta['nag_tau']}, "
        f"interpolation={case_meta['interpolation']}, upscale={case_meta['upscale_ratio']}, "
        f"seed={case_meta['seed']}, "
        f"high_unet={case_meta.get('unet_high', '')}, low_unet={case_meta.get('unet_low', '')}, "
        f"high_lora={case_meta.get('lora_high', '')}, low_lora={case_meta.get('lora_low', '')}"
    )
    payload = {
        "prompt": prompt,
        "client_id": client_id_for(run_id, str(case_meta["case_id"]), profile_id),
        "extra_data": {
            "agent": "codex",
            "workflow_name": WORKFLOW_NAME,
            "source": "agent-skills/scripts/generated/cms_wan22_loop_tests/run_cms_wan22_loop_matrix.py",
            "notes": notes,
            "case": case_meta,
        },
    }
    response = post_json(server, "/prompt", payload, timeout=60)
    prompt_id = response.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI did not return prompt_id: {response}")
    return str(prompt_id)


def wait_for_history(server: str, prompt_id: str, timeout: int, poll: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = fetch_json(server, f"/history/{prompt_id}", timeout=20)
        item = history.get(prompt_id)
        if item:
            return item
        time.sleep(poll)
    return {"status": {"status_str": "timeout"}, "outputs": {}}


def output_files_from_history(history_item: dict[str, Any]) -> list[str]:
    files: list[str] = []
    outputs = history_item.get("outputs") or {}
    for value in outputs.values():
        if not isinstance(value, dict):
            continue
        for key in ("gifs", "images", "audio", "animated"):
            for item in value.get(key, []) or []:
                if isinstance(item, dict):
                    filename = item.get("filename")
                    subfolder = item.get("subfolder", "")
                    item_type = item.get("type", "output")
                    if filename:
                        files.append(f"{item_type}:{subfolder}/{filename}".replace("\\", "/"))
    return files


def resolve_output_ref(ref: str) -> Path | None:
    if ":" not in ref:
        return None
    item_type, rel = ref.split(":", 1)
    rel = rel.lstrip("/").replace("/", os.sep)
    if item_type == "output":
        return ROOT / "ComfyUI" / "output" / rel
    if item_type == "temp":
        return ROOT / "ComfyUI" / "temp" / rel
    if item_type == "input":
        return ROOT / "ComfyUI" / "input" / rel
    return None


def html_video_block(report_dir: Path, outputs: str) -> str:
    refs = [part.strip() for part in outputs.split(";") if part.strip()]
    blocks: list[str] = []
    for ref in refs:
        output_path = resolve_output_ref(ref)
        if output_path is None:
            blocks.append(f"<div class=\"missing\">{html.escape(ref)}</div>")
            continue
        rel = os.path.relpath(output_path, report_dir).replace("\\", "/")
        label = html.escape(ref)
        if output_path.suffix.lower() in {".mp4", ".webm", ".mkv", ".mov"}:
            blocks.append(
                f"<figure><video controls preload=\"metadata\" src=\"{html.escape(rel)}\"></video>"
                f"<figcaption>{label}</figcaption></figure>"
            )
        else:
            blocks.append(f"<a href=\"{html.escape(rel)}\">{label}</a>")
    return "\n".join(blocks) if blocks else "<span class=\"muted\">未生成输出</span>"


def write_html_report(path: Path, rows: list[dict[str, Any]], *, submit: bool, run_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cards: list[str] = []
    for row in rows:
        params = [
            ("profile", row.get("profile_id", "")),
            ("长度", row["target_length_frames"]),
            ("fps", row["base_fps"]),
            ("seed", row["seed"]),
            ("steps", row["steps"]),
            ("cfg", row["cfg"]),
            ("speed", row["speed"]),
            ("motion", row["motion_amplitude"]),
            ("NAG", f"{row['nag_scale']} / {row['nag_alpha']} / {row['nag_tau']}"),
            ("enhance", row["enhance"]),
            ("插帧", row["interpolation"]),
            ("upscale", row["upscale_ratio"]),
            ("crf", row["crf"]),
            ("High UNet", row.get("unet_high", "")),
            ("Low UNet", row.get("unet_low", "")),
            ("High LoRA", row.get("lora_high", "")),
            ("Low LoRA", row.get("lora_low", "")),
        ]
        param_html = "".join(
            f"<li><span>{html.escape(str(name))}</span><strong>{html.escape(str(value))}</strong></li>"
            for name, value in params
        )
        cards.append(
            f"""
            <section class="case">
              <header>
                <div>
                  <h2>{html.escape(str(row['case_id']))}</h2>
                  <p class="profile">{html.escape(str(row.get('profile_id', '')))}</p>
                  <p>{html.escape(str(row['description']))}</p>
                  <p>{html.escape(str(row.get('profile_description', '')))}</p>
                </div>
                <span class="status">{html.escape(str(row['status']))}</span>
              </header>
              <ul class="params">{param_html}</ul>
              <div class="videos">{html_video_block(path.parent, str(row.get('outputs', '')))}</div>
              <details>
                <summary>运行记录</summary>
                <p>prompt_id: {html.escape(str(row.get('prompt_id', '')))}</p>
                <p>UI workflow: {html.escape(str(row.get('ui_workflow', '')))}</p>
                <p>API prompt: {html.escape(str(row.get('api_prompt', '')))}</p>
              </details>
            </section>
            """
        )
    doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CMS Wan2.2 Loop 测试报表 - {html.escape(run_id)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #101214;
      --panel: #181c20;
      --line: #2a3138;
      --text: #eef2f5;
      --muted: #9ba7b2;
      --accent: #74d3ae;
      --accent-2: #e7c46c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    main {{
      width: min(1480px, calc(100vw - 40px));
      margin: 0 auto;
      padding: 28px 0 44px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    .meta {{ color: var(--muted); margin: 0 0 22px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
      gap: 18px;
    }}
    .case {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      border-bottom: 1px solid var(--line);
      padding-bottom: 12px;
    }}
    h2 {{ margin: 0 0 6px; font-size: 20px; }}
    .profile {{ color: var(--accent-2); font-weight: 700; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    .status {{
      color: #101214;
      background: var(--accent);
      border-radius: 999px;
      padding: 4px 10px;
      font-weight: 700;
      white-space: nowrap;
    }}
    .params {{
      list-style: none;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      padding: 0;
      margin: 14px 0;
    }}
    .params li {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      min-width: 0;
    }}
    .params span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .params strong {{
      display: block;
      font-size: 14px;
      overflow-wrap: anywhere;
    }}
    .videos {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    figure {{ margin: 0; }}
    video {{
      display: block;
      width: 100%;
      max-height: 420px;
      background: #000;
      border-radius: 6px;
      border: 1px solid var(--line);
    }}
    figcaption {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 5px;
      overflow-wrap: anywhere;
    }}
    details {{
      margin-top: 12px;
      border-top: 1px solid var(--line);
      padding-top: 10px;
      color: var(--muted);
      font-size: 13px;
    }}
    summary {{ cursor: pointer; color: var(--accent-2); }}
    .muted, .missing {{ color: var(--muted); }}
    @media (max-width: 760px) {{
      main {{ width: calc(100vw - 24px); padding-top: 18px; }}
      .grid {{ grid-template-columns: 1fr; }}
      .params {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>CMS Wan2.2 Loop 参数测试报表</h1>
    <p class="meta">run_id: {html.escape(run_id)} · submit: {submit} · cases: {len(rows)}</p>
    <div class="grid">
      {''.join(cards)}
    </div>
  </main>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")


def write_manifest_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown_report(path: Path, rows: list[dict[str, Any]], *, submit: bool) -> None:
    lines = [
        "# CMS Wan2.2 Loop Parameter Matrix",
        "",
        f"- submit: {submit}",
        f"- cases: {len(rows)}",
        "",
        "| profile | case | length | fps | seed | steps | cfg | speed | motion | nag | interp | upscale | status |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    for row in rows:
        nag = f"{row['nag_scale']}/{row['nag_alpha']}/{row['nag_tau']}"
        lines.append(
            "| {profile_id} | {case_id} | {target_length_frames} | {base_fps} | {seed} | {steps} | {cfg} | "
            "{speed} | {motion_amplitude} | "
            f"{nag} | "
            "{interpolation} | {upscale_ratio} | {status} |".format(**row)
        )
    lines.append("")
    lines.append("Review the OG, IN, and UP outputs for each case when available.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.list_model_profiles:
        print("Default profiles used by --all-model-profiles:")
        for profile in MODEL_PROFILES:
            print(f"{profile.profile_id}: {profile.description}")
            print(f"  high_unet: {profile.high_unet}")
            print(f"  low_unet:  {profile.low_unet}")
            print(f"  high_lora: {profile.high_lora}")
            print(f"  low_lora:  {profile.low_lora}")
        print("\nLegacy profiles available only when explicitly selected with --model-profiles:")
        for profile in LEGACY_MODEL_PROFILES:
            print(f"{profile.profile_id}: {profile.description}")
            print(f"  high_unet: {profile.high_unet}")
            print(f"  low_unet:  {profile.low_unet}")
            print(f"  high_lora: {profile.high_lora}")
            print(f"  low_lora:  {profile.low_lora}")
        return 0

    workflow_path = args.workflow.resolve()
    if not workflow_path.is_file():
        raise FileNotFoundError(workflow_path)
    if args.length < 2:
        raise ValueError("--length must be at least 2")
    if args.fps <= 0:
        raise ValueError("--fps must be positive")
    if args.submit and not args.allow_ui_convert:
        raise SystemExit(
            "Refusing to submit a UI workflow unless --allow-ui-convert is set. "
            "Run once without --submit first and inspect the generated variants."
        )

    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = (args.runtime_dir / run_id).resolve()
    variants_dir = run_dir / "workflow_variants"
    api_dir = run_dir / "api_prompts"
    run_dir.mkdir(parents=True, exist_ok=True)

    base_workflow = read_json(workflow_path)
    cases = selected_cases(args.only)
    profiles = selected_model_profiles(args.model_profiles, args.all_model_profiles)
    enable_postprocess = args.enable_postprocess and not args.keep_disabled_postprocess
    enable_frame_skip_preview = args.enable_frame_skip_preview

    preflight: dict[str, Any] | None = None
    if args.submit or args.write_api:
        preflight_workflow = copy.deepcopy(base_workflow)
        if enable_postprocess:
            enable_postprocess_chain(preflight_workflow)
        if not enable_frame_skip_preview:
            disable_frame_skip_preview_chain(preflight_workflow)
        preflight = preflight_server(args.server, preflight_workflow)
        if args.artifact_mode == "full":
            write_json(run_dir / "preflight.json", {
                "server": args.server,
                "missing_node_types": preflight["missing_node_types"],
                "system": preflight["stats"].get("system", {}),
                "devices": preflight["stats"].get("devices", []),
            })
        if preflight["missing_node_types"]:
            raise RuntimeError("Missing node types: " + ", ".join(preflight["missing_node_types"]))
        validate_model_profiles(profiles, preflight["object_info"])

    rows: list[dict[str, Any]] = []
    case_index_by_id = {case.case_id: index for index, case in enumerate(CASES)}

    for profile in profiles:
        for case in cases:
            case_index = case_index_by_id[case.case_id]
            existing_outputs = [] if args.rerun_completed else find_existing_case_outputs(case.case_id, profile)
            if existing_outputs:
                row = metadata_for_case(
                    case,
                    profile=profile,
                    case_index=case_index,
                    length=args.length,
                    fps=args.fps,
                    seed=args.seed,
                    random_seeds=args.random_seeds,
                    enable_postprocess=enable_postprocess,
                    enable_frame_skip_preview=enable_frame_skip_preview,
                )
                row["ui_workflow"] = ""
                row["api_prompt"] = ""
                row["prompt_id"] = ""
                row["status"] = "skipped_existing"
                row["outputs"] = "; ".join(existing_outputs)
                rows.append(row)
                write_json(run_dir / "manifest.json", rows)
                write_manifest_csv(run_dir / "manifest.csv", rows)
                write_html_report(run_dir / "report.html", rows, submit=bool(args.submit), run_id=run_id)
                print(f"{combo_queue_case(profile, case.case_id)}: skipped_existing -> {row['outputs']}")
                continue

            variant, meta = apply_case(
                base_workflow,
                case,
                profile=profile,
                case_index=case_index,
                run_id=run_id,
                length=args.length,
                fps=args.fps,
                seed=args.seed,
                random_seeds=args.random_seeds,
                enable_postprocess=enable_postprocess,
                enable_frame_skip_preview=enable_frame_skip_preview,
            )
            profile_dir = variants_dir / profile.profile_id if profile else variants_dir
            api_profile_dir = api_dir / profile.profile_id if profile else api_dir
            variant_path = profile_dir / f"{case.case_id}.ui.json"
            if args.artifact_mode == "full":
                write_json(variant_path, variant)

            row = dict(meta)
            row["ui_workflow"] = str(variant_path.relative_to(ROOT)) if args.artifact_mode == "full" else ""
            row["api_prompt"] = ""
            row["prompt_id"] = ""
            row["status"] = "prepared"
            row["outputs"] = ""
            row_written = False

            api_prompt: dict[str, Any] | None = None
            if args.write_api or args.submit:
                api_prompt = ui_to_api_prompt(variant)
                api_path = api_profile_dir / f"{case.case_id}.api.json"
                if args.write_api or args.artifact_mode == "full":
                    write_json(api_path, api_prompt)
                    row["api_prompt"] = str(api_path.relative_to(ROOT))

            if args.submit:
                assert api_prompt is not None
                if not args.skip_free_memory:
                    print(f"{combo_queue_case(profile, case.case_id)}: freeing ComfyUI model/VRAM cache")
                    free_memory(args.server)
                prompt_id = submit_prompt(args.server, api_prompt, run_id, meta)
                row["prompt_id"] = prompt_id
                row["status"] = "submitted"
                rows.append(row)
                row_written = True
                write_json(run_dir / "manifest.json", rows)
                write_manifest_csv(run_dir / "manifest.csv", rows)
                write_html_report(run_dir / "report.html", rows, submit=bool(args.submit), run_id=run_id)
                print(f"{combo_queue_case(profile, case.case_id)}: submitted -> {prompt_id}")
                if not args.no_wait:
                    history = wait_for_history(args.server, prompt_id, args.timeout, args.poll)
                    status = history.get("status", {}).get("status_str", "completed")
                    row["status"] = str(status)
                    outputs = output_files_from_history(history)
                    row["outputs"] = "; ".join(outputs)
                    if args.artifact_mode == "full":
                        history_name = f"{combo_filename_stem(profile, case.case_id)}.{prompt_id}.json"
                        write_json(run_dir / "history" / history_name, history)
                    if not args.skip_free_memory:
                        print(f"{combo_queue_case(profile, case.case_id)}: freeing ComfyUI model/VRAM cache after completion")
                        free_memory(args.server)

            if not row_written:
                rows.append(row)
            write_json(run_dir / "manifest.json", rows)
            write_manifest_csv(run_dir / "manifest.csv", rows)
            write_html_report(run_dir / "report.html", rows, submit=bool(args.submit), run_id=run_id)
            print(f"{combo_queue_case(profile, case.case_id)}: {row['status']} -> {row['ui_workflow']}")

    write_json(run_dir / "manifest.json", rows)
    write_manifest_csv(run_dir / "manifest.csv", rows)
    write_markdown_report(run_dir / "README.md", rows, submit=bool(args.submit))
    write_html_report(run_dir / "report.html", rows, submit=bool(args.submit), run_id=run_id)
    print(f"Run directory: {run_dir}")
    print(f"HTML report: {run_dir / 'report.html'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
