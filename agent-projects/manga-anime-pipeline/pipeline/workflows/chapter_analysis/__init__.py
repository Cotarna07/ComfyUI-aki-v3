"""Chapter analysis workflow.

This workflow turns a chapter manifest into windows, structured packets, and a
shot manifest. The legacy :mod:`pipeline.stage1` module re-exports this public
API for existing scripts and tests.
"""

from pipeline.workflows.chapter_analysis.models import OutputExistsError, StageResult
from pipeline.workflows.chapter_analysis.runner import run_stage1

__all__ = ["OutputExistsError", "StageResult", "run_stage1"]

