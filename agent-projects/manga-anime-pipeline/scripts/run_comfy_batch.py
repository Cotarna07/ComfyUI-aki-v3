"""Standalone ComfyUI batch submission (Stage 6 without acceptance/gate)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.comfy.client import ComfyClient, ComfyClientConfig, ServerUnreachable  # noqa: E402
from pipeline.comfy.submitter import SubmitterConfig, submit_batch  # noqa: E402
from pipeline.comfy.workflow_router import WorkflowRouter  # noqa: E402
from pipeline.common.io import read_json  # noqa: E402
from pipeline.qc.gate_common import safe_path_part  # noqa: E402
from pipeline.runtime_layout import prepare_runtime_for_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit shot_manifest shots to ComfyUI")
    parser.add_argument("--shot-manifest", required=True)
    parser.add_argument("--comfy-config", default="configs/comfy.default.json")
    parser.add_argument("--runtime-root", default="runtime")
    args = parser.parse_args()
    manifest_path = _resolve(args.shot_manifest)
    if not manifest_path.exists():
        print(json.dumps({"status": "fail", "error": f"shot_manifest not found: {manifest_path}"}, ensure_ascii=False, indent=2))
        return 2
    comfy_config_path = _resolve(args.comfy_config)
    runtime_context = prepare_runtime_for_manifest(PROJECT_ROOT, _resolve_runtime(args.runtime_root), manifest_path)
    manifest_path = runtime_context.manifest_path
    runtime_root = runtime_context.runtime_root
    manifest = read_json(manifest_path)
    series_id = runtime_context.series_id
    chapter_id = runtime_context.chapter_id
    comfy_config = read_json(comfy_config_path)
    server_url = (comfy_config.get("comfy") or {}).get("server", "http://127.0.0.1:8188")
    client = ComfyClient(ComfyClientConfig(server=server_url))
    try:
        client.check_server()
    except ServerUnreachable as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, ensure_ascii=False, indent=2))
        return 3
    router = WorkflowRouter(
        comfy_config.get("workflow_templates", {}) or {},
        PROJECT_ROOT,
        comfy_config.get("workflow_mappings", {}) or {},
    )
    output_dir = runtime_root / "comfy" / safe_path_part(series_id) / safe_path_part(chapter_id)
    settings = comfy_config.get("comfy", {}) or {}
    result = submit_batch(
        shot_manifest=manifest,
        output_dir=output_dir,
        client=client,
        router=router,
        submitter_config=SubmitterConfig(
            poll_interval_seconds=float(settings.get("poll_interval_seconds", 3.0)),
            history_poll_attempts=int(settings.get("history_poll_attempts", 1)),
            max_retries=int(settings.get("max_retries", 1)),
            dry_run=bool(settings.get("dry_run", False)),
            comfy_input_dir=_resolve_runtime(settings["input_dir"]) if settings.get("input_dir") else None,
            output_prefix_root=str(settings.get("output_prefix_root", "manga_anime_pipeline")),
        ),
        agent_id="manga-anime-pipeline",
    )
    print(
        json.dumps(
            {"status": "ok", "summary": result["summary"], "output_path": str(result["output_path"])},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not result["summary"].get("failed_count") and not result["summary"].get("template_missing_routes") else 1


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
