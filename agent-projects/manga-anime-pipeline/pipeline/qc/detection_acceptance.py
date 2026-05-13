"""Detection acceptance evaluation.

Reads structured packets and shot manifest produced by the pipeline and
evaluates lightweight detection quality. Pure function: does not run the
pipeline itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.common.io import read_json
from pipeline.qc.acceptance import _artifact_paths, _normalize_provider_name, _read_artifact, _read_packets


def evaluate_detection_acceptance(
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
    artifacts = {
        "window_manifest_exists": paths["window_manifest_path"].exists(),
        "structured_packets_exists": paths["structured_packet_index_path"].exists(),
        "shot_manifest_exists": paths["shot_manifest_path"].exists(),
        "status_report_exists": paths["status_report_path"].exists(),
    }
    if pipeline_error:
        errors.append(f"pipeline execution failed: {pipeline_error}")
    for label, exists in artifacts.items():
        if not exists:
            errors.append(f"required artifact missing: {label}")

    packet_index = _read_artifact(paths["structured_packet_index_path"], errors)
    packets = _read_packets(project_root, packet_index, errors) if packet_index is not None else None

    expected_detection = _normalize_provider_name(config.get("providers", {}).get("detection", "mock"))
    expected_director = _normalize_provider_name(config.get("providers", {}).get("director", "mock"))
    provider_summary = (stage_report or {}).get("providers") or config.get("providers", {})

    quality = _detection_quality(packets or [])
    schema_errors = _detection_schema_errors(packets or [])
    if schema_errors:
        errors.extend(schema_errors)

    if expected_detection == "lightweight" and quality["is_mock_detection"]:
        errors.append("config requires detection=lightweight but structured packets still look like mock_detection")
    if expected_detection == "lightweight" and quality["windows_with_crops"] == 0 and quality["window_count"] > 0:
        errors.append("crop_candidates are empty across all windows")
    if quality["crop_out_of_bounds"]:
        errors.append("crop_candidates contain boxes outside window bounds: " + ", ".join(sorted(set(quality["crop_out_of_bounds"]))))

    if 0 < quality["windows_with_crops"] < quality["window_count"]:
        warnings.append("some windows have no crop_candidates")
    if quality["windows_missing_scene_density_level"]:
        warnings.append("some windows are missing scene_density.level")
    if quality["windows_with_no_object_boxes"] == quality["window_count"] and quality["windows_with_crops"] > 0:
        warnings.append("object_boxes empty but crop_candidates exist")
    if expected_director.startswith("mock"):
        warnings.append("director provider is still mock")
    if _has_reused_status(paths["status_report_path"]):
        warnings.append("stage output was reused")

    pipeline_status = "fail" if errors else "warning" if warnings else "pass"
    next_stage_allowed = (
        not errors
        and expected_detection == "lightweight"
        and not quality["is_mock_detection"]
        and quality["windows_with_crops"] > 0
    )
    return {
        "pipeline_status": pipeline_status,
        "next_stage_allowed": next_stage_allowed,
        "series_id": series_id,
        "chapter_id": chapter_id,
        "provider_summary": provider_summary,
        "artifact_summary": artifacts,
        "detection_quality": quality,
        "warnings": warnings,
        "errors": errors,
    }


def _detection_quality(packets: list[dict[str, Any]]) -> dict[str, Any]:
    out_of_bounds: list[str] = []
    windows_with_crops = 0
    object_box_total = 0
    crop_total = 0
    windows_missing_level: list[str] = []
    windows_with_no_object_boxes = 0
    is_mock = False
    crop_providers: set[str] = set()
    for packet in packets:
        crops = packet.get("crop_candidates", []) or []
        if crops:
            windows_with_crops += 1
        else:
            pass
        crop_total += len(crops)
        object_boxes = packet.get("object_boxes", []) or []
        object_box_total += len(object_boxes)
        if not object_boxes:
            windows_with_no_object_boxes += 1
        width = int(packet.get("width") or _box_width(packet.get("source_box")))
        height = int(packet.get("height") or _box_height(packet.get("source_box")))
        for crop in crops:
            box = crop.get("box") or []
            if not _box_within(box, width, height):
                out_of_bounds.append(str(crop.get("crop_id", "crop")))
            provider = str(crop.get("provider", ""))
            if provider:
                crop_providers.add(provider)
                if provider.startswith("mock"):
                    is_mock = True
        scene_density = packet.get("scene_density")
        if isinstance(scene_density, dict):
            if not scene_density.get("level"):
                windows_missing_level.append(str(packet.get("window_id", "")))
            provider = str(scene_density.get("provider", ""))
            if provider.startswith("mock"):
                is_mock = True
        elif scene_density is None:
            windows_missing_level.append(str(packet.get("window_id", "")))
        for object_box in object_boxes:
            provider = str(object_box.get("provider", ""))
            if provider.startswith("mock"):
                is_mock = True
    return {
        "window_count": len(packets),
        "windows_with_crops": windows_with_crops,
        "object_box_count": object_box_total,
        "crop_candidate_count": crop_total,
        "crop_out_of_bounds": out_of_bounds,
        "windows_missing_scene_density_level": windows_missing_level,
        "windows_with_no_object_boxes": windows_with_no_object_boxes,
        "is_mock_detection": is_mock,
        "crop_providers": sorted(crop_providers),
    }


def _detection_schema_errors(packets: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    required_fields = ("object_boxes", "object_masks", "crop_candidates", "focus_subjects", "scene_density")
    for packet in packets:
        for field in required_fields:
            if field not in packet:
                errors.append(f"structured packet {packet.get('window_id', '')} missing field {field}")
    return errors


def _box_within(box: Any, width: int, height: int) -> bool:
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return False
    try:
        x1, y1, x2, y2 = (int(item) for item in box)
    except (TypeError, ValueError):
        return False
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
        return False
    return x2 > x1 and y2 > y1


def _box_width(box: Any) -> int:
    if isinstance(box, (list, tuple)) and len(box) == 4:
        try:
            return int(box[2]) - int(box[0])
        except (TypeError, ValueError):
            return 0
    return 0


def _box_height(box: Any) -> int:
    if isinstance(box, (list, tuple)) and len(box) == 4:
        try:
            return int(box[3]) - int(box[1])
        except (TypeError, ValueError):
            return 0
    return 0


def _has_reused_status(status_report_path: Path) -> bool:
    if not status_report_path.exists():
        return False
    try:
        report = read_json(status_report_path)
    except Exception:
        return False
    return any(item.get("status") == "reused" for item in report.get("statuses", []))
