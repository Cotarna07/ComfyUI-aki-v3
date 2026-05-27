# -*- coding: utf-8 -*-
"""Generate product hero candidates without repainting the merchandise pixels."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import requests


ROOT = Path(r"D:\ComfyUI-aki-v3")
COMFY_URL = "http://127.0.0.1:8188"
INPUT_ROOT = ROOT / "ComfyUI" / "input"
WORKFLOW_PATH = (
    ROOT / "agent-skills" / "comfyui" / "workflows" / "api" / "product_locked_background_sdxl.json"
)
RUNTIME_ROOT = ROOT / "agent-skills" / "comfyui" / "runtime" / "product_image_locked_20260527"
OUTPUT_PREFIX = "agent_runs/aliexpress_locked_20260527"
STAGED_OUTPUT_PREFIX = "agent_runs/aliexpress_locked_staged_20260527"
STAGED_NEGATIVE_PROMPT = (
    "product, toy, car, vehicle, figure, minifigure, model, box, package, text, logo, watermark, "
    "label, sign, people, duplicate subject, spare wheel, accessory, building blocks, clutter, "
    "low quality, warped geometry, blown highlights"
)


@dataclass(frozen=True)
class Job:
    product_id: str
    source: Path
    width: int
    height: int
    seed: int
    background_prompt: str
    staged_background_prompt: str
    identity_notes: str


JOBS = (
    Job(
        product_id="1005010410824249",
        source=Path(r"Y:\tiktok_ins_crawl\aliexpress\images\1005010410824249\05.jpg"),
        width=768,
        height=1024,
        seed=2026052701,
        background_prompt=(
            "completely empty commercial studio cyclorama, seamless pale gray matte floor and wall, "
            "soft emerald gradient rim light on the backdrop and gentle warm softbox light from upper left, "
            "flat unobstructed floor across the full frame, clean luxury product-advertising lighting, "
            "blank background plate only, absolutely no props or objects"
        ),
        staged_background_prompt=(
            "cinematic product photography set with no merchandise present, moss green and charcoal studio backdrop, "
            "a single broad low matte slate display platform across the lower third, large enough for a tall centerpiece "
            "and two tiny items, gentle emerald rim light, warm key light from upper left, realistic contact surface, "
            "clean empty set, no toys, no characters, no blocks, no text"
        ),
        identity_notes=(
            "green brick-built Creeper statue; four splayed feet; black pixel face; "
            "one pink pig and one red-white TNT accessory must remain visible"
        ),
    ),
    Job(
        product_id="1005010739958948",
        source=Path(r"Y:\tiktok_ins_crawl\aliexpress\images\1005010739958948\02.jpg"),
        width=1024,
        height=1024,
        seed=2026052702,
        background_prompt=(
            "completely empty automotive studio cyclorama, smooth charcoal matte floor and dark gray gradient wall, "
            "thin warm red rim light and broad softbox reflections, subtle floor sheen, clean premium advertising set, "
            "blank background plate only, absolutely no props or objects"
        ),
        staged_background_prompt=(
            "premium automotive advertising studio with no vehicle present, dark charcoal walls and red linear accent "
            "lights, one broad low black presentation platform centered in the lower half, glossy top surface and "
            "subtle reflections, dramatic overhead softboxes, empty scene, no car, no wheels, no logos, no text"
        ),
        identity_notes=(
            "red brick-built Ferrari SF90 XX Stradale; four wheels; black windshield; "
            "large rear wing; full car silhouette must remain visible"
        ),
    ),
    Job(
        product_id="1005007109462323",
        source=Path(r"Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323\04.jpg"),
        width=1024,
        height=1024,
        seed=2026052703,
        background_prompt=(
            "completely empty bright studio cyclorama, clean light gray seamless wall and matte floor, "
            "very soft cool blue edge light with a neutral overhead softbox, subtle floor sheen, "
            "commercial catalog background plate only, absolutely no props or objects"
        ),
        staged_background_prompt=(
            "bright clean commercial photography studio with no merchandise present, cool pale blue seamless backdrop, "
            "one wide low light-gray display riser across the lower half with a level top and soft grounded shadows, "
            "blue rim illumination and neutral softboxes, empty scene, no car, no figure, no badge, no text"
        ),
        identity_notes=(
            "blue-white brick police car rear three-quarter view with four wheels and roof blue light bar; "
            "exactly one police minifigure holding a light must remain at right"
        ),
    ),
    Job(
        product_id="1005008273906722",
        source=Path(r"Y:\tiktok_ins_crawl\aliexpress\images\1005008273906722\02.jpg"),
        width=1024,
        height=1024,
        seed=2026052704,
        background_prompt=(
            "completely empty warm beige studio cyclorama, smooth matte floor and soft gradient wall, "
            "gentle amber side light and restrained golden atmospheric glow, clean premium display lighting, "
            "blank background plate only, absolutely no props or objects"
        ),
        staged_background_prompt=(
            "warm cinematic museum-style product photography set with no merchandise present, softly lit sandstone "
            "backdrop, one broad empty dark-wood tabletop display surface occupying the lower half, gentle amber "
            "side light and candlelike glow only in the background, empty surface, no figures, no bottles, no text"
        ),
        identity_notes=(
            "tan-brown open potions classroom diorama; three black-robed minifigures; "
            "black cauldron, potion bottles and wands visible in source must remain"
        ),
    ),
    Job(
        product_id="1005009067934624",
        source=Path(r"Y:\tiktok_ins_crawl\aliexpress\images\1005009067934624\06.jpg"),
        width=1024,
        height=1024,
        seed=2026052705,
        background_prompt=(
            "top-down empty matte graphite pit-lane display surface filling the entire frame, no horizon and no wall, "
            "subtle wet sheen and very faint diagonal red lane accent beneath the product area, soft overhead "
            "strip-light reflections, clean flat support plane only, absolutely no objects or silhouettes"
        ),
        staged_background_prompt=(
            "empty abstract red and graphite studio cyclorama with no merchandise present, a broad level matte "
            "display surface spanning the lower half, soft overhead light and a restrained red edge glow, "
            "clean empty scene, no vehicles, no wheels, no figures, no logos and no text"
        ),
        identity_notes=(
            "red-black brick-built Ferrari SF-24 Formula 1 car; four tires, front wing, cockpit and rear wing; "
            "red helmet driver seated in the cockpit; whole vehicle must remain in frame"
        ),
    ),
)


def service_ok() -> dict:
    response = requests.get(f"{COMFY_URL}/system_stats", timeout=20)
    response.raise_for_status()
    return response.json()


def load_template() -> dict:
    return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))


def stage_input(job: Job) -> str:
    relative = Path("agent_aliexpress_locked") / "20260527" / job.product_id / job.source.name
    target = INPUT_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(job.source, target)
    return relative.as_posix()


def build_prompt(template: dict, job: Job, input_name: str, style: str) -> dict:
    workflow = copy.deepcopy(template)
    workflow["1"]["inputs"]["image"] = input_name
    workflow["2"]["inputs"]["width"] = job.width
    workflow["2"]["inputs"]["height"] = job.height
    workflow["5"]["inputs"]["text"] = (
        job.staged_background_prompt if style == "staged" else job.background_prompt
    )
    if style == "staged":
        workflow["6"]["inputs"]["text"] = STAGED_NEGATIVE_PROMPT
    workflow["7"]["inputs"]["width"] = job.width
    workflow["7"]["inputs"]["height"] = job.height
    workflow["8"]["inputs"]["seed"] = job.seed
    workflow["11"]["inputs"]["width"] = job.width
    workflow["11"]["inputs"]["height"] = job.height
    output_prefix = STAGED_OUTPUT_PREFIX if style == "staged" else OUTPUT_PREFIX
    base = f"{output_prefix}/{job.product_id}"
    workflow["15"]["inputs"]["filename_prefix"] = f"{base}/locked_factual"
    workflow["16"]["inputs"]["filename_prefix"] = f"{base}/background"
    workflow["17"]["inputs"]["filename_prefix"] = f"{base}/foreground_audit"
    return workflow


def wait_for_result(prompt_id: str, timeout_seconds: int = 900) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=30)
        response.raise_for_status()
        history = response.json()
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(2)
    raise TimeoutError(f"ComfyUI run timed out: {prompt_id}")


def run_job(template: dict, job: Job, style: str) -> dict:
    input_name = stage_input(job)
    workflow = build_prompt(template, job, input_name, style)
    run_id = uuid.uuid4().hex[:8]
    client_id = f"agent:codex|workflow:product_locked_background_sdxl|run:{run_id}"
    notes = (
        f"factual_product; product={job.product_id}; original foreground pixel lock via RMBG mask; "
        f"background_style={style}; "
        f"input={job.source.name}; background_model=juggernautXL_v9Rdphoto2Lightning; "
        f"background_seed={job.seed}; size={job.width}x{job.height}; "
        f"steps=8; cfg=2.0; sampler=dpmpp_sde; scheduler=karras; "
        f"shadow=mask_blur_35_sigma_14_offset_y12_opacity_0.35; identity={job.identity_notes}"
    )
    payload = {
        "prompt": workflow,
        "client_id": client_id,
        "extra_data": {
            "agent": "codex",
            "workflow_name": "product_locked_background_sdxl",
            "source": str(job.source),
            "notes": notes,
        },
    }
    response = requests.post(f"{COMFY_URL}/prompt", json=payload, timeout=60)
    response.raise_for_status()
    prompt_id = response.json()["prompt_id"]
    print(f"{job.product_id}: submitted {prompt_id}")
    history = wait_for_result(prompt_id)
    status = history.get("status", {})
    if not status.get("completed", False):
        errors = [
            message[1].get("exception_message", "unknown ComfyUI execution failure")
            for message in status.get("messages", [])
            if message[0] == "execution_error"
        ]
        raise RuntimeError(f"{job.product_id} failed: {'; '.join(errors) or status}")
    outputs = history.get("outputs", {})
    return {
        "product_id": job.product_id,
        "source": str(job.source),
        "input_name": input_name,
        "prompt_id": prompt_id,
        "client_id": client_id,
        "notes": notes,
        "status": status,
        "outputs": outputs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product", action="append", help="Only run one or more product IDs.")
    parser.add_argument(
        "--style",
        choices=("studio", "staged"),
        default="studio",
        help="Use a plain studio plate or an empty supporting display stage.",
    )
    args = parser.parse_args()

    stats = service_ok()
    device = stats.get("devices", [{}])[0].get("name", "unknown")
    print(f"ComfyUI connected: {device}")
    selected = [job for job in JOBS if not args.product or job.product_id in args.product]
    if not selected:
        raise SystemExit("No product matches --product.")

    template = load_template()
    results = []
    for job in selected:
        results.append(run_job(template, job, args.style))

    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    summary_path = RUNTIME_ROOT / f"locked_runs_{datetime.now():%Y%m%d_%H%M%S}.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
