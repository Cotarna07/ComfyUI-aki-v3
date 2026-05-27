from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.comfy.provenance import write_output_provenance
from pipeline.common.io import read_json, write_json

from scripts.generated.test_projects_review import generate_comfy_character_design as design
from scripts.generated.test_projects_review import run_character_style_matrix as style
from scripts.generated.test_projects_review import run_character_video_model_matrix as video


RUNTIME_ROOT = PROJECT_ROOT / "runtime" / "2026-05-15_test_projects_short_manga"
REVIEW_DIR = RUNTIME_ROOT / "review"


def main() -> int:
    summary = {
        "character_design": backfill_character_design(REVIEW_DIR / "comfy_character_design" / "comfy_character_design_tasks.json"),
        "style_matrix": backfill_style_matrix(REVIEW_DIR / "style_matrix" / "20260515_style_matrix_v1" / "matrix_tasks.json"),
        "video_model_matrix": backfill_video_matrix(REVIEW_DIR / "video_model_matrix" / "20260515_video_models_v2" / "video_matrix_tasks.json"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def backfill_character_design(tasks_path: Path) -> dict[str, Any]:
    if not tasks_path.exists():
        return {"status": "missing", "tasks_path": str(tasks_path)}
    data = read_json(tasks_path)
    checkpoint = str(data.get("checkpoint") or "waiIllustriousSDXL_v170.safetensors")
    written = 0
    for task in data.get("tasks", []) or []:
        width, height = _pair(task.get("size"), [832, 1216])
        steps = int(task.get("steps") or 24)
        cfg = float(task.get("cfg") or 6.5)
        seed = int(task.get("seed") or 0)
        character_id = str(task.get("character_id") or "character")
        workflow = design.build_sdxl_workflow(
            checkpoint=str(task.get("checkpoint") or checkpoint),
            positive=str(task.get("positive_prompt") or ""),
            negative=str(task.get("negative_prompt") or ""),
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed,
            filename_prefix=f"manga_anime_pipeline/test_projects_short_manga/character_design/backfilled/{character_id}",
        )
        task["provenance_files"] = _write_for_outputs(
            task,
            workflow=workflow,
            workflow_name="character_design_sdxl",
            task_context={
                **task,
                "checkpoint": checkpoint,
                "size": [width, height],
                "steps": steps,
                "cfg": cfg,
                "backfill_note": "旧任务未记录原始 filename_prefix；其余核心参数按任务 JSON 和脚本默认值回填。",
            },
        )
        written += len(task["provenance_files"])
    write_json(tasks_path, data)
    return {"status": "ok", "tasks_path": str(tasks_path.relative_to(PROJECT_ROOT)), "sidecars_written": written}


def backfill_style_matrix(tasks_path: Path) -> dict[str, Any]:
    if not tasks_path.exists():
        return {"status": "missing", "tasks_path": str(tasks_path)}
    data = read_json(tasks_path)
    run_id = str(data.get("run_id") or tasks_path.parent.name)
    profiles = {profile.profile_id: profile for profile in style.STYLE_PROFILES}
    written = 0
    for task in data.get("tasks", []) or []:
        profile = profiles[str(task["profile_id"])]
        width, height = _pair(task.get("size"), [profile.width, profile.height])
        workflow = style.build_sdxl_workflow(
            checkpoint=str(task["checkpoint"]),
            positive=str(task.get("positive_prompt") or ""),
            negative=str(task.get("negative_prompt") or ""),
            width=width,
            height=height,
            steps=int(task.get("steps") or profile.steps),
            cfg=float(task.get("cfg") or profile.cfg),
            seed=int(task.get("seed") or 0),
            filename_prefix=(
                "manga_anime_pipeline/test_projects_short_manga/style_matrix/"
                f"{run_id}/{task['condition_id']}/{task['character_id']}"
            ),
        )
        task["provenance_files"] = _write_for_outputs(task, workflow=workflow, workflow_name="character_style_matrix_sdxl", task_context=task)
        written += len(task["provenance_files"])
    write_json(tasks_path, data)
    return {"status": "ok", "tasks_path": str(tasks_path.relative_to(PROJECT_ROOT)), "sidecars_written": written}


def backfill_video_matrix(tasks_path: Path) -> dict[str, Any]:
    if not tasks_path.exists():
        return {"status": "missing", "tasks_path": str(tasks_path)}
    data = read_json(tasks_path)
    run_id = str(data.get("run_id") or tasks_path.parent.name)
    model_cases = {case.model_id: case for case in video.VIDEO_MODELS}
    written = 0
    for task in data.get("tasks", []) or []:
        case = model_cases[str(task["model_id"])]
        filename_prefix = f"manga_anime_pipeline/test_projects_short_manga/video_model_matrix/{run_id}/{case.model_id}/{task['character_id']}"
        if case.builder == "wan22_dual":
            workflow = video.build_wan22_dual_workflow(
                case,
                str(task["input_image"]),
                str(task.get("positive_prompt") or ""),
                str(task.get("negative_prompt") or ""),
                int(task.get("seed") or 0),
                filename_prefix,
            )
        else:
            workflow = video.build_wan_single_workflow(
                case,
                str(task["input_image"]),
                str(task.get("positive_prompt") or ""),
                str(task.get("negative_prompt") or ""),
                int(task.get("seed") or 0),
                filename_prefix,
            )
        task["provenance_files"] = _write_for_outputs(task, workflow=workflow, workflow_name="character_video_model_matrix", task_context=task)
        written += len(task["provenance_files"])
    write_json(tasks_path, data)
    return {"status": "ok", "tasks_path": str(tasks_path.relative_to(PROJECT_ROOT)), "sidecars_written": written}


def _write_for_outputs(task: dict[str, Any], *, workflow: dict[str, Any], workflow_name: str, task_context: dict[str, Any]) -> list[str]:
    sidecars: list[str] = []
    for rel_path in task.get("output_files", []) or []:
        output_path = PROJECT_ROOT / rel_path
        if not output_path.exists():
            continue
        sidecar = write_output_provenance(
            output_path,
            project_root=PROJECT_ROOT,
            workflow=workflow,
            workflow_name=workflow_name,
            prompt_id=str(task.get("prompt_id") or ""),
            client_id=f"agent:codex|workflow:{workflow_name}|run:backfill",
            extra_data={
                "agent": "codex",
                "workflow_name": workflow_name,
                "source": "manga-anime-pipeline",
                "notes": "backfilled provenance for existing reviewed output",
            },
            task_context=task_context,
        )
        sidecars.append(str(sidecar.relative_to(PROJECT_ROOT)))
    return sidecars


def _pair(value: Any, fallback: list[int]) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return int(value[0]), int(value[1])
    return int(fallback[0]), int(fallback[1])


if __name__ == "__main__":
    raise SystemExit(main())
