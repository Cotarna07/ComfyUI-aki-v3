"""Stage 3A gate: OCR + OCR-based Dialogue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.ingest.slicer import SliceConfig  # noqa: E402
from pipeline.qc.gate_common import (  # noqa: E402
    load_input_metadata,
    project_ref,
    render_simple_markdown,
    write_gate_reports,
)
from scripts.check_ocr_env import check_ocr_environment  # noqa: E402


GATE_NAME = "stage3a_gate"
GATE_TITLE = "Stage 3A Gate (OCR + OCR-based Dialogue)"


def run_gate(
    input_path: Path,
    config_path: Path,
    project_root: Path,
    runtime_root: Path,
    slice_config: SliceConfig,
    force: bool,
) -> tuple[dict[str, Any], Path, Path]:
    series_id, chapter_id = load_input_metadata(input_path)
    env = check_ocr_environment()
    checks = {
        "ocr_env_ready": env["ocr_env_ready"],
        "paddleocr_import_ok": env["paddleocr_import_ok"],
        "paddle_import_ok": env["paddle_import_ok"],
        "provider_ready": env["provider_ready"],
        "acceptance_ran": False,
        "acceptance_status": None,
        "acceptance_next_stage_allowed": False,
    }
    errors = list(env.get("errors", []))
    warnings = list(env.get("warnings", []))
    acceptance_summary: dict[str, Any] | None = None
    if env["ocr_env_ready"]:
        from pipeline.qc.acceptance import run_acceptance  # local import to keep startup fast

        report, json_path, md_path = run_acceptance(
            input_path=input_path,
            config_path=config_path,
            project_root=project_root,
            runtime_root=runtime_root,
            slice_config=slice_config,
            force=force,
        )
        checks["acceptance_ran"] = True
        checks["acceptance_status"] = report["pipeline_status"]
        checks["acceptance_next_stage_allowed"] = bool(report["next_stage_allowed"])
        acceptance_summary = {
            "pipeline_status": report["pipeline_status"],
            "next_stage_allowed": bool(report["next_stage_allowed"]),
            "report_json": project_ref(json_path, project_root),
            "report_md": project_ref(md_path, project_root),
            "errors": report.get("errors", []),
            "warnings": report.get("warnings", []),
        }
        if report["pipeline_status"] == "fail":
            errors.extend([f"acceptance error: {item}" for item in report.get("errors", [])])
        warnings.extend([f"acceptance warning: {item}" for item in report.get("warnings", [])])

    gate_status, next_stage_allowed, next_action = _decide(checks, errors)
    commands = {
        "install_ocr": "python -m pip install -r requirements-ocr.txt",
        "run_acceptance": f"python scripts/run_acceptance.py --input {input_path} --config {config_path} --force",
    }
    report: dict[str, Any] = {
        "gate_name": GATE_NAME,
        "gate_status": gate_status,
        "next_stage_allowed": next_stage_allowed,
        "required_stage": "Stage 2 + Stage 3A",
        "series_id": series_id,
        "chapter_id": chapter_id,
        "input_path": project_ref(input_path, project_root),
        "config_path": project_ref(config_path, project_root),
        "checks": checks,
        "environment": {
            "python_version": env.get("python_version"),
            "python_executable": env.get("python_executable"),
            "virtual_env": env.get("virtual_env"),
            "paddleocr_version": env.get("paddleocr_version"),
            "paddle_version": env.get("paddle_version"),
        },
        "acceptance_summary": acceptance_summary,
        "commands": commands,
        "errors": errors,
        "warnings": warnings,
        "next_action": next_action,
    }
    markdown = render_simple_markdown(GATE_TITLE, report)
    json_path, md_path = write_gate_reports(project_root, runtime_root, GATE_NAME, report, markdown)
    return report, json_path, md_path


def _decide(checks: dict[str, Any], errors: list[str]) -> tuple[str, bool, str]:
    if not checks["ocr_env_ready"]:
        return (
            "blocked",
            False,
            "请先执行：python -m pip install -r requirements-ocr.txt，然后重跑 stage3a gate。",
        )
    if not checks["acceptance_ran"]:
        return "fail", False, "OCR 环境就绪但 acceptance 未运行成功，请查看 errors。"
    if checks["acceptance_status"] == "fail":
        return "fail", False, "acceptance 报告状态为 fail，请修复对应错误后重跑。"
    if not checks["acceptance_next_stage_allowed"]:
        return "fail", False, "acceptance 未允许下一阶段，请查看 acceptance_report.md。"
    return "pass", True, "可以继续 Stage 4A。"


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3A gate runner")
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--runtime-root", default="runtime")
    parser.add_argument("--window-height", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=160)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = _resolve(args.input)
    config_path = _resolve(args.config)
    runtime_root = _resolve_runtime(args.runtime_root)
    report, json_path, md_path = run_gate(
        input_path=input_path,
        config_path=config_path,
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
