from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from pipeline.common.io import as_project_path, write_json
from pipeline.common.schemas import STAGE1_STATUS_SCHEMA
from pipeline.common.status import TaskStatus, utc_now_iso
from pipeline.common.validation import validate_json_schema
from pipeline.ingest.chapter import load_chapter_manifest
from pipeline.ingest.slicer import SliceConfig
from pipeline.workflows.chapter_analysis.artifacts import (
    load_or_build_shot_manifest,
    load_or_build_structured_packets,
    load_or_slice_chapter,
)
from pipeline.workflows.chapter_analysis.executor import run_tracked_stage
from pipeline.workflows.chapter_analysis.paths import status_report_path
from pipeline.workflows.chapter_analysis.providers import create_analysis_providers, provider_report
from pipeline.workflows.chapter_analysis.reports import write_failure_report


def run_stage1(
    input_path: Path,
    project_root: Path,
    runtime_root: Path | None = None,
    slice_config: SliceConfig | None = None,
    config: dict[str, Any] | None = None,
    config_ref: str = "inline_config",
    force: bool = False,
) -> dict[str, Any]:
    runtime_root = runtime_root or project_root / "runtime"
    slice_config = slice_config or SliceConfig()
    config = config or {}
    statuses: list[TaskStatus] = []
    run_id = f"stage1-{uuid4().hex[:10]}"
    started_at = utc_now_iso()
    chapter: dict[str, Any] | None = None

    try:
        chapter = run_tracked_stage(
            statuses,
            "load_chapter",
            [as_project_path(project_root, input_path)],
            lambda: load_chapter_manifest(input_path, project_root),
            project_root,
        )
        providers = run_tracked_stage(
            statuses,
            "load_providers",
            [config_ref],
            lambda: create_analysis_providers(config),
            project_root,
        )
        window_manifest, window_manifest_path = run_tracked_stage(
            statuses,
            "slice_windows",
            [page["image_path"] for page in chapter["pages"]],
            lambda: load_or_slice_chapter(chapter, project_root, runtime_root, slice_config, force),
            project_root,
        )
        packets, packet_paths, packet_index_path = run_tracked_stage(
            statuses,
            "build_structured_packets",
            [as_project_path(project_root, window_manifest_path)],
            lambda: load_or_build_structured_packets(window_manifest, project_root, runtime_root, providers, force),
            project_root,
        )
        shot_manifest, shot_manifest_path = run_tracked_stage(
            statuses,
            "draft_shot_manifest",
            [as_project_path(project_root, packet_index_path)],
            lambda: load_or_build_shot_manifest(packets, packet_paths, project_root, runtime_root, providers["director"], force),
            project_root,
        )
    except Exception as error:
        write_failure_report(run_id, started_at, statuses, error, chapter, project_root, runtime_root, force)
        raise

    report = {
        "run_id": run_id,
        "series_id": chapter["series_id"],
        "chapter_id": chapter["chapter_id"],
        "overall_status": "succeeded",
        "force": force,
        "rerun_policy": "reuse existing validated outputs unless --force is provided",
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "outputs": {
            "window_manifest": as_project_path(project_root, window_manifest_path),
            "structured_packet_index": as_project_path(project_root, packet_index_path),
            "shot_manifest": as_project_path(project_root, shot_manifest_path),
        },
        "counts": {
            "pages": len(chapter["pages"]),
            "windows": len(window_manifest["windows"]),
            "structured_packets": len(packets),
            "shots": len(shot_manifest["shots"]),
        },
        "statuses": [status.to_dict() for status in statuses],
        "providers": provider_report(providers),
        "mock_modules": [provider.provider_name for provider in providers.values() if provider.provider_name.startswith("mock")],
    }
    report_path = status_report_path(chapter["series_id"], chapter["chapter_id"], runtime_root, run_id, force)
    status = TaskStatus.started("write_status_report", [as_project_path(project_root, shot_manifest_path)])
    statuses.append(status)
    try:
        write_json(report_path, report)
        status.complete([as_project_path(project_root, report_path)])
        report["outputs"]["status_report"] = as_project_path(project_root, report_path)
        report["statuses"] = [item.to_dict() for item in statuses]
        validate_json_schema(report, STAGE1_STATUS_SCHEMA, "stage1_status")
        write_json(report_path, report)
    except Exception as error:
        status.fail(error)
        raise
    return report

