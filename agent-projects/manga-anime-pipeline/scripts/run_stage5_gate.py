"""Stage 5 gate: Qwen3-VL director."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.common.io import as_project_path, read_json  # noqa: E402
from pipeline.ingest.slicer import SliceConfig  # noqa: E402
from pipeline.qc.director_acceptance import evaluate_director_acceptance  # noqa: E402
from pipeline.qc.gate_common import load_input_metadata, project_ref, render_simple_markdown, write_gate_reports  # noqa: E402
from pipeline.stage1 import run_stage1  # noqa: E402
from scripts.run_stage4a_gate import run_gate as run_stage4a_gate  # noqa: E402

GATE_NAME = "stage5_gate"
GATE_TITLE = "Stage 5 Gate (Qwen3-VL Director)"


def check_qwen_env(model_path: str | None) -> dict[str, Any]:
    findings: dict[str, Any] = {
        "transformers_import_ok": False,
        "torch_import_ok": False,
        "model_path_configured": bool(model_path),
        "model_path_exists": False,
        "errors": [],
        "warnings": [],
    }
    try:
        importlib.import_module("torch")
        findings["torch_import_ok"] = True
    except Exception as error:
        findings["errors"].append(f"torch import failed: {error}")
    try:
        importlib.import_module("transformers")
        findings["transformers_import_ok"] = True
    except Exception as error:
        findings["errors"].append(f"transformers import failed: {error}")
    if model_path:
        findings["model_path_exists"] = Path(model_path).exists()
        if not findings["model_path_exists"]:
            findings["errors"].append(f"model_path does not exist: {model_path}")
    else:
        findings["errors"].append("director.qwen3vl.model_path not configured")
    findings["env_ready"] = (
        findings["transformers_import_ok"]
        and findings["torch_import_ok"]
        and findings["model_path_configured"]
        and findings["model_path_exists"]
    )
    return findings


def run_gate(
    input_path: Path,
    pipeline_config_path: Path,
    upstream_config_path: Path,
    detection_config_path: Path,
    project_root: Path,
    runtime_root: Path,
    slice_config: SliceConfig,
    force: bool,
) -> tuple[dict[str, Any], Path, Path]:
    series_id, chapter_id = load_input_metadata(input_path)
    upstream_report, upstream_json, upstream_md = run_stage4a_gate(
        input_path=input_path,
        pipeline_config_path=detection_config_path,
        upstream_config_path=upstream_config_path,
        project_root=project_root,
        runtime_root=runtime_root,
        slice_config=slice_config,
        force=force,
    )
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, Any] = {
        "stage4a_status": upstream_report["gate_status"],
        "stage4a_next_stage_allowed": upstream_report["next_stage_allowed"],
        "qwen_env_ready": False,
        "transformers_import_ok": False,
        "torch_import_ok": False,
        "model_path_configured": False,
        "model_path_exists": False,
        "pipeline_ran": False,
        "director_acceptance_ran": False,
        "director_acceptance_status": None,
        "director_acceptance_next_stage_allowed": False,
    }
    director_quality: dict[str, Any] | None = None
    pipeline_config = read_json(pipeline_config_path)
    model_path = (((pipeline_config.get("director") or {}).get("qwen3vl") or {}).get("model_path")) or None
    env = check_qwen_env(model_path)
    checks.update(
        {
            "qwen_env_ready": env["env_ready"],
            "transformers_import_ok": env["transformers_import_ok"],
            "torch_import_ok": env["torch_import_ok"],
            "model_path_configured": env["model_path_configured"],
            "model_path_exists": env["model_path_exists"],
        }
    )

    if not upstream_report["next_stage_allowed"]:
        gate_status = "blocked"
        next_stage_allowed = False
        next_action = "Stage 4A 未通过，先修复 detection 门禁后再重跑 Stage 5。"
        errors.append("upstream Stage 4A gate not passed; downstream blocked")
    elif not env["env_ready"]:
        gate_status = "blocked"
        next_stage_allowed = False
        next_action = "Qwen3-VL 环境未就绪，安装 requirements-director.txt 并配置 director.qwen3vl.model_path 后重跑。"
        errors.extend(env["errors"])
    else:
        chapter = read_json(input_path)
        pipeline_error: str | None = None
        stage_report = None
        try:
            stage_report = run_stage1(
                input_path=input_path,
                project_root=project_root,
                runtime_root=runtime_root,
                slice_config=slice_config,
                config=pipeline_config,
                config_ref=as_project_path(project_root, pipeline_config_path),
                force=force,
            )
            checks["pipeline_ran"] = True
        except Exception as error:
            pipeline_error = str(error)
            errors.append(f"pipeline execution failed: {pipeline_error}")
        acceptance_report = evaluate_director_acceptance(
            project_root=project_root,
            runtime_root=runtime_root,
            config=pipeline_config,
            chapter=chapter,
            stage_report=stage_report,
            pipeline_error=pipeline_error,
        )
        checks["director_acceptance_ran"] = True
        checks["director_acceptance_status"] = acceptance_report["pipeline_status"]
        checks["director_acceptance_next_stage_allowed"] = bool(acceptance_report["next_stage_allowed"])
        director_quality = acceptance_report["director_quality"]
        errors.extend(acceptance_report["errors"])
        warnings.extend(acceptance_report["warnings"])
        if errors:
            gate_status = "fail"
            next_stage_allowed = False
            next_action = "director 门禁失败，查看 director_quality 后调整 Qwen3-VL prompt / 配置后重跑。"
        else:
            gate_status = "pass"
            next_stage_allowed = True
            next_action = "可以继续 Stage 6 (ComfyUI 投递)。"

    commands = {
        "install_director": "python -m pip install -r requirements-director.txt",
        "run_stage4a_gate": f"python scripts/run_stage4a_gate.py --input {input_path} --pipeline-config {detection_config_path} --force",
        "run_stage5_gate": f"python scripts/run_stage5_gate.py --input {input_path} --pipeline-config {pipeline_config_path} --force",
    }
    report = {
        "gate_name": GATE_NAME,
        "gate_status": gate_status,
        "next_stage_allowed": next_stage_allowed,
        "required_stage": "Stage 2 + Stage 3A + Stage 4A + Stage 5",
        "series_id": series_id,
        "chapter_id": chapter_id,
        "input_path": project_ref(input_path, project_root),
        "pipeline_config_path": project_ref(pipeline_config_path, project_root),
        "upstream_gate": {
            "name": upstream_report["gate_name"],
            "status": upstream_report["gate_status"],
            "next_stage_allowed": upstream_report["next_stage_allowed"],
            "report_json": project_ref(upstream_json, project_root),
            "report_md": project_ref(upstream_md, project_root),
        },
        "checks": checks,
        "qwen_env": env,
        "director_quality": director_quality,
        "commands": commands,
        "errors": errors,
        "warnings": warnings,
        "next_action": next_action,
    }
    markdown = render_simple_markdown(GATE_TITLE, report)
    json_path, md_path = write_gate_reports(project_root, runtime_root, GATE_NAME, report, markdown)
    return report, json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 5 gate runner")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pipeline-config", required=True, help="config that enables director=qwen3vl")
    parser.add_argument("--detection-config", default=None, help="Stage 4A pipeline config; defaults to pipeline-config")
    parser.add_argument("--upstream-config", default=None, help="Stage 3A acceptance config; defaults to detection-config")
    parser.add_argument("--runtime-root", default="runtime")
    parser.add_argument("--window-height", type=int, default=1200)
    parser.add_argument("--overlap", type=int, default=160)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    input_path = _resolve(args.input)
    pipeline_config_path = _resolve(args.pipeline_config)
    detection_config_path = _resolve(args.detection_config) if args.detection_config else pipeline_config_path
    upstream_config_path = _resolve(args.upstream_config) if args.upstream_config else detection_config_path
    runtime_root = _resolve_runtime(args.runtime_root)
    report, json_path, md_path = run_gate(
        input_path=input_path,
        pipeline_config_path=pipeline_config_path,
        upstream_config_path=upstream_config_path,
        detection_config_path=detection_config_path,
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
