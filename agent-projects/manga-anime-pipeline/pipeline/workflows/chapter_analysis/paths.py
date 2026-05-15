from __future__ import annotations

from pathlib import Path
from typing import Any


def safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"


def chapter_output_dir(runtime_root: Path, stage: str, chapter: dict[str, Any]) -> Path:
    return runtime_root / stage / safe_path_part(chapter["series_id"]) / safe_path_part(chapter["chapter_id"])


def status_report_path(
    series_id: str,
    chapter_id: str,
    runtime_root: Path,
    run_id: str,
    force: bool,
    failed: bool = False,
) -> Path:
    output_dir = runtime_root / "qc" / safe_path_part(series_id) / safe_path_part(chapter_id)
    stable_path = output_dir / "stage1_status.json"
    if force or not stable_path.exists():
        return stable_path
    suffix = "failed_status" if failed else "status"
    return output_dir / f"{run_id}_{suffix}.json"

