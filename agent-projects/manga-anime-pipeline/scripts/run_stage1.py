from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.common.io import read_json  # noqa: E402
from pipeline.ingest.slicer import SliceConfig  # noqa: E402
from pipeline.stage1 import run_stage1  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run stage1 manga analysis pipeline.")
    parser.add_argument("--input", required=True, help="Chapter manifest JSON path.")
    parser.add_argument("--config", default="configs/stage1.default.json", help="Stage1 config JSON path.")
    parser.add_argument("--runtime-root", default="runtime", help="Runtime output root, relative to project root by default.")
    parser.add_argument("--window-height", type=int, default=None, help="Override window slice height.")
    parser.add_argument("--overlap", type=int, default=None, help="Override overlap between adjacent windows.")
    parser.add_argument("--force", action="store_true", help="Rebuild existing stage outputs instead of reusing validated outputs.")
    args = parser.parse_args()

    try:
        config_path = _resolve_existing_path(args.config, PROJECT_ROOT)
        config = read_json(config_path) if config_path.exists() else {}
        input_path = _resolve_existing_path(args.input, PROJECT_ROOT)
        runtime_root = _resolve_runtime_path(args.runtime_root, PROJECT_ROOT)
        slice_config = SliceConfig(
            window_height=args.window_height if args.window_height is not None else int(config.get("window_height", 1200)),
            overlap=args.overlap if args.overlap is not None else int(config.get("overlap", 160)),
        )
        report = run_stage1(
            input_path=input_path,
            project_root=PROJECT_ROOT,
            runtime_root=runtime_root,
            slice_config=slice_config,
            config=config,
            config_ref=_project_ref(config_path, PROJECT_ROOT),
            force=args.force,
        )
    except Exception as error:
        print(f"stage1 failed: {error}", file=sys.stderr)
        return 1

    print(json.dumps(_summary(report), ensure_ascii=False, indent=2))
    return 0


def _resolve_existing_path(value: str, project_root: Path) -> Path:
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


def _summary(report: dict[str, object]) -> dict[str, object]:
    return {
        "run_id": report["run_id"],
        "overall_status": report["overall_status"],
        "series_id": report["series_id"],
        "chapter_id": report["chapter_id"],
        "counts": report["counts"],
        "outputs": report["outputs"],
        "providers": report["providers"],
        "mock_modules": report["mock_modules"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
