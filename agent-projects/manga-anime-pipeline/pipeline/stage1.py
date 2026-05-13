from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from pipeline.common.io import as_project_path, read_json, resolve_project_path, write_json
from pipeline.common.schemas import STAGE1_STATUS_SCHEMA
from pipeline.common.status import TaskStatus, utc_now_iso
from pipeline.common.validation import validate_json_schema
from pipeline.detection.provider_factory import create_detection_provider
from pipeline.dialogue.provider_factory import create_dialogue_provider
from pipeline.director.provider_factory import create_director_provider
from pipeline.ingest.chapter import load_chapter_manifest
from pipeline.ingest.slicer import SliceConfig, slice_chapter
from pipeline.manifest.integrity import validate_shot_manifest_links, validate_structured_packets, validate_window_manifest
from pipeline.manifest.packets import build_structured_packets
from pipeline.manifest.shot_manifest import build_shot_manifest
from pipeline.ocr.provider_factory import create_ocr_provider


@dataclass(frozen=True)
class StageResult:
    value: Any
    reused: bool = False


class OutputExistsError(RuntimeError):
    pass


def run_stage1(
    input_path: Path,
    project_root: Path,
    runtime_root: Path | None = None,
    slice_config: SliceConfig | None = None,
    config: dict[str, Any] | None = None,
    config_ref: str = "inline_config",
    force: bool = False,
) -> dict[str, Any]:
    runtime_root = runtime_root or project_root / "runtime"
    slice_config = slice_config or SliceConfig()
    config = config or {}
    statuses: list[TaskStatus] = []
    run_id = f"stage1-{uuid4().hex[:10]}"
    started_at = utc_now_iso()
    chapter: dict[str, Any] | None = None

    try:
        chapter = _run_stage(
            statuses,
            "load_chapter",
            [as_project_path(project_root, input_path)],
            lambda: load_chapter_manifest(input_path, project_root),
            project_root,
        )
        providers = _run_stage(
            statuses,
            "load_providers",
            [config_ref],
            lambda: _create_providers(config),
            project_root,
        )
        window_manifest, window_manifest_path = _run_stage(
            statuses,
            "slice_windows",
            [page["image_path"] for page in chapter["pages"]],
            lambda: _load_or_slice_chapter(chapter, project_root, runtime_root, slice_config, force),
            project_root,
        )
        packets, packet_paths, packet_index_path = _run_stage(
            statuses,
            "build_structured_packets",
            [as_project_path(project_root, window_manifest_path)],
            lambda: _load_or_build_structured_packets(window_manifest, project_root, runtime_root, providers, force),
            project_root,
        )
        shot_manifest, shot_manifest_path = _run_stage(
            statuses,
            "draft_shot_manifest",
            [as_project_path(project_root, packet_index_path)],
            lambda: _load_or_build_shot_manifest(packets, packet_paths, project_root, runtime_root, providers["director"], force),
            project_root,
        )
    except Exception as error:
        _write_failure_report(run_id, started_at, statuses, error, chapter, project_root, runtime_root, force)
        raise

    report = {
        "run_id": run_id,
        "series_id": chapter["series_id"],
        "chapter_id": chapter["chapter_id"],
        "overall_status": "succeeded",
        "force": force,
        "rerun_policy": "reuse existing validated outputs unless --force is provided",
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "outputs": {
            "window_manifest": as_project_path(project_root, window_manifest_path),
            "structured_packet_index": as_project_path(project_root, packet_index_path),
            "shot_manifest": as_project_path(project_root, shot_manifest_path),
        },
        "counts": {
            "pages": len(chapter["pages"]),
            "windows": len(window_manifest["windows"]),
            "structured_packets": len(packets),
            "shots": len(shot_manifest["shots"]),
        },
        "statuses": [status.to_dict() for status in statuses],
        "providers": _provider_report(providers),
        "mock_modules": [provider.provider_name for provider in providers.values() if provider.provider_name.startswith("mock")],
    }
    report_path = _status_report_path(chapter["series_id"], chapter["chapter_id"], runtime_root, run_id, force)
    status = TaskStatus.started("write_status_report", [as_project_path(project_root, shot_manifest_path)])
    statuses.append(status)
    try:
        write_json(report_path, report)
        status.complete([as_project_path(project_root, report_path)])
        report["outputs"]["status_report"] = as_project_path(project_root, report_path)
        report["statuses"] = [item.to_dict() for item in statuses]
        validate_json_schema(report, STAGE1_STATUS_SCHEMA, "stage1_status")
        write_json(report_path, report)
    except Exception as error:
        status.fail(error)
        raise
    return report


def _create_providers(config: dict[str, Any]) -> dict[str, Any]:
    provider_config = config.get("providers", {})
    providers = {
        "ocr": create_ocr_provider(provider_config.get("ocr", "mock"), config),
        "dialogue": create_dialogue_provider(provider_config.get("dialogue", "mock"), config),
        "detection": create_detection_provider(provider_config.get("detection", "mock"), config),
        "director": create_director_provider(provider_config.get("director", "mock"), config),
    }
    for provider in providers.values():
        check_runtime = getattr(provider, "check_runtime", None)
        if callable(check_runtime):
            check_runtime()
    return providers


