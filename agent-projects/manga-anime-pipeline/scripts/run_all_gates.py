"""Run all stage gates in sequence and produce an aggregated report."""

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
from scripts.run_stage3a_gate import run_gate as run_stage3a_gate  # noqa: E402
from scripts.run_stage4a_gate import run_gate as run_stage4a_gate  # noqa: E402
from scripts.run_stage5_gate import run_gate as run_stage5_gate  # noqa: E402
from scripts.run_stage6_gate import run_gate as run_stage6_gate  # noqa: E402


def run_all(
    input_path: Path,
    ocr_config_path: Path,
    detect_config_path: Path,
    director_config_path: Path,
    comfy_config_path: Path,
    project_root: Path,
    runtime_root: Path,
    slice_config: SliceConfig,
    force: bool,
) -> tuple[dict[str, Any], Path, Path]:
    series_id, chapter_id = load_input_metadata(input_path)
    gates: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    warnings: list[str] = []
    required_user_actions: list[str] = []

    stage3a, stage3a_json, stage3a_md = run_stage3a_gate(
        input_path=input_path,
        config_path=ocr_config_path,
        project_root=project_root,
        runtime_root=runtime_root,
        slice_config=slice_config,
        force=force,
    )
    gates["stage3a"] = _gate_summary(stage3a, stage3a_json, project_root)
    if stage3a["gate_status"] != "pass":
        required_user_actions.append(
            f"Stage 3A {stage3a['gate_status']}: {stage3a['next_action']}"
        )

    if stage3a["next_stage_allowed"]:
        stage4a, stage4a_json, stage4a_md = run_stage4a_gate(
            input_path=input_path,
            pipeline_config_path=detect_config_path,
            upstream_config_path=ocr_config_path,
            project_root=project_root,
            runtime_root=runtime_root,
            slice_config=slice_config,
            force=force,
        )
        gates["stage4a"] = _gate_summary(stage4a, stage4a_json, project_root)
        if stage4a["gate_status"] != "pass":
            required_user_actions.append(
                f"Stage 4A {stage4a['gate_status']}: {stage4a['next_action']}"
            )
    else:
        gates["stage4a"] = _blocked_summary("stage4a_gate", "Stage 3A 未通过，已跳过 Stage 4A。")

    if gates["stage4a"]["next_stage_allowed"]:
        stage5, stage5_json, stage5_md = run_stage5_gate(
            input_path=input_path,
            pipeline_config_path=director_config_path,
            upstream_config_path=ocr_config_path,
            detection_config_path=detect_config_path,
            project_root=project_root,
            runtime_root=runtime_root,
            slice_config=slice_config,
            force=force,
        )
        gates["stage5"] = _gate_summary(stage5, stage5_json, project_root)
        if stage5["gate_status"] != "pass":
            required_user_actions.append(
                f"Stage 5 {stage5['gate_status']}: {stage5['next_action']}"
            )
    else:
        gates["stage5"] = _blocked_summary("stage5_gate", "Stage 4A 未通过，已跳过 Stage 5。")

    if gates["stage5"]["next_stage_allowed"]:
        stage6, stage6_json, stage6_md = run_stage6_gate(
            input_path=input_path,
            pipeline_config_path=director_config_path,
            detection_config_path=detect_config_path,
            upstream_config_path=ocr_config_path,
            comfy_config_path=comfy_config_path,
            project_root=project_root,
            runtime_root=runtime_root,
            slice_config=slice_config,
            force=force,
        )
        gates["stage6"] = _gate_summary(stage6, stage6_json, project_root)
        if stage6["gate_status"] != "pass":
            required_user_actions.append(
                f"Stage 6 {stage6['gate_status']}: {stage6['next_action']}"
            )
    else:
        gates["stage6"] = _blocked_summary("stage6_gate", "Stage 5 未通过，已跳过 Stage 6。")

    statuses = [gate["status"] for gate in gates.values()]
    if all(status == "pass" for status in statuses):
        overall = "pass"
        next_action = "全部门禁通过，可继续 Stage 7。"
    elif any(status == "fail" for status in statuses):
        overall = "fail"
        next_action = required_user_actions[0] if required_user_actions else "请查看各 stage 报告修复后重跑。"
    else:
        overall = "blocked"
        next_action = required_user_actions[0] if required_user_actions else "请按 errors / warnings 完成环境准备后重跑。"

    report = {
        "gate_name": "all_gates",
        "gate_status": overall,
        "next_stage_allowed": overall == "pass",
        "overall_status": overall,
        "series_id": series_id,
        "chapter_id": chapter_id,
        "input_path": project_ref(input_path, project_root),
        "ocr_config_path": project_ref(ocr_config_path, project_root),
        "detect_config_path": project_ref(detect_config_path, project_root),
        "director_config_path": project_ref(director_config_path, project_root),
        "comfy_config_path": project_ref(comfy_config_path, project_root),
        "gates": gates,
        "errors": errors,
        "warnings": warnings,
        "required_user_actions": required_user_actions,
        "next_action": next_action,
        "checks": {key: gate["status"] for key, gate in gates.items()},
        "commands": {
            "rerun_all": (
                f"python scripts/run_all_gates.py --input {input_path} "
                f"--ocr-config {ocr_config_path} --detect-config {detect_config_path} "
                f"--director-config {director_config_path} --comfy-config {comfy_config_path} --force"
            ),
        },
    }
    markdown = render_simple_markdown("All Stage Gates Report", report)
    json_path, md_path = write_gate_reports(project_root, runtime_root, "all_gates", report, markdown)
    return report, json_path, md_path


