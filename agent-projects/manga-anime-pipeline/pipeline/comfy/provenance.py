"""ComfyUI output provenance helpers.

Every reviewed image/video should carry the workflow that made it.  The
functions here write a small sidecar next to each output so a future agent can
inspect one file and recover the prompt, seed, sampler, model, VAE and full
API graph without hunting through a run-level manifest.
"""

from __future__ import annotations

import copy
import hashlib
import time
from pathlib import Path
from typing import Any

from pipeline.common.io import as_project_path, write_json


MODEL_INPUT_KEYS = {
    "ckpt_name": "checkpoint",
    "unet_name": "diffusion_model",
    "vae_name": "vae",
    "lora_name": "lora",
    "clip_name": "text_encoder",
    "clip_name1": "text_encoder",
    "clip_name2": "text_encoder",
    "clip_name3": "text_encoder",
    "clip_vision_name": "clip_vision",
    "control_net_name": "controlnet",
    "model_name": "model",
    "upscale_model": "upscale_model",
}
SAMPLER_INPUT_KEYS = {
    "seed",
    "noise_seed",
    "steps",
    "cfg",
    "sampler_name",
    "scheduler",
    "denoise",
    "start_at_step",
    "end_at_step",
    "add_noise",
    "return_with_leftover_noise",
}
DIMENSION_INPUT_KEYS = {"width", "height", "length", "fps", "batch_size"}
MEDIA_INPUT_KEYS = {"image", "video", "audio", "start_image", "end_image", "mask", "control_image"}


def write_output_provenance(
    output_path: Path,
    *,
    project_root: Path,
    workflow: dict[str, Any],
    workflow_name: str,
    prompt_id: str = "",
    client_id: str = "",
    extra_data: dict[str, Any] | None = None,
    task_context: dict[str, Any] | None = None,
    source_output: dict[str, Any] | None = None,
    history_status: dict[str, Any] | None = None,
    sidecar_path: Path | None = None,
    output_label: str | None = None,
) -> Path:
    """Write ``<output filename>.provenance.json`` and return its path."""

    output_path = Path(output_path)
    target = sidecar_path or output_path.with_name(output_path.name + ".provenance.json")
    workflow_copy = copy.deepcopy(workflow)
    provenance = {
        "schema_version": 1,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "output_file": output_label or as_project_path(project_root, output_path),
        "workflow_name": workflow_name,
        "prompt_id": prompt_id,
        "client_id": client_id,
        "extra_data": copy.deepcopy(extra_data or {}),
        "task_context": copy.deepcopy(task_context or {}),
        "source_output": copy.deepcopy(source_output or {}),
        "history_status": copy.deepcopy(history_status or {}),
        "workflow_digest_sha256": workflow_digest(workflow_copy),
        "extracted_parameters": extract_workflow_parameters(workflow_copy),
        "workflow_api": workflow_copy,
    }
    write_json(target, provenance)
    return target


def write_output_provenance_files(
    output_paths: list[Path],
    *,
    project_root: Path,
    workflow: dict[str, Any],
    workflow_name: str,
    prompt_id: str = "",
    client_id: str = "",
    extra_data: dict[str, Any] | None = None,
    task_context: dict[str, Any] | None = None,
    source_outputs: list[dict[str, Any]] | None = None,
    history_status: dict[str, Any] | None = None,
) -> list[Path]:
    """Write one provenance sidecar for each output path."""

    sidecars: list[Path] = []
    for index, output_path in enumerate(output_paths):
        source_output = (source_outputs or [{}])[index] if index < len(source_outputs or []) else {}
        sidecars.append(
            write_output_provenance(
                output_path,
                project_root=project_root,
                workflow=workflow,
                workflow_name=workflow_name,
                prompt_id=prompt_id,
                client_id=client_id,
                extra_data=extra_data,
                task_context=task_context,
                source_output=source_output,
                history_status=history_status,
            )
        )
    return sidecars


def extract_workflow_parameters(workflow: dict[str, Any]) -> dict[str, Any]:
    """Extract review-friendly parameters while preserving the full graph elsewhere."""

    nodes: dict[str, dict[str, Any]] = {}
    models: list[dict[str, Any]] = []
    samplers: list[dict[str, Any]] = []
    vae: list[dict[str, Any]] = []
    dimensions: list[dict[str, Any]] = []
    prompts: list[dict[str, Any]] = []
    media_inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []

    for node_id, node in sorted(workflow.items(), key=lambda item: str(item[0])):
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type") or "")
        inputs = copy.deepcopy(node.get("inputs") or {})
        nodes[str(node_id)] = {"class_type": class_type, "inputs": inputs}

        for key, role in MODEL_INPUT_KEYS.items():
            if key in inputs:
                models.append({"node_id": str(node_id), "class_type": class_type, "role": role, "field": key, "name": inputs[key]})
        if "VAE" in class_type or "vae" in inputs or "vae_name" in inputs:
            vae.append({"node_id": str(node_id), "class_type": class_type, "inputs": _pick(inputs, {"vae", "vae_name", "samples"})})
        if _is_sampler_node(class_type, inputs):
            samplers.append({"node_id": str(node_id), "class_type": class_type, "inputs": _pick(inputs, SAMPLER_INPUT_KEYS)})
        if any(key in inputs for key in DIMENSION_INPUT_KEYS):
            dimensions.append({"node_id": str(node_id), "class_type": class_type, "inputs": _pick(inputs, DIMENSION_INPUT_KEYS)})
        if _is_prompt_node(class_type, inputs):
            prompts.append({"node_id": str(node_id), "class_type": class_type, "inputs": _pick(inputs, {"text", "prompt"})})
        if any(key in inputs for key in MEDIA_INPUT_KEYS) or class_type.startswith("Load"):
            media_inputs.append({"node_id": str(node_id), "class_type": class_type, "inputs": _pick(inputs, MEDIA_INPUT_KEYS)})
        if class_type.startswith("Save") or "filename_prefix" in inputs:
            outputs.append(
                {
                    "node_id": str(node_id),
                    "class_type": class_type,
                    "inputs": _pick(inputs, {"filename_prefix", "format", "codec", "images", "video", "audio"}),
                }
            )

    return {
        "models": models,
        "samplers": samplers,
        "vae": vae,
        "dimensions": dimensions,
        "prompts": prompts,
        "media_inputs": media_inputs,
        "outputs": outputs,
        "nodes": nodes,
    }


def workflow_digest(workflow: dict[str, Any]) -> str:
    import json

    payload = json.dumps(workflow, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_sampler_node(class_type: str, inputs: dict[str, Any]) -> bool:
    return "Sampler" in class_type or any(key in inputs for key in SAMPLER_INPUT_KEYS)


def _is_prompt_node(class_type: str, inputs: dict[str, Any]) -> bool:
    return "TextEncode" in class_type or "text" in inputs or "prompt" in inputs


def _pick(inputs: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    return {key: copy.deepcopy(inputs[key]) for key in sorted(keys) if key in inputs}
