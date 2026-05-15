from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.common.io import as_project_path, write_json
from pipeline.common.schemas import STAGE1_STATUS_SCHEMA
from pipeline.common.status import TaskStatus, utc_now_iso
from pipeline.common.validation import validate_json_schema
from pipeline.workflows.chapter_analysis.paths import status_report_path


def write_failure_report(
    run_id: str,
    started_at: str,
    statuses: list[TaskStatus],
    error: Exception,
    chapter: dict[str, Any] | None,
    project_root: Path,
    runtime_root: Path,
    force: bool,
) -> None:
    series_id = chapter.get("series_id", "unknown_series") if chapter else "unknown_series"
    chapter_id = chapter.get("chapter_id", "unknown_chapter") if chapter else "unknown_chapter"
    report_path = status_report_path(series_id, chapter_id, runtime_root, run_id, force, failed=True)
    report = {
        "run_id": run_id,
        "series_id": series_id,
        "chapter_id": chapter_id,
        "overall_status": "failed",
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "outputs": {"failure_status_report": as_project_path(project_root, report_path)},
        "error_message": str(error),
        "statuses": [status.to_dict() for status in statuses],
    }
    validate_json_schema(report, STAGE1_STATUS_SCHEMA, "stage1_status")
    write_json(report_path, report)

