"""Stage 6 comfy submission acceptance evaluation."""

from __future__ import annotations

from typing import Any


def evaluate_comfy_acceptance(submission_result: dict[str, Any]) -> dict[str, Any]:
    summary = submission_result.get("summary", {}) or {}
    tasks = submission_result.get("tasks", []) or []
    errors: list[str] = []
    warnings: list[str] = []
    shot_count = int(summary.get("shot_count", 0))
    submitted = int(summary.get("submitted_count", 0))
    finished = int(summary.get("finished_count", 0))
    failed = int(summary.get("failed_count", 0))
    skipped = int(summary.get("skipped_count", 0))
    template_missing = summary.get("template_missing_routes") or []
    blocked = [task for task in tasks if task.get("status") == "blocked"]
    if blocked:
        return {
            "pipeline_status": "blocked",
            "next_stage_allowed": False,
            "comfy_quality": _comfy_quality(summary),
            "errors": [task.get("error_message", "comfy server unreachable") for task in blocked][:3] or ["comfy server unreachable"],
            "warnings": [],
        }
    if template_missing:
        errors.append("workflow templates missing for routes: " + ", ".join(template_missing))
    if shot_count == 0:
        errors.append("shot_manifest produced no shots")
    if shot_count > 0 and submitted == 0 and skipped < shot_count:
        errors.append("no shots submitted to ComfyUI")
    if failed > 0:
        errors.append(f"{failed} shots failed to submit/finish")
    if not finished and submitted > 0:
        warnings.append("no shots finished yet (only submitted); poll later")
    if errors:
        return {
            "pipeline_status": "fail",
            "next_stage_allowed": False,
            "comfy_quality": _comfy_quality(summary),
            "errors": errors,
            "warnings": warnings,
        }
    return {
        "pipeline_status": "pass" if not warnings else "warning",
        "next_stage_allowed": True,
        "comfy_quality": _comfy_quality(summary),
        "errors": errors,
        "warnings": warnings,
    }


def _comfy_quality(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "shot_count": summary.get("shot_count", 0),
        "submitted_count": summary.get("submitted_count", 0),
        "finished_count": summary.get("finished_count", 0),
        "failed_count": summary.get("failed_count", 0),
        "skipped_count": summary.get("skipped_count", 0),
        "template_missing_routes": summary.get("template_missing_routes", []),
    }
