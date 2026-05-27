# -*- coding: utf-8 -*-
"""Render a VLM-approved creative campaign brief through Flux.1 Kontext.

Factual delivery is deliberately excluded: Flux Kontext repaints product
pixels, so factual images must use the separate locked-foreground workflow.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(r"D:\ComfyUI-aki-v3")
COMFY_URL = "http://127.0.0.1:8188"
INPUT_ROOT = ROOT / "ComfyUI" / "input"
WORKFLOW_PATH = (
    ROOT / "agent-skills" / "comfyui" / "workflows" / "api" / "kontext_product_edit.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a creative shot from a director manifest.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shot-id", required=True)
    parser.add_argument("--seed", type=int, default=2026052715)
    parser.add_argument("--steps", type=int, default=28)
    parser.add_argument("--guidance", type=float, default=2.8)
    parser.add_argument(
        "--bright-clean",
        action="store_true",
        help="Add close bright hero framing and remove non-product catalog graphics.",
    )
    return parser.parse_args()


def find_shot(manifest: dict[str, Any], shot_id: str) -> dict[str, Any]:
    for shot in manifest["plan"]["shot_briefs"]:
        if shot.get("id") == shot_id:
            return shot
    raise ValueError(f"Unknown shot id: {shot_id}")


def source_for_shot(manifest: dict[str, Any], shot: dict[str, Any]) -> Path:
    source_by_name = {Path(path).name: Path(path) for path in manifest["source_images"]}
    for source_name in shot.get("base_source_files", []):
        source = source_by_name.get(source_name)
        if source and source.is_file():
            return source
    raise FileNotFoundError(f"No available source image for shot {shot.get('id')}")


def stage_source(source: Path, product_id: str) -> str:
    relative = (
        Path("agent_aliexpress_campaign")
        / f"{datetime.now():%Y%m%d}"
        / product_id
        / source.name
    )
    target = INPUT_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return relative.as_posix()


def build_prompt(shot: dict[str, Any], bright_clean: bool) -> str:
    prompt = (
        shot["generation_prompt_en"]
        + " Preserve the evidenced source product configuration exactly: keep all listed "
        "do-not-change product features, character count and product surface markings readable. "
        "No additional vehicle, figure, packaging, generated title, logo overlay or watermark. "
        "creative_campaign; not for factual SKU verification."
    )
    if bright_clean:
        prompt += (
            " Remove only non-product catalog graphics from the source, including header logos, "
            "item-number header and instructional arrows. Frame a bright close premium hero shot "
            "with the product occupying about 78 percent of the image, strong soft frontal fill, "
            "readable toy-brick surfaces and restrained cinematic background depth."
        )
    return prompt


def wait_for_history(prompt_id: str, timeout_seconds: int = 1200) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        history = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=30).json()
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(3)
    raise TimeoutError(prompt_id)


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validation = manifest.get("plan_validation", {})
    if not validation.get("passed"):
        raise RuntimeError(f"Director plan failed deterministic gate: {validation.get('errors')}")
    shot = find_shot(manifest, args.shot_id)
    if shot.get("track") != "creative_campaign":
        raise RuntimeError(
            "This renderer is limited to creative_campaign; use locked foreground for factual_product."
        )
    source = source_for_shot(manifest, shot)
    input_name = stage_source(source, manifest["product_id"])
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    prompt = build_prompt(shot, args.bright_clean)
    workflow["1"]["inputs"]["image"] = input_name
    workflow["5"]["inputs"]["text"] = prompt
    workflow["7"]["inputs"]["guidance"] = args.guidance
    workflow["9"]["inputs"]["seed"] = args.seed
    workflow["9"]["inputs"]["steps"] = args.steps
    workflow["11"]["inputs"]["width"] = 1024
    workflow["11"]["inputs"]["height"] = 1024
    output_prefix = (
        f"agent_runs/vlm_directed_campaign_{datetime.now():%Y%m%d}/"
        f"{manifest['product_id']}/{shot['id']}"
    )
    if args.bright_clean:
        output_prefix += "_bright_clean"
    workflow["15"]["inputs"]["filename_prefix"] = output_prefix

    requests.post(
        f"{COMFY_URL}/free",
        json={"unload_models": True, "free_memory": True},
        timeout=30,
    ).raise_for_status()
    run_id = uuid.uuid4().hex[:8]
    client_id = f"agent:codex|workflow:vlm_directed_kontext_campaign|run:{run_id}"
    notes = (
        f"creative_campaign; product={manifest['product_id']}; shot={shot['id']}; "
        f"source={source.name}; director_model={manifest['model']}; "
        f"generator=flux1-dev-kontext_fp8_scaled; seed={args.seed}; steps={args.steps}; "
        f"guidance={args.guidance}; sampler=euler; scheduler=simple; size=1024x1024; "
        "workflow_latent=EmptySD3LatentImage; not_for_factual_sku_verification"
    )
    result = requests.post(
        f"{COMFY_URL}/prompt",
        json={
            "prompt": workflow,
            "client_id": client_id,
            "extra_data": {
                "agent": "codex",
                "workflow_name": "vlm_directed_kontext_campaign",
                "source": str(source),
                "notes": notes,
            },
        },
        timeout=60,
    )
    result.raise_for_status()
    prompt_id = result.json()["prompt_id"]
    print(f"Submitted: {prompt_id}")
    history = wait_for_history(prompt_id)
    record = {
        "prompt_id": prompt_id,
        "client_id": client_id,
        "shot": shot,
        "source": str(source),
        "input_name": input_name,
        "prompt": prompt,
        "notes": notes,
        "history": history,
    }
    records_dir = args.manifest.parent / "renders"
    records_dir.mkdir(parents=True, exist_ok=True)
    record_path = records_dir / f"{shot['id']}_{run_id}.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Record: {record_path}")
    print(json.dumps(history.get("outputs", {}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
