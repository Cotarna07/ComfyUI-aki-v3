"""Compatibility entry point for the chapter analysis workflow."""

from __future__ import annotations

from pipeline.workflows.chapter_analysis import OutputExistsError, StageResult, run_stage1
from pipeline.workflows.chapter_analysis.artifacts import (
    load_or_build_shot_manifest as _load_or_build_shot_manifest,
    load_or_build_structured_packets as _load_or_build_structured_packets,
    load_or_slice_chapter as _load_or_slice_chapter,
)
from pipeline.workflows.chapter_analysis.executor import output_refs as _output_refs
from pipeline.workflows.chapter_analysis.executor import run_tracked_stage as _run_stage
from pipeline.workflows.chapter_analysis.paths import chapter_output_dir as _chapter_output_dir
from pipeline.workflows.chapter_analysis.paths import safe_path_part as _safe_path_part
from pipeline.workflows.chapter_analysis.paths import status_report_path as _status_report_path
from pipeline.workflows.chapter_analysis.providers import create_analysis_providers as _create_providers
from pipeline.workflows.chapter_analysis.providers import provider_report as _provider_report
from pipeline.workflows.chapter_analysis.reports import write_failure_report as _write_failure_report

__all__ = [
    "OutputExistsError",
    "StageResult",
    "run_stage1",
]

