from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.common.io import as_project_path, read_json, resolve_project_path
from pipeline.common.schemas import SHOT_MANIFEST_SCHEMA, STAGE1_STATUS_SCHEMA, STRUCTURED_PACKET_SCHEMA, WINDOW_MANIFEST_SCHEMA
from pipeline.common.validation import SchemaValidationError, validate_json_schema
from pipeline.ingest.slicer import SliceConfig
from pipeline.manifest.integrity import validate_shot_manifest_links, validate_structured_packets, validate_window_manifest
from pipeline.stage1 import run_stage1


def run_acceptance(
    input_path: Path,
    config_path: Path,
    project_root: Path,
    runtime_root: Path | None = None,
    slice_config: SliceConfig | None = None,
    force: bool = False,
) -> tuple[dict[str, Any], Path, Path]:
    runtime_root = runtime_root or project_root / "runtime"
    slice_config = slice_config or SliceConfig()
    config = _safe_read_json(config_path)
    chapter = _safe_read_json(input_path)
    pipeline_error: str | None = None
    stage_report: dict[str, Any] | None = None
    try:
        stage_report = run_stage1(
            input_path=input_path,
            project_root=project_root,
            runtime_root=runtime_root,
            slice_config=slice_config,
            config=config,
            config_ref=as_project_path(project_root, config_path),
            force=force,
        )
    except Exception as error:
        pipeline_error = str(error)

    report = evaluate_acceptance(
        project_root=project_root,
        runtime_root=runtime_root,
        input_path=input_path,
        config_path=config_path,
        config=config,
        chapter=chapter,
        stage_report=stage_report,
        pipeline_error=pipeline_error,
    )
    from pipeline.qc.report import write_acceptance_reports

    json_path, md_path = write_acceptance_reports(project_root, runtime_root, report)
    return report, json_path, md_path


