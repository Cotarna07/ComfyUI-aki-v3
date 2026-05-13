"""Stage 4A gate: lightweight detection after OCR + dialogue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.common.io import as_project_path, read_json  # noqa: E402
from pipeline.ingest.slicer import SliceConfig  # noqa: E402
from pipeline.qc.detection_acceptance import evaluate_detection_acceptance  # noqa: E402
from pipeline.qc.gate_common import load_input_metadata, project_ref, render_simple_markdown, write_gate_reports  # noqa: E402
from pipeline.stage1 import run_stage1  # noqa: E402
from scripts.run_stage3a_gate import run_gate as run_stage3a_gate  # noqa: E402

GATE_NAME = "stage4a_gate"
GATE_TITLE = "Stage 4A Gate (Lightweight Detection)"


def run_gate(
    input_path: Path,
    pipeline_config_path: Path,
    upstream_config_path: Path,
    project_root: Path,
    runtime_root: Path,
    slice_config: SliceConfig,
    force: bool,
) -> tuple[dict[str, Any], Path, Path]:
    series_id, chapter_id = load_input_metadata(input_path)
    upstream_report, upstream_json, upstream_md = run_stage3a_gate(
        input_path=input_path,
        config_path=upstream_config_path,
        project_root=project_root,
        runtime_root=runtime_root,
        slice_config=slice_config,
        force=force,
    )
    checks: dict[str, Any] = {
        "stage3a_status": upstream_report["gate_status"],
        "stage3a_next_stage_allowed": upstream_report["next_stage_allowed"],
        "pipeline_ran": False,
        "pipeline_status": None,
        "detection_acceptance_ran": False,
        "detection_acceptance_status": None,
        "detection_acceptance_next_stage_allowed": False,
    }
    errors: list[str] = []
    warnings: list[str] = []
    acceptance_summary: dict[str, Any] | None = None
    detection_quality: dict[str, Any] | None = None
    if not upstream_report["next_stage_allowed"]:
        gate_status = "blocked"
        next_stage_allowed = False
        next_action = "Stage 3A 未通过，先修复 OCR/dialogue 门禁后再重跑 Stage 4A。"
        errors.append("upstream Stage 3A gate not passed; downstream blocked")
    else:
        config = read_json(pipeline_config_path)
        chapter = read_json(input_path)
        pipeline_error: str | None = None
        try:
            stage_report = run_stage1(
                input_path=input_path,
                project_root=project_root,
                runtime_root=runtime_root,
                slice_config=slice_config,
                config=config,
                config_ref=as_project_path(project_root, pipeline_config_path),
                force=force,
            )
            checks["pipeline_ran"] = True
            checks["pipeline_status"] = stage_report.get("status", "completed")
        except Exception as error:
            stage_report = None
            pipeline_error = str(error)
            errors.append(f"pipeline execution failed: {pipeline_error}")
        acceptance_report = evaluate_detection_acceptance(
            project_root=project_root,
            runtime_root=runtime_root,
            config=config,
            chapter=chapter,
            stage_report=stage_report,
            pipeline_error=pipeline_error,
        )
        checks["detection_acceptance_ran"] = True
        checks["detection_acceptance_status"] = acceptance_report["pipeline_status"]
        checks["detection_acceptance_next_stage_allowed"] = bool(acceptance_report["next_stage_allowed"])
        detection_quality = acceptance_report["detection_quality"]
        errors.extend(acceptance_report["errors"])
        warnings.extend(acceptance_report["warnings"])
        acceptance_summary = {
            "pipeline_status": acceptance_report["pipeline_status"],
            "next_stage_allowed": acceptance_report["next_stage_allowed"],
        }
        if errors:
            gate_status = "fail"
            next_stage_allowed = False
            next_action = "detection 门禁失败，请查看 errors / detection_quality 后调整 lightweight 参数或源图后再跑。"
        else:
            gate_status = "pass"
            next_stage_allowed = True
            next_action = "可以继续 Stage 5 (Director)。"

    commands = {
        "install_pillow": "python -m pip install -r requirements-detection.txt",
        "run_stage3a_gate": f"python scripts/run_stage3a_gate.py --input {input_path} --config {upstream_config_path} --force",
        "run_stage4a_gate": f"python scripts/run_stage4a_gate.py --input {input_path} --pipeline-config {pipeline_config_path} --force",
    }
    report = {
        "gate_name": GATE_NAME,
        "gate_status": gate_status,
        "next_stage_allowed": next_stage_allowed,
        "required_stage": "Stage 2 + Stage 3A + Stage 4A",
        "series_id": series_id,
        "chapter_id": chapter_id,
        "input_path": project_ref(input_path, project_root),
        "pipeline_config_path": project_ref(pipeline_config_path, project_root),
        "upstream_config_path": project_ref(upstream_config_path, project_root),
        "upstream_gate": {
            "name": upstream_report["gate_name"],
            "status": upstream_report["gate_status"],
            "next_stage_allowed": upstream_report["next_stage_allowed"],
            "report_json": project_ref(upstream_json, project_root),
            "report_md": project_ref(upstream_md, project_root),
        },
        "checks": checks,
        "detection_quality": detection_quality,
        "acceptance_summary": acceptance_summary,
        "commands": commands,
        "errors": errors,
        "warnings": warnings,
        "next_action": next_action,
    }
    markdown = render_simple_markdown(GATE_TITLE, report)
    json_path, md_path = write_gate_reports(project_root, runtime_root, GATE_NAME, report, markdown)
    return report, json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 4A gate runner")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pipeline-config", required=True, help="config that enables detection=lightweight")
    parser.add_argument("--upstream-config", default=None, help="Stage 3A acceptance config; defaults to pipeline-config")
    parser.add_argument("--runtime-root", default="runtime")
    parser.add_argument("--window-height", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=160)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = _resolve(args.input)
    pipeline_config_path = _resolve(args.pipeline_config)
    upstream_config_path = _resolve(args.upstream_config) if args.upstream_config else pipeline_config_path
    runtime_root = _resolve_runtime(args.runtime_root)
    report, json_path, md_path = run_gate(
        input_path=input_path,
        pipeline_config_path=pipeline_config_path,
        upstream_config_path=upstream_config_path,
        project_root=PROJECT_ROOT,
        runtime_root=runtime_root,
        slice_config=SliceConfig(window_height=args.window_height, overlap=args.overlap),
        force=args.force,
    )
    print(
        json.dumps(
            {
                "gate_name": report["gate_name"],
                "gate_status": report["gate_status"],
                "next_stage_allowed": report["next_stage_allowed"],
                "report_json": project_ref(json_path, PROJECT_ROOT),
                "report_md": project_ref(md_path, PROJECT_ROOT),
                "errors": report["errors"],
                "warnings": report["warnings"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["gate_status"] == "pass" else 1


def _resolve(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (PROJECT_ROOT / path).resolve()


def _resolve_runtime(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


if __name__ == "__main__":
    raise SystemExit(main())
