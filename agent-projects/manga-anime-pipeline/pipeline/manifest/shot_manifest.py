from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.common.io import as_project_path, write_json
from pipeline.common.schemas import SHOT_MANIFEST_SCHEMA
from pipeline.common.status import utc_now_iso
from pipeline.common.validation import validate_json_schema
from pipeline.director.context import build_context_summary
from pipeline.manifest.integrity import validate_shot_manifest_links


def build_shot_manifest(
    packets: list[dict[str, Any]],
    packet_paths: list[Path],
    project_root: Path,
    runtime_root: Path,
    director: Any,
) -> tuple[dict[str, Any], Path]:
    if not packets:
        raise ValueError("Cannot build shot manifest from an empty structured packet list")
    series_id = packets[0]["series_id"]
    chapter_id = packets[0]["chapter_id"]
    shots: list[dict[str, Any]] = []
    for index, packet in enumerate(packets):
        shots.extend(director.create_shots(packet, build_context_summary(packets, index)))
    manifest = {
        "manifest_version": "stage1.mock.v1",
        "series_id": series_id,
        "chapter_id": chapter_id,
        "generated_at": utc_now_iso(),
        "director": {"provider": director.provider_name, "model": director.model_name},
        "source_packet_refs": [as_project_path(project_root, path) for path in packet_paths],
        "shots": shots,
    }
    validate_json_schema(manifest, SHOT_MANIFEST_SCHEMA, "shot_manifest")
    validate_shot_manifest_links(packets, manifest)
    output_path = runtime_root / "manifests" / _safe_path_part(series_id) / _safe_path_part(chapter_id) / "shot_manifest.json"
    write_json(output_path, manifest)
    return manifest, output_path


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"