def evaluate_acceptance(
    project_root: Path,
    runtime_root: Path,
    input_path: Path,
    config_path: Path,
    config: dict[str, Any],
    chapter: dict[str, Any],
    stage_report: dict[str, Any] | None = None,
    pipeline_error: str | None = None,
) -> dict[str, Any]:
    series_id = str(chapter.get("series_id", "unknown_series"))
    chapter_id = str(chapter.get("chapter_id", "unknown_chapter"))
    provider_summary = _provider_summary(config, stage_report)
    paths = _artifact_paths(project_root, runtime_root, series_id, chapter_id, stage_report)
    warnings: list[str] = []
    errors: list[str] = []
    schema_errors: list[str] = []
    integrity_errors: list[str] = []
    status_errors: list[str] = []

    if pipeline_error:
        errors.append(f"pipeline execution failed: {pipeline_error}")

    artifacts = {name: path.exists() for name, path in paths.items() if name.endswith("path")}
    artifact_summary = {
        "window_manifest_exists": paths["window_manifest_path"].exists(),
        "structured_packets_exists": paths["structured_packet_index_path"].exists(),
        "shot_manifest_exists": paths["shot_manifest_path"].exists(),
        "status_report_exists": paths["status_report_path"].exists(),
    }
    for label, exists in artifact_summary.items():
        if not exists:
            errors.append(f"required artifact missing: {label}")

    window_manifest = _read_artifact(paths["window_manifest_path"], errors)
    packet_index = _read_artifact(paths["structured_packet_index_path"], errors)
    shot_manifest = _read_artifact(paths["shot_manifest_path"], errors)
    status_report = _read_artifact(paths["status_report_path"], errors)
    packets = _read_packets(project_root, packet_index, errors)

    if window_manifest is not None:
        _try_schema(lambda: validate_json_schema(window_manifest, WINDOW_MANIFEST_SCHEMA, "window_manifest"), schema_errors)
        _try_schema_or_integrity(lambda: validate_window_manifest(chapter, window_manifest, project_root), integrity_errors)
    if packets is not None:
        for packet in packets:
            _try_schema(lambda packet=packet: validate_json_schema(packet, STRUCTURED_PACKET_SCHEMA, "structured_packet"), schema_errors)
    if shot_manifest is not None:
        _try_schema(lambda: validate_json_schema(shot_manifest, SHOT_MANIFEST_SCHEMA, "shot_manifest"), schema_errors)
    if window_manifest is not None and packets is not None:
        _try_schema_or_integrity(lambda: validate_structured_packets(window_manifest, packets), integrity_errors)
    if packets is not None and shot_manifest is not None:
        _try_schema_or_integrity(lambda: validate_shot_manifest_links(packets, shot_manifest), integrity_errors)
    if status_report is not None:
        _try_schema(lambda: validate_json_schema(status_report, STAGE1_STATUS_SCHEMA, "stage1_status"), status_errors)
        for item in status_report.get("statuses", []):
            if item.get("status") == "failed":
                status_errors.append(f"stage failed: {item.get('stage')}: {item.get('error_message')}")
            if item.get("status") == "reused":
                warnings.append(f"stage output reused: {item.get('stage')}")

    if schema_errors:
        errors.extend(schema_errors)
    if integrity_errors:
        errors.extend(integrity_errors)
    if status_errors:
        errors.extend(status_errors)

    quality = _quality_summary(packets or [], provider_summary)
    count_summary = quality["count_summary"]
    if isinstance(shot_manifest, dict):
        count_summary["shot_count"] = len(shot_manifest.get("shots", []))
    ocr_quality = quality["ocr_quality"]
    dialogue_quality = quality["dialogue_quality"]

    expected_ocr = _normalize_provider_name(config.get("providers", {}).get("ocr", "mock"))
    expected_dialogue = _normalize_provider_name(config.get("providers", {}).get("dialogue", "mock"))
    if expected_ocr == "paddleocr" and ocr_quality["is_mock_ocr"]:
        errors.append("config requires ocr=paddleocr but structured packets still look like mock OCR")
    if expected_dialogue == "ocr_based" and dialogue_quality["is_mock_dialogue"]:
        errors.append("config requires dialogue=ocr_based but structured packets still look like mock dialogue")
    if count_summary["window_count"] > 0 and ocr_quality["windows_with_ocr"] == 0:
        errors.append("all windows have empty OCR results")
    if count_summary["ocr_block_count"] > 0 and count_summary["dialogue_block_count"] == 0 and count_summary["cleaned_text_candidate_count"] == 0:
        errors.append("OCR exists but dialogue provider produced no dialogue_blocks or cleaned_text_candidates")

    if 0 < ocr_quality["windows_with_ocr"] < count_summary["window_count"]:
        warnings.append("some windows have empty OCR results")
    if ocr_quality["average_confidence"] is not None and ocr_quality["average_confidence"] < 0.5:
        warnings.append("OCR average confidence is below 0.5")
    if not ocr_quality["sample_texts"]:
        warnings.append("OCR sample_texts is empty")
    if 0 < dialogue_quality["windows_with_dialogue"] < count_summary["window_count"]:
        warnings.append("some windows have empty dialogue results")
    if 0 < count_summary["dialogue_block_count"] < max(2, count_summary["window_count"]):
        warnings.append("dialogue block count is very low")
    if provider_summary.get("detection", "").startswith("mock"):
        warnings.append("detection provider is still mock")
    if provider_summary.get("director", "").startswith("mock"):
        warnings.append("director provider is still mock")

    next_stage_allowed = (
        not errors
        and expected_ocr == "paddleocr"
        and expected_dialogue == "ocr_based"
        and provider_summary.get("ocr") == "paddleocr"
        and provider_summary.get("dialogue") == "ocr_based"
        and not ocr_quality["is_mock_ocr"]
        and not dialogue_quality["is_mock_dialogue"]
        and ocr_quality["windows_with_ocr"] > 0
        and (count_summary["dialogue_block_count"] > 0 or count_summary["cleaned_text_candidate_count"] > 0)
    )
    pipeline_status = "fail" if errors else "warning" if warnings else "pass"
    return {
        "pipeline_status": pipeline_status,
        "next_stage_allowed": next_stage_allowed,
        "series_id": series_id,
        "chapter_id": chapter_id,
        "config_path": as_project_path(project_root, config_path),
        "provider_summary": provider_summary,
        "artifact_summary": artifact_summary,
        "count_summary": count_summary,
        "ocr_quality": ocr_quality,
        "dialogue_quality": dialogue_quality,
        "schema_check": {"valid": not schema_errors, "errors": schema_errors},
        "integrity_check": {"valid": not integrity_errors, "errors": integrity_errors},
        "status_check": {"valid": not status_errors, "errors": status_errors},
        "warnings": warnings,
        "errors": errors,
    }


