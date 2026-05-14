"""Comfy batch submitter."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.common.io import read_json, write_json
from pipeline.comfy.client import ComfyClient, ServerUnreachable
from pipeline.comfy.template_patcher import (
    TemplatePatchError,
    infer_comfy_input_dir,
    load_mapping,
    patch_workflow_template,
)
from pipeline.comfy.workflow_router import TemplateMissing, WorkflowRouter


@dataclass
class SubmitterConfig:
    poll_interval_seconds: float = 3.0
    history_poll_attempts: int = 1
    max_retries: int = 1
    dry_run: bool = False
    comfy_input_dir: Path | None = None
    output_prefix_root: str = "manga_anime_pipeline"


def submit_batch(
    shot_manifest: dict[str, Any],
    output_dir: Path,
    client: ComfyClient,
    router: WorkflowRouter,
    submitter_config: SubmitterConfig,
    agent_id: str = "manga-anime-pipeline",
) -> dict[str, Any]:
    tasks: list[dict[str, Any]] = []
    errors: list[str] = []
    template_missing_routes: set[str] = set()
    submitted = 0
    finished = 0
    failed = 0
    skipped = 0
    if submitter_config.comfy_input_dir is None:
        submitter_config.comfy_input_dir = infer_comfy_input_dir(router.project_root)
    for shot in shot_manifest.get("shots", []) or []:
        record = _process_shot(shot, shot_manifest, output_dir, client, router, submitter_config, agent_id)
        tasks.append(record)
        if record["status"] == "skipped":
            skipped += 1
        elif record["status"] == "finished":
            finished += 1
            submitted += 1
        elif record["status"] == "failed":
            failed += 1
            submitted += 1
            if record.get("error_message"):
                errors.append(f"{record['shot_id']}: {record['error_message']}")
        elif record["status"] == "submitted":
            submitted += 1
        elif record["status"] == "template_missing":
            template_missing_routes.add(record.get("workflow_route", ""))
            errors.append(f"{record['shot_id']}: template missing ({record.get('workflow_template')})")
        elif record["status"] == "blocked":
            errors.append(f"{record['shot_id']}: {record.get('error_message')}")
    summary = {
        "shot_count": len(shot_manifest.get("shots", []) or []),
        "submitted_count": submitted,
        "finished_count": finished,
        "failed_count": failed,
        "skipped_count": skipped,
        "template_missing_routes": sorted(template_missing_routes),
        "errors": errors,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "comfy_tasks.json"
    write_json(output_path, {"summary": summary, "tasks": tasks})
    return {"summary": summary, "tasks": tasks, "output_path": output_path}


def _process_shot(
    shot: dict[str, Any],
    shot_manifest: dict[str, Any],
    output_dir: Path,
    client: ComfyClient,
    router: WorkflowRouter,
    submitter_config: SubmitterConfig,
    agent_id: str,
) -> dict[str, Any]:
    shot_id = str(shot.get("shot_id", "shot_unknown"))
    workflow_route = str(shot.get("workflow_route", ""))
    record: dict[str, Any] = {
        "shot_id": shot_id,
        "workflow_route": workflow_route,
        "workflow_template": None,
        "prompt_id": None,
        "status": "pending",
        "submitted_at": None,
        "finished_at": None,
        "output_files": [],
        "error_message": None,
        "retry_count": 0,
        "seed": None,
        "output_prefix": None,
        "input_image": None,
        "input_assets": {},
        "patched_fields": [],
        "patched_workflow_path": None,
    }
    if workflow_route == "skip":
        record["status"] = "skipped"
        return record
    try:
        template_path = router.resolve(workflow_route)
    except TemplateMissing as error:
        record["status"] = "template_missing"
        record["error_message"] = str(error)
        return record
    if template_path is None:
        record["status"] = "skipped"
        return record
    record["workflow_template"] = str(template_path)
    try:
        workflow_payload = read_json(template_path)
    except Exception as error:
        record["status"] = "failed"
        record["error_message"] = f"failed to load workflow template: {error}"
        return record
    try:
        mapping_path = router.resolve_mapping(workflow_route, template_path)
        mapping = load_mapping(mapping_path)
        patch_result = patch_workflow_template(
            workflow_payload,
            shot,
            shot_manifest,
            project_root=router.project_root,
            mapping=mapping,
            comfy_input_dir=submitter_config.comfy_input_dir,
            output_prefix_root=submitter_config.output_prefix_root,
        )
        workflow_payload = patch_result.workflow
        record["seed"] = patch_result.seed
        record["output_prefix"] = patch_result.output_prefix
        record["patched_fields"] = patch_result.patched_fields
        if patch_result.input_image:
            record["input_image"] = {
                "image_value": patch_result.input_image.image_value,
                "source_path": patch_result.input_image.source_path,
                "crop_box": patch_result.input_image.crop_box,
                "output_path": patch_result.input_image.output_path,
            }
        if patch_result.input_assets:
            record["input_assets"] = {
                field: {
                    "asset_value": asset.asset_value,
                    "source_path": asset.source_path,
                    "output_path": asset.output_path,
                    "media_type": asset.media_type,
                    "crop_box": asset.crop_box,
                }
                for field, asset in patch_result.input_assets.items()
            }
        patched_path = output_dir / "patched_workflows" / f"{_safe_path_part(shot_id)}.json"
        write_json(patched_path, workflow_payload)
        record["patched_workflow_path"] = str(patched_path)
    except (TemplateMissing, TemplatePatchError, Exception) as error:
        record["status"] = "failed"
        record["error_message"] = f"failed to patch workflow template: {error}"
        return record
    client_id = f"agent:{agent_id}|workflow:{workflow_route}|run:{uuid.uuid4().hex[:8]}"
    note_parts = [
        f"shot_id={shot_id}",
        f"seed={record['seed']}",
        f"output_prefix={record['output_prefix']}",
    ]
    if record["input_image"]:
        note_parts.append(f"input_image={record['input_image']['image_value']}")
    if record["input_assets"]:
        asset_notes = [f"{field}={asset['asset_value']}" for field, asset in record["input_assets"].items()]
        note_parts.append("input_assets=" + ",".join(asset_notes))
    if record["patched_fields"]:
        note_parts.append("patched_fields=" + ",".join(record["patched_fields"]))
    payload = {
        "prompt": workflow_payload,
        "client_id": client_id,
        "extra_data": {
            "agent": agent_id,
            "workflow_name": workflow_route,
            "source": "manga-anime-pipeline",
            "shot_id": shot_id,
            "workflow_route": workflow_route,
            "seed": record["seed"],
            "output_prefix": record["output_prefix"],
            "notes": "; ".join(note_parts),
        },
    }
    if submitter_config.dry_run:
        record["status"] = "skipped"
        record["error_message"] = "dry_run=true, submission skipped"
        return record
    for attempt in range(submitter_config.max_retries + 1):
        record["retry_count"] = attempt
        try:
            response = client.submit_prompt(payload)
        except ServerUnreachable as error:
            record["status"] = "blocked"
            record["error_message"] = f"server unreachable: {error}"
            return record
        except Exception as error:
            record["status"] = "failed"
            record["error_message"] = f"submit failed (attempt {attempt}): {error}"
            continue
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            record["status"] = "failed"
            record["error_message"] = f"submit response missing prompt_id: {response}"
            continue
        record["prompt_id"] = prompt_id
        record["status"] = "submitted"
        record["submitted_at"] = _now_iso()
        _poll_history(client, record, submitter_config)
        return record
    return record


def _poll_history(client: ComfyClient, record: dict[str, Any], submitter_config: SubmitterConfig) -> None:
    """Poll history until the prompt appears or configured attempts run out."""
    attempts = max(1, int(submitter_config.history_poll_attempts))
    for attempt in range(attempts):
        if attempt > 0:
            time.sleep(max(0.0, submitter_config.poll_interval_seconds))
        try:
            history = client.get_history(record["prompt_id"])
        except Exception:
            continue
        entry = history.get(record["prompt_id"]) if isinstance(history, dict) else None
        if not entry:
            continue
        status_info = entry.get("status") if isinstance(entry.get("status"), dict) else {}
        status_str = str(status_info.get("status_str", "")).lower()
        if status_str in {"error", "failed"}:
            record["finished_at"] = _now_iso()
            record["status"] = "failed"
            record["error_message"] = _history_error_message(status_info)
            return
        record["finished_at"] = _now_iso()
        record["status"] = "finished"
        record["output_files"] = _history_output_files(entry)
        return


def _history_output_files(entry: dict[str, Any]) -> list[str]:
    outputs = entry.get("outputs") or {}
    files: list[str] = []
    for node_output in outputs.values():
        for image in node_output.get("images", []) or []:
            filename = image.get("filename", "")
            if filename:
                files.append(filename)
        for video in node_output.get("videos", []) or []:
            filename = video.get("filename", "")
            if filename:
                files.append(filename)
        for audio in node_output.get("audio", []) or []:
            filename = audio.get("filename", "")
            if filename:
                files.append(filename)
    return files


def _history_error_message(status_info: dict[str, Any]) -> str:
    messages = status_info.get("messages") or []
    if messages:
        return str(messages[-1])
    return str(status_info or "ComfyUI history reported failure")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"