def _load_or_slice_chapter(
    chapter: dict[str, Any],
    project_root: Path,
    runtime_root: Path,
    slice_config: SliceConfig,
    force: bool,
) -> StageResult:
    output_dir = _chapter_output_dir(runtime_root, "windows", chapter)
    manifest_path = output_dir / "window_manifest.json"
    if manifest_path.exists() and not force:
        manifest = read_json(manifest_path)
        validate_window_manifest(chapter, manifest, project_root)
        return StageResult((manifest, manifest_path), reused=True)
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise OutputExistsError(f"Window output directory already exists without a valid manifest: {output_dir}. Use --force to rebuild.")
    if output_dir.exists() and force:
        shutil.rmtree(output_dir)
    return StageResult(slice_chapter(chapter, project_root, runtime_root, slice_config))


def _load_or_build_structured_packets(
    window_manifest: dict[str, Any],
    project_root: Path,
    runtime_root: Path,
    providers: dict[str, Any],
    force: bool,
) -> StageResult:
    chapter_stub = {"series_id": window_manifest["series_id"], "chapter_id": window_manifest["chapter_id"]}
    output_dir = _chapter_output_dir(runtime_root, "structured", chapter_stub)
    index_path = output_dir / "structured_packets.json"
    if index_path.exists() and not force:
        index = read_json(index_path)
        packet_paths = [resolve_project_path(project_root, item) for item in index.get("packet_refs", [])]
        packets = [read_json(path) for path in packet_paths]
        validate_structured_packets(window_manifest, packets)
        return StageResult((packets, packet_paths, index_path), reused=True)
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise OutputExistsError(f"Structured output directory already exists without a valid index: {output_dir}. Use --force to rebuild.")
    if output_dir.exists() and force:
        shutil.rmtree(output_dir)
    return StageResult(
        build_structured_packets(
            window_manifest,
            project_root,
            runtime_root,
            providers["ocr"],
            providers["dialogue"],
            providers["detection"],
        )
    )


def _load_or_build_shot_manifest(
    packets: list[dict[str, Any]],
    packet_paths: list[Path],
    project_root: Path,
    runtime_root: Path,
    director: Any,
    force: bool,
) -> StageResult:
    series_id = packets[0]["series_id"]
    chapter_id = packets[0]["chapter_id"]
    output_dir = runtime_root / "manifests" / _safe_path_part(series_id) / _safe_path_part(chapter_id)
    manifest_path = output_dir / "shot_manifest.json"
    if manifest_path.exists() and not force:
        manifest = read_json(manifest_path)
        validate_shot_manifest_links(packets, manifest)
        return StageResult((manifest, manifest_path), reused=True)
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise OutputExistsError(f"Manifest output directory already exists without a valid shot_manifest.json: {output_dir}. Use --force to rebuild.")
    if output_dir.exists() and force:
        shutil.rmtree(output_dir)
    return StageResult(build_shot_manifest(packets, packet_paths, project_root, runtime_root, director))


def _provider_report(providers: dict[str, Any]) -> dict[str, str]:
    return {name: provider.provider_name for name, provider in providers.items()}


def _write_failure_report(
    run_id: str,
    started_at: str,
    statuses: list[TaskStatus],
    error: Exception,
    chapter: dict[str, Any] | None,
    project_root: Path,
    runtime_root: Path,
    force: bool,
) -> None:
    series_id = chapter.get("series_id", "unknown_series") if chapter else "unknown_series"
    chapter_id = chapter.get("chapter_id", "unknown_chapter") if chapter else "unknown_chapter"
    report_path = _status_report_path(series_id, chapter_id, runtime_root, run_id, force, failed=True)
    report = {
        "run_id": run_id,
        "series_id": series_id,
        "chapter_id": chapter_id,
        "overall_status": "failed",
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "outputs": {"failure_status_report": as_project_path(project_root, report_path)},
        "error_message": str(error),
        "statuses": [status.to_dict() for status in statuses],
    }
    validate_json_schema(report, STAGE1_STATUS_SCHEMA, "stage1_status")
    write_json(report_path, report)


def _run_stage(statuses: list[TaskStatus], stage: str, input_refs: list[str], func: Callable[[], Any], project_root: Path) -> Any:
    status = TaskStatus.started(stage, input_refs)
    statuses.append(status)
    try:
        result = func()
        reused = isinstance(result, StageResult) and result.reused
        value = result.value if isinstance(result, StageResult) else result
        if reused:
            status.reuse(_output_refs(value, project_root))
        else:
            status.complete(_output_refs(value, project_root))
        return value
    except Exception as error:
        status.fail(error)
        raise


def _output_refs(result: Any, project_root: Path) -> list[str]:
    if isinstance(result, tuple):
        refs: list[str] = []
        for item in result:
            refs.extend(_output_refs(item, project_root))
        return refs
    if isinstance(result, Path):
        return [as_project_path(project_root, result)]
    if isinstance(result, list):
        refs = []
        for item in result:
            refs.extend(_output_refs(item, project_root))
        return refs
    return []


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"


def _chapter_output_dir(runtime_root: Path, stage: str, chapter: dict[str, Any]) -> Path:
    return runtime_root / stage / _safe_path_part(chapter["series_id"]) / _safe_path_part(chapter["chapter_id"])


def _status_report_path(series_id: str, chapter_id: str, runtime_root: Path, run_id: str, force: bool, failed: bool = False) -> Path:
    output_dir = runtime_root / "qc" / _safe_path_part(series_id) / _safe_path_part(chapter_id)
    stable_path = output_dir / "stage1_status.json"
    if force or not stable_path.exists():
        return stable_path
    suffix = "failed_status" if failed else "status"
    return output_dir / f"{run_id}_{suffix}.json"