def _artifact_paths(project_root: Path, runtime_root: Path, series_id: str, chapter_id: str, stage_report: dict[str, Any] | None) -> dict[str, Path]:
    base = runtime_root
    paths = {
        "window_manifest_path": base / "windows" / _safe_path_part(series_id) / _safe_path_part(chapter_id) / "window_manifest.json",
        "structured_packet_index_path": base / "structured" / _safe_path_part(series_id) / _safe_path_part(chapter_id) / "structured_packets.json",
        "shot_manifest_path": base / "manifests" / _safe_path_part(series_id) / _safe_path_part(chapter_id) / "shot_manifest.json",
        "status_report_path": _latest_status_report(base, series_id, chapter_id),
    }
    if stage_report:
        outputs = stage_report.get("outputs", {})
        for key, report_key in [
            ("window_manifest_path", "window_manifest"),
            ("structured_packet_index_path", "structured_packet_index"),
            ("shot_manifest_path", "shot_manifest"),
            ("status_report_path", "status_report"),
        ]:
            if report_key in outputs:
                paths[key] = resolve_project_path(project_root, outputs[report_key])
    return paths


def _latest_status_report(runtime_root: Path, series_id: str, chapter_id: str) -> Path:
    qc_dir = runtime_root / "qc" / _safe_path_part(series_id) / _safe_path_part(chapter_id)
    stable = qc_dir / "stage1_status.json"
    candidates = [path for path in qc_dir.glob("*status*.json") if path.name != "acceptance_report.json"] if qc_dir.exists() else []
    if candidates:
        return max(candidates, key=lambda path: path.stat().st_mtime)
    return stable


