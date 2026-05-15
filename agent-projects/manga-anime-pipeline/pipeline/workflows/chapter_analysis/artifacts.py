from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pipeline.common.io import read_json, resolve_project_path
from pipeline.ingest.slicer import SliceConfig, slice_chapter
from pipeline.manifest.integrity import validate_shot_manifest_links, validate_structured_packets, validate_window_manifest
from pipeline.manifest.packets import build_structured_packets
from pipeline.manifest.shot_manifest import build_shot_manifest
from pipeline.workflows.chapter_analysis.models import OutputExistsError, StageResult
from pipeline.workflows.chapter_analysis.paths import chapter_output_dir, safe_path_part


def load_or_slice_chapter(
    chapter: dict[str, Any],
    project_root: Path,
    runtime_root: Path,
    slice_config: SliceConfig,
    force: bool,
) -> StageResult:
    output_dir = chapter_output_dir(runtime_root, "windows", chapter)
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


def load_or_build_structured_packets(
    window_manifest: dict[str, Any],
    project_root: Path,
    runtime_root: Path,
    providers: dict[str, Any],
    force: bool,
) -> StageResult:
    chapter_stub = {"series_id": window_manifest["series_id"], "chapter_id": window_manifest["chapter_id"]}
    output_dir = chapter_output_dir(runtime_root, "structured", chapter_stub)
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


def load_or_build_shot_manifest(
    packets: list[dict[str, Any]],
    packet_paths: list[Path],
    project_root: Path,
    runtime_root: Path,
    director: Any,
    force: bool,
) -> StageResult:
    series_id = packets[0]["series_id"]
    chapter_id = packets[0]["chapter_id"]
    output_dir = runtime_root / "manifests" / safe_path_part(series_id) / safe_path_part(chapter_id)
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

