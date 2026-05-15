from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.ingest.slicer import SliceConfig  # noqa: E402
from pipeline.qc.acceptance import run_acceptance  # noqa: E402
from pipeline.runtime_layout import prepare_runtime_for_input  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stage pipeline and write acceptance reports.")
    parser.add_argument("--input", required=True, help="Chapter manifest JSON path.")
    parser.add_argument("--config", required=True, help="Stage config JSON path.")
    parser.add_argument("--runtime-root", default="runtime", help="Runtime output root, relative to project root by default.")
    parser.add_argument("--window-height", type=int, default=1200, help="Window slice height.")
    parser.add_argument("--overlap", type=int, default=160, help="Overlap between adjacent windows.")
    parser.add_argument("--force", action="store_true", help="Rebuild existing stage outputs before acceptance.")
    args = parser.parse_args()

    input_path = _resolve_path(args.input, PROJECT_ROOT)
    config_path = _resolve_path(args.config, PROJECT_ROOT)
    runtime_context = prepare_runtime_for_input(PROJECT_ROOT, _resolve_runtime_path(args.runtime_root, PROJECT_ROOT), input_path)
    input_path = runtime_context.input_path
    runtime_root = runtime_context.runtime_root
    report, json_path, md_path = run_acceptance(
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
                "pipeline_status": report["pipeline_status"],
                "next_stage_allowed": report["next_stage_allowed"],
                "acceptance_report_json": _project_ref(json_path, PROJECT_ROOT),
                "acceptance_report_md": _project_ref(md_path, PROJECT_ROOT),
                "errors": report["errors"],
                "warnings": report["warnings"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if report["pipeline_status"] == "fail" else 0


def _resolve_path(value: str, project_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    cwd_path = (Path.cwd() / path).resolve()
    if cwd_path.exists():
        return cwd_path
    return (project_root / path).resolve()


def _resolve_runtime_path(value: str, project_root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def _project_ref(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
