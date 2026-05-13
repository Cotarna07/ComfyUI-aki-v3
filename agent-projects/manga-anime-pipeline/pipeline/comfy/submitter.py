"""Comfy batch submitter."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.common.io import read_json, write_json
from pipeline.comfy.client import ComfyClient, ServerUnreachable
from pipeline.comfy.workflow_router import TemplateMissing, WorkflowRouter


@dataclass
class SubmitterConfig:
    poll_interval_seconds: float = 3.0
    max_retries: int = 1
    dry_run: bool = False


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
    for shot in shot_manifest.get("shots", []) or []:
        record = _process_shot(shot, client, router, submitter_config, agent_id)
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
    client_id = f"agent:{agent_id}|workflow:{workflow_route}|run:{uuid.uuid4().hex[:8]}"
    payload = {
        "prompt": workflow_payload,
        "client_id": client_id,
        "extra_data": {
            "agent": agent_id,
            "workflow_name": workflow_route,
            "source": "manga-anime-pipeline",
            "notes": f"shot_id={shot_id}",
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
    """Polls history once to capture completion if it already happened."""
    try:
        history = client.get_history(record["prompt_id"])
    except Exception:
        return
    entry = history.get(record["prompt_id"]) if isinstance(history, dict) else None
    if not entry:
        return
    record["finished_at"] = _now_iso()
    record["status"] = "finished"
    outputs = entry.get("outputs") or {}
    files: list[str] = []
    for node_output in outputs.values():
        for image in node_output.get("images", []) or []:
            files.append(image.get("filename", ""))
    record["output_files"] = files


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