def _gate_summary(gate_report: dict[str, Any], json_path: Path, project_root: Path) -> dict[str, Any]:
    return {
        "name": gate_report["gate_name"],
        "status": gate_report["gate_status"],
        "next_stage_allowed": gate_report["next_stage_allowed"],
        "report_json": project_ref(json_path, project_root),
        "errors": gate_report.get("errors", []),
        "warnings": gate_report.get("warnings", []),
        "next_action": gate_report.get("next_action", ""),
    }


def _blocked_summary(name: str, message: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "blocked",
        "next_stage_allowed": False,
        "report_json": None,
        "errors": [message],
        "warnings": [],
        "next_action": message,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all stage gates")
    parser.add_argument("--input", required=True)
    parser.add_argument("--ocr-config", default="configs/stage1.ocr.dialogue.json")
    parser.add_argument("--detect-config", default="configs/stage1.ocr.dialogue.detect.json")
    parser.add_argument("--director-config", default="configs/stage1.full.director.json")
    parser.add_argument("--comfy-config", default="configs/comfy.default.json")
    parser.add_argument("--runtime-root", default="runtime")
    parser.add_argument("--window-height", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=160)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    report, json_path, md_path = run_all(
        input_path=_resolve(args.input),
        ocr_config_path=_resolve(args.ocr_config),
        detect_config_path=_resolve(args.detect_config),
        director_config_path=_resolve(args.director_config),
        comfy_config_path=_resolve(args.comfy_config),
        project_root=PROJECT_ROOT,
        runtime_root=_resolve_runtime(args.runtime_root),
        slice_config=SliceConfig(window_height=args.window_height, overlap=args.overlap),
        force=args.force,
    )
    print(
        json.dumps(
            {
                "overall_status": report["overall_status"],
                "next_action": report["next_action"],
                "report_json": project_ref(json_path, PROJECT_ROOT),
                "report_md": project_ref(md_path, PROJECT_ROOT),
                "gates": {key: {"status": item["status"], "next_stage_allowed": item["next_stage_allowed"]} for key, item in report["gates"].items()},
                "required_user_actions": report["required_user_actions"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["overall_status"] == "pass" else 1


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
