"""Stage 6 gate: submit shots to ComfyUI in batch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.comfy.client import ComfyClient, ComfyClientConfig, ServerUnreachable  # noqa: E402
from pipeline.comfy.submitter import SubmitterConfig, submit_batch  # noqa: E402
from pipeline.comfy.workflow_router import WorkflowRouter  # noqa: E402
from pipeline.common.io import read_json  # noqa: E402
from pipeline.ingest.slicer import SliceConfig  # noqa: E402
from pipeline.qc.comfy_acceptance import evaluate_comfy_acceptance  # noqa: E402
from pipeline.qc.gate_common import (  # noqa: E402
    gate_output_dir,
    load_input_metadata,
    project_ref,
    render_simple_markdown,
    safe_path_part,
    write_gate_reports,
)
from scripts.run_stage5_gate import run_gate as run_stage5_gate  # noqa: E402

GATE_NAME = "stage6_gate"
GATE_TITLE = "Stage 6 Gate (ComfyUI Submission)"


def run_gate(
    input_path: Path,
    pipeline_config_path: Path,
    detection_config_path: Path,
    upstream_config_path: Path,
    comfy_config_path: Path,
    project_root: Path,
    runtime_root: Path,
    slice_config: SliceConfig,
    force: bool,
) -> tuple[dict[str, Any], Path, Path]:
    series_id, chapter_id = load_input_metadata(input_path)
    upstream_report, upstream_json, upstream_md = run_stage5_gate(
        input_path=input_path,
        pipeline_config_path=pipeline_config_path,
        upstream_config_path=upstream_config_path,
        detection_config_path=detection_config_path,
        project_root=project_root,
        runtime_root=runtime_root,
        slice_config=slice_config,
        force=force,
    )
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {
        "stage5_status": upstream_report["gate_status"],
        "stage5_next_stage_allowed": upstream_report["next_stage_allowed"],
        "comfy_server_reachable": False,
        "templates_ok": False,
        "submission_ran": False,
        "submission_status": None,
    }
    comfy_quality: dict[str, Any] | None = None
    output_path: Path | None = None
    comfy_config = read_json(comfy_config_path)
    server_url = (comfy_config.get("comfy") or {}).get("server", "http://127.0.0.1:8188")
    templates = comfy_config.get("workflow_templates", {}) or {}
    router = WorkflowRouter(templates, project_root)
    template_findings = router.validate_all()

    if not upstream_report["next_stage_allowed"]:
        gate_status = "blocked"
        next_stage_allowed = False
        next_action = "Stage 5 未通过，先修复 director 门禁后再重跑 Stage 6。"
        errors.append("upstream Stage 5 gate not passed; downstream blocked")
    else:
        client = ComfyClient(ComfyClientConfig(server=server_url))
        try:
            client.check_server()
            checks["comfy_server_reachable"] = True
        except ServerUnreachable as error:
            checks["comfy_server_reachable"] = False
            errors.append(str(error))
        if template_findings["missing"]:
            errors.extend([f"template missing: {item['route']} -> {item['path']}" for item in template_findings["missing"]])
        else:
            checks["templates_ok"] = True
        if not checks["comfy_server_reachable"]:
            gate_status = "blocked"
            next_stage_allowed = False
            next_action = (
                f"ComfyUI 服务未启动或不可达：{server_url}。请先启动 ComfyUI（默认 http://127.0.0.1:8188）。"
            )
        elif not checks["templates_ok"]:
            gate_status = "fail"
            next_stage_allowed = False
            next_action = "请先准备 configs/comfy_workflows/ 下的 workflow JSON，再重跑 Stage 6。"
        else:
            shot_manifest_path = (
                runtime_root
                / "manifests"
                / safe_path_part(series_id)
                / safe_path_part(chapter_id)
                / "shot_manifest.json"
            )
            if not shot_manifest_path.exists():
                gate_status = "fail"
                next_stage_allowed = False
                errors.append(f"shot_manifest missing: {shot_manifest_path}")
                next_action = "请确认 Stage 5 已生成 shot_manifest 后再重跑。"
            else:
                shot_manifest = read_json(shot_manifest_path)
                comfy_settings = comfy_config.get("comfy", {}) or {}
                submitter_config = SubmitterConfig(
                    poll_interval_seconds=float(comfy_settings.get("poll_interval_seconds", 3.0)),
                    max_retries=int(comfy_settings.get("max_retries", 1)),
                    dry_run=bool(comfy_settings.get("dry_run", False)),
                )
                output_dir = (
                    runtime_root
                    / "comfy"
                    / safe_path_part(series_id)
                    / safe_path_part(chapter_id)
                )
                submission_result = submit_batch(
                    shot_manifest=shot_manifest,
                    output_dir=output_dir,
                    client=client,
                    router=router,
                    submitter_config=submitter_config,
                    agent_id="manga-anime-pipeline",
                )
                output_path = submission_result["output_path"]
                checks["submission_ran"] = True
                acceptance = evaluate_comfy_acceptance(submission_result)
                checks["submission_status"] = acceptance["pipeline_status"]
                comfy_quality = acceptance["comfy_quality"]
                errors.extend(acceptance["errors"])
                warnings.extend(acceptance["warnings"])
                if acceptance["pipeline_status"] == "blocked":
                    gate_status = "blocked"
                    next_stage_allowed = False
                    next_action = "ComfyUI 服务在提交过程中不可达，请重新启动后重跑。"
                elif errors:
                    gate_status = "fail"
                    next_stage_allowed = False
                    next_action = "ComfyUI 提交失败，查看 comfy_tasks.json 调整 prompt / 模板后重跑。"
                else:
                    gate_status = "pass"
                    next_stage_allowed = True
                    next_action = "ComfyUI 已成功接收所有非 skip 镜头任务。"

    commands = {
        "install_comfy": "python -m pip install -r requirements-comfy.txt",
        "run_stage5_gate": f"python scripts/run_stage5_gate.py --input {input_path} --pipeline-config {pipeline_config_path} --force",
        "run_stage6_gate": (
            f"python scripts/run_stage6_gate.py --input {input_path} --pipeline-config {pipeline_config_path} "
            f"--comfy-config {comfy_config_path} --force"
        ),
    }
    report = {
        "gate_name": GATE_NAME,
        "gate_status": gate_status,
        "next_stage_allowed": next_stage_allowed,
        "required_stage": "Stage 2 + Stage 3A + Stage 4A + Stage 5 + Stage 6",
        "series_id": series_id,
        "chapter_id": chapter_id,
        "input_path": project_ref(input_path, project_root),
        "pipeline_config_path": project_ref(pipeline_config_path, project_root),
        "comfy_config_path": project_ref(comfy_config_path, project_root),
        "upstream_gate": {
            "name": upstream_report["gate_name"],
            "status": upstream_report["gate_status"],
            "next_stage_allowed": upstream_report["next_stage_allowed"],
            "report_json": project_ref(upstream_json, project_root),
            "report_md": project_ref(upstream_md, project_root),
        },
        "checks": checks,
        "comfy_config_summary": {
            "server": server_url,
            "templates_valid": template_findings["valid"],
            "templates_missing": template_findings["missing"],
            "templates_skipped": template_findings["skipped"],
        },
        "comfy_quality": comfy_quality,
        "comfy_tasks_path": project_ref(output_path, project_root) if output_path else None,
        "commands": commands,
        "errors": errors,
        "warnings": warnings,
        "next_action": next_action,
    }
    markdown = render_simple_markdown(GATE_TITLE, report)
    json_path, md_path = write_gate_reports(project_root, runtime_root, GATE_NAME, report, markdown)
    return report, json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 6 gate runner")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pipeline-config", required=True)
    parser.add_argument("--comfy-config", default="configs/comfy.default.json")
    parser.add_argument("--detection-config", default=None)
    parser.add_argument("--upstream-config", default=None)
    parser.add_argument("--runtime-root", default="runtime")
    parser.add_argument("--window-height", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=160)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = _resolve(args.input)
    pipeline_config_path = _resolve(args.pipeline_config)
    detection_config_path = _resolve(args.detection_config) if args.detection_config else pipeline_config_path
    upstream_config_path = _resolve(args.upstream_config) if args.upstream_config else detection_config_path
    comfy_config_path = _resolve(args.comfy_config)
    runtime_root = _resolve_runtime(args.runtime_root)
    report, json_path, md_path = run_gate(
        input_path=input_path,
        pipeline_config_path=pipeline_config_path,
        detection_config_path=detection_config_path,
        upstream_config_path=upstream_config_path,
        comfy_config_path=comfy_config_path,
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
