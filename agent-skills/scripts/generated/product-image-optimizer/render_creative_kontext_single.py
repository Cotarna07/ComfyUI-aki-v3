# -*- coding: utf-8 -*-
"""Render one clearly labelled creative product campaign image with Flux Kontext."""

from __future__ import annotations

import argparse
import json
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests


ROOT = Path(r"D:\ComfyUI-aki-v3")
COMFY_URL = "http://127.0.0.1:8188"
INPUT_ROOT = ROOT / "ComfyUI" / "input"
WORKFLOW_PATH = (
    ROOT / "agent-skills" / "comfyui" / "workflows" / "api" / "kontext_product_edit.json"
)
RUNTIME_ROOT = ROOT / "agent-skills" / "comfyui" / "runtime" / "creative_kontext_runs"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--shot-id", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--seed", type=int, default=2026052717)
    parser.add_argument("--steps", type=int, default=28)
    parser.add_argument("--guidance", type=float, default=2.8)
    return parser.parse_args()


def wait_for_result(prompt_id: str, timeout_seconds: int = 1200) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=30)
        response.raise_for_status()
        history = response.json()
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(3)
    raise TimeoutError(prompt_id)


def main() -> int:
    args = parse_args()
    if not args.source.is_file():
        raise FileNotFoundError(args.source)
    relative = (
        Path("agent_aliexpress_campaign")
        / f"{datetime.now():%Y%m%d}"
        / args.product_id
        / args.source.name
    )
    input_path = INPUT_ROOT / relative
    input_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.source, input_path)
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    workflow["1"]["inputs"]["image"] = relative.as_posix()
    workflow["5"]["inputs"]["text"] = args.prompt
    workflow["7"]["inputs"]["guidance"] = args.guidance
    workflow["9"]["inputs"]["seed"] = args.seed
    workflow["9"]["inputs"]["steps"] = args.steps
    workflow["11"]["inputs"]["width"] = 1024
    workflow["11"]["inputs"]["height"] = 1024
    output_prefix = (
        f"agent_runs/creative_kontext_{datetime.now():%Y%m%d}/"
        f"{args.product_id}/{args.shot_id}"
    )
    workflow["15"]["inputs"]["filename_prefix"] = output_prefix

    requests.post(
        f"{COMFY_URL}/free",
        json={"unload_models": True, "free_memory": True},
        timeout=30,
    ).raise_for_status()
    run_id = uuid.uuid4().hex[:8]
    notes = (
        f"creative_campaign; not_for_factual_sku_verification; product={args.product_id}; "
        f"shot={args.shot_id}; source={args.source.name}; generator=flux1-dev-kontext_fp8_scaled; "
        f"seed={args.seed}; steps={args.steps}; guidance={args.guidance}; sampler=euler; "
        "scheduler=simple; size=1024x1024; workflow_latent=EmptySD3LatentImage"
    )
    response = requests.post(
        f"{COMFY_URL}/prompt",
        json={
            "prompt": workflow,
            "client_id": f"agent:codex|workflow:creative_kontext_single|run:{run_id}",
            "extra_data": {
                "agent": "codex",
                "workflow_name": "creative_kontext_single",
                "source": str(args.source),
                "notes": notes,
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    prompt_id = response.json()["prompt_id"]
    history = wait_for_result(prompt_id)
    record = {
        "prompt_id": prompt_id,
        "source": str(args.source),
        "prompt": args.prompt,
        "notes": notes,
        "history": history,
    }
    record_dir = RUNTIME_ROOT / args.product_id
    record_dir.mkdir(parents=True, exist_ok=True)
    record_path = record_dir / f"{args.shot_id}_{run_id}.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Prompt: {prompt_id}")
    print(f"Record: {record_path}")
    print(json.dumps(history.get("outputs", {}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
