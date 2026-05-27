from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pipeline.common.io import as_project_path
from pipeline.common.status import TaskStatus
from pipeline.workflows.chapter_analysis.models import StageResult


def run_tracked_stage(
    statuses: list[TaskStatus],
    stage: str,
    input_refs: list[str],
    func: Callable[[], Any],
    project_root: Path,
) -> Any:
    status = TaskStatus.started(stage, input_refs)
    statuses.append(status)
    try:
        result = func()
        reused = isinstance(result, StageResult) and result.reused
        value = result.value if isinstance(result, StageResult) else result
        if reused:
            status.reuse(output_refs(value, project_root))
        else:
            status.complete(output_refs(value, project_root))
        return value
    except Exception as error:
        status.fail(error)
        raise


def output_refs(result: Any, project_root: Path) -> list[str]:
    if isinstance(result, tuple):
        refs: list[str] = []
        for item in result:
            refs.extend(output_refs(item, project_root))
        return refs
    if isinstance(result, Path):
        return [as_project_path(project_root, result)]
    if isinstance(result, list):
        refs = []
        for item in result:
            refs.extend(output_refs(item, project_root))
        return refs
    return []

