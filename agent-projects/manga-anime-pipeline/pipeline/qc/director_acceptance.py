"""Director acceptance evaluation (shot manifest level)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.common.io import read_json
from pipeline.common.schemas import WORKFLOW_ROUTES
from pipeline.qc.acceptance import _artifact_paths, _normalize_provider_name


def evaluate_director_acceptance(
    project_root: Path,
    runtime_root: Path,
    config: dict[str, Any],
    chapter: dict[str, Any],
    stage_report: dict[str, Any] | None = None,
    pipeline_error: str | None = None,
) -> dict[str, Any]:
    series_id = str(chapter.get("series_id", "unknown_series"))
    chapter_id = str(chapter.get("chapter_id", "unknown_chapter"))
    paths = _artifact_paths(project_root, runtime_root, series_id, chapter_id, stage_report)
    errors: list[str] = []
    warnings: list[str] = []
    if pipeline_error:
        errors.append(f"pipeline execution failed: {pipeline_error}")
    shot_manifest_path = paths["shot_manifest_path"]
    if not shot_manifest_path.exists():
        errors.append("shot_manifest.json missing")
        return _build_report(series_id, chapter_id, errors, warnings, None, "fail", False, config)

    try:
        shot_manifest = read_json(shot_manifest_path)
    except Exception as error:
        errors.append(f"failed to read shot_manifest.json: {error}")
        return _build_report(series_id, chapter_id, errors, warnings, None, "fail", False, config)

    shots = shot_manifest.get("shots", []) or []
    expected_director = _normalize_provider_name(config.get("providers", {}).get("director", "mock"))
    quality = _director_quality(shots)
    if expected_director == "qwen3vl" and quality["is_mock_director"]:
        errors.append("config requires director=qwen3vl but shot manifest still looks like mock_director")
    if quality["shot_count"] == 0:
        errors.append("shot_manifest contains no shots")
    if quality["invalid_workflow_routes"]:
        errors.append("invalid workflow_route values: " + ", ".join(sorted(set(quality["invalid_workflow_routes"]))))
    if quality["empty_prompts"]:
        errors.append("shots with empty positive/negative prompt: " + ", ".join(sorted(set(quality["empty_prompts"]))))
    if quality["score_out_of_range"]:
        errors.append("anime_fit_score or confidence out of [0,1]: " + ", ".join(sorted(set(quality["score_out_of_range"]))))
    if expected_director == "qwen3vl" and quality["non_qwen_provider_shots"]:
        errors.append("shots not labeled provider=qwen3vl: " + ", ".join(sorted(set(quality["non_qwen_provider_shots"]))))

    if quality["all_same_route"]:
        warnings.append("all shots share the same workflow_route")
    if quality["skip_ratio"] >= 0.5:
        warnings.append("more than half of shots are workflow_route=skip")

    if errors:
        pipeline_status = "fail"
        next_stage_allowed = False
    elif warnings:
        pipeline_status = "warning"
        next_stage_allowed = expected_director == "qwen3vl" and not quality["is_mock_director"] and quality["shot_count"] > 0
    else:
        pipeline_status = "pass"
        next_stage_allowed = expected_director == "qwen3vl" and quality["shot_count"] > 0

    return _build_report(series_id, chapter_id, errors, warnings, quality, pipeline_status, next_stage_allowed, config)


def _director_quality(shots: list[dict[str, Any]]) -> dict[str, Any]:
    invalid_routes: list[str] = []
    empty_prompts: list[str] = []
    score_out_of_range: list[str] = []
    routes_seen: list[str] = []
    is_mock_director = False
    non_qwen_provider_shots: list[str] = []
    skip_count = 0
    for shot in shots:
        shot_id = str(shot.get("shot_id", ""))
        route = shot.get("workflow_route")
        if route not in WORKFLOW_ROUTES:
            invalid_routes.append(shot_id)
        else:
            routes_seen.append(str(route))
        if route == "skip":
            skip_count += 1
        positive = str(shot.get("positive_prompt", "") or "").strip()
        negative = str(shot.get("negative_prompt", "") or "").strip()
        if route != "skip" and (not positive or not negative):
            empty_prompts.append(shot_id)
        for field in ("anime_fit_score", "confidence"):
            value = shot.get(field)
            try:
                value = float(value)
            except (TypeError, ValueError):
                score_out_of_range.append(shot_id)
                continue
            if value < 0.0 or value > 1.0:
                score_out_of_range.append(shot_id)
        provider = str(shot.get("provider", ""))
        if provider.startswith("mock"):
            is_mock_director = True
        if provider and provider != "qwen3vl":
            non_qwen_provider_shots.append(shot_id)
        if not provider:
            is_mock_director = True
    unique_routes = sorted(set(routes_seen))
    total = max(1, len(shots))
    return {
        "shot_count": len(shots),
        "invalid_workflow_routes": invalid_routes,
        "empty_prompts": empty_prompts,
        "score_out_of_range": score_out_of_range,
        "routes_seen": unique_routes,
        "all_same_route": len(unique_routes) <= 1 and len(shots) > 1,
        "skip_ratio": skip_count / total,
        "is_mock_director": is_mock_director,
        "non_qwen_provider_shots": non_qwen_provider_shots,
    }


def _build_report(
    series_id: str,
    chapter_id: str,
    errors: list[str],
    warnings: list[str],
    quality: dict[str, Any] | None,
    pipeline_status: str,
    next_stage_allowed: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "pipeline_status": pipeline_status,
        "next_stage_allowed": next_stage_allowed,
        "series_id": series_id,
        "chapter_id": chapter_id,
        "provider_summary": config.get("providers", {}),
        "director_quality": quality,
        "errors": errors,
        "warnings": warnings,
    }