def _read_artifact(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return read_json(path)
    except Exception as error:
        errors.append(f"JSON parse failed for {path}: {error}")
        return None


def _read_packets(project_root: Path, packet_index: dict[str, Any] | None, errors: list[str]) -> list[dict[str, Any]] | None:
    if packet_index is None:
        return None
    packets: list[dict[str, Any]] = []
    for ref in packet_index.get("packet_refs", []):
        path = resolve_project_path(project_root, ref)
        packet = _read_artifact(path, errors)
        if packet is not None:
            packets.append(packet)
    return packets


def _quality_summary(packets: list[dict[str, Any]], provider_summary: dict[str, str]) -> dict[str, Any]:
    ocr_blocks = [block for packet in packets for block in packet.get("ocr_blocks", [])]
    dialogue_blocks = [block for packet in packets for block in packet.get("dialogue_blocks", [])]
    cleaned_candidates = [item for packet in packets for item in packet.get("cleaned_text_candidates", [])]
    confidences = [float(block.get("confidence", 0.0)) for block in ocr_blocks if isinstance(block.get("confidence", None), (int, float))]
    windows_with_ocr = [packet["window_id"] for packet in packets if packet.get("ocr_blocks")]
    windows_with_dialogue = [packet["window_id"] for packet in packets if packet.get("dialogue_blocks") or packet.get("cleaned_text_candidates")]
    ocr_providers = {str(block.get("provider", provider_summary.get("ocr", ""))) for block in ocr_blocks}
    dialogue_providers = {str(block.get("provider", provider_summary.get("dialogue", ""))) for block in dialogue_blocks}
    if not dialogue_providers:
        dialogue_providers = {str(item.get("provider", provider_summary.get("dialogue", ""))) for item in cleaned_candidates if isinstance(item, dict)}
    return {
        "count_summary": {
            "window_count": len(packets),
            "structured_packet_count": len(packets),
            "shot_count": 0,
            "ocr_block_count": len(ocr_blocks),
            "dialogue_block_count": len(dialogue_blocks),
            "bubble_box_count": sum(len(packet.get("bubble_boxes", [])) for packet in packets),
            "sfx_block_count": sum(len(packet.get("sfx_blocks", [])) for packet in packets),
            "cleaned_text_candidate_count": len(cleaned_candidates),
            "crop_candidate_count": sum(len(packet.get("crop_candidates", [])) for packet in packets),
        },
        "ocr_quality": {
            "provider": provider_summary.get("ocr", "unknown"),
            "is_mock_ocr": provider_summary.get("ocr", "").startswith("mock") or any(provider.startswith("mock") for provider in ocr_providers),
            "windows_with_ocr": len(windows_with_ocr),
            "empty_ocr_windows": [packet["window_id"] for packet in packets if not packet.get("ocr_blocks")],
            "average_confidence": sum(confidences) / len(confidences) if confidences else None,
            "min_confidence": min(confidences) if confidences else None,
            "max_confidence": max(confidences) if confidences else None,
            "sample_texts": [str(block.get("text", "")) for block in ocr_blocks[:5] if str(block.get("text", "")).strip()],
        },
        "dialogue_quality": {
            "provider": provider_summary.get("dialogue", "unknown"),
            "is_mock_dialogue": provider_summary.get("dialogue", "").startswith("mock") or any(provider.startswith("mock") for provider in dialogue_providers),
            "windows_with_dialogue": len(windows_with_dialogue),
            "empty_dialogue_windows": [packet["window_id"] for packet in packets if not packet.get("dialogue_blocks") and not packet.get("cleaned_text_candidates")],
            "dialogue_block_count": len(dialogue_blocks),
            "sample_dialogues": [str(block.get("text", "")) for block in dialogue_blocks[:5] if str(block.get("text", "")).strip()],
        },
    }


def _provider_summary(config: dict[str, Any], stage_report: dict[str, Any] | None) -> dict[str, str]:
    if stage_report and "providers" in stage_report:
        return dict(stage_report["providers"])
    providers = config.get("providers", {})
    return {
        "ocr": _normalize_provider_name(providers.get("ocr", "mock")),
        "dialogue": _normalize_provider_name(providers.get("dialogue", "mock")),
        "detection": _normalize_provider_name(providers.get("detection", "mock")),
        "director": _normalize_provider_name(providers.get("director", "mock")),
    }


def _normalize_provider_name(name: Any) -> str:
    value = str(name or "mock").strip().lower()
    aliases = {
        "mock_ocr": "mock",
        "mock_dialogue": "mock",
        "mock_detection": "mock",
        "mock_director": "mock",
        "paddle": "paddleocr",
        "ocr-based": "ocr_based",
        "ocrbased": "ocr_based",
    }
    normalized = aliases.get(value, value)
    if normalized == "mock":
        return "mock"
    return normalized


def _try_schema(func: Any, errors: list[str]) -> None:
    try:
        func()
    except SchemaValidationError as error:
        errors.extend(error.errors)
    except Exception as error:
        errors.append(str(error))


def _try_schema_or_integrity(func: Any, errors: list[str]) -> None:
    try:
        func()
    except SchemaValidationError as error:
        errors.extend(error.errors)
    except Exception as error:
        errors.append(str(error))


def _safe_read_json(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"
