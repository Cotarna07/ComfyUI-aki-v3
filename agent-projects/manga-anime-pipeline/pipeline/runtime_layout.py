from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.common.io import as_project_path, read_json, resolve_project_path, write_json


LEGACY_TOP_LEVEL_DIRS = {
    "comfy",
    "downloads",
    "generated",
    "grounded_sam2_retry",
    "grounded_sam2_test",
    "input",
    "manifests",
    "qc",
    "structured",
    "windows",
}
MIGRATABLE_STAGE_DIRS = ("windows", "structured", "manifests", "qc", "comfy")
SCOPE_METADATA_NAME = "_runtime_scope.json"


@dataclass(frozen=True)
class RuntimeInputContext:
    runtime_root: Path
    input_path: Path
    series_id: str
    chapter_id: str


@dataclass(frozen=True)
class RuntimeManifestContext:
    runtime_root: Path
    manifest_path: Path
    series_id: str
    chapter_id: str


def prepare_runtime_for_input(project_root: Path, base_runtime_root: Path, input_path: Path) -> RuntimeInputContext:
    chapter = read_json(input_path)
    series_id = _series_label(chapter)
    chapter_id = str(chapter.get("chapter_id", "unknown_chapter"))
    scoped_root = _resolve_scoped_runtime_root(base_runtime_root, input_path, series_id)
    _write_scope_metadata(scoped_root, series_id, chapter_id)
    _migrate_legacy_outputs(base_runtime_root, scoped_root, series_id)
    scoped_input_path = _snapshot_input_bundle(project_root, scoped_root, input_path, chapter)
    return RuntimeInputContext(
        runtime_root=scoped_root,
        input_path=scoped_input_path,
        series_id=series_id,
        chapter_id=chapter_id,
    )


def prepare_runtime_for_manifest(project_root: Path, base_runtime_root: Path, manifest_path: Path) -> RuntimeManifestContext:
    manifest = read_json(manifest_path)
    series_id = _series_label(manifest)
    chapter_id = str(manifest.get("chapter_id", "unknown_chapter"))
    scoped_root = _resolve_scoped_runtime_root(base_runtime_root, manifest_path, series_id)
    relocated_path = _relocated_legacy_path(base_runtime_root, scoped_root, manifest_path)
    _write_scope_metadata(scoped_root, series_id, chapter_id)
    _migrate_legacy_outputs(base_runtime_root, scoped_root, series_id)
    if relocated_path is not None and relocated_path.exists():
        manifest_path = relocated_path
    return RuntimeManifestContext(
        runtime_root=scoped_root,
        manifest_path=manifest_path,
        series_id=series_id,
        chapter_id=chapter_id,
    )


def _resolve_scoped_runtime_root(base_runtime_root: Path, path: Path, series_id: str) -> Path:
    detected_root = _detect_scoped_runtime_root(base_runtime_root, path)
    if detected_root is not None:
        return detected_root
    existing_root = _find_existing_scoped_root(base_runtime_root, series_id)
    if existing_root is not None:
        return existing_root
    return base_runtime_root / f"{date.today().isoformat()}_{_safe_path_part(series_id)}"


def _detect_scoped_runtime_root(base_runtime_root: Path, path: Path) -> Path | None:
    try:
        relative = path.resolve().relative_to(base_runtime_root.resolve())
    except ValueError:
        return None
    if not relative.parts:
        return None
    head = relative.parts[0]
    if head in LEGACY_TOP_LEVEL_DIRS:
        return None
    return base_runtime_root / head


def _find_existing_scoped_root(base_runtime_root: Path, series_id: str) -> Path | None:
    if not base_runtime_root.exists():
        return None
    exact_matches: list[Path] = []
    suffix_matches: list[Path] = []
    safe_series_id = _safe_path_part(series_id)
    for child in sorted(base_runtime_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or child.name in LEGACY_TOP_LEVEL_DIRS:
            continue
        metadata_path = child / SCOPE_METADATA_NAME
        if metadata_path.exists():
            metadata = read_json(metadata_path)
            if str(metadata.get("series_id", "")) == series_id:
                exact_matches.append(child)
                continue
        if child.name.endswith(f"_{safe_series_id}"):
            suffix_matches.append(child)
    if exact_matches:
        return exact_matches[0]
    if suffix_matches:
        return suffix_matches[0]
    return None


def _snapshot_input_bundle(project_root: Path, scoped_root: Path, input_path: Path, chapter: dict[str, Any]) -> Path:
    detected_root = _detect_scoped_runtime_root(scoped_root.parent, input_path) if scoped_root.parent.exists() else None
    if detected_root == scoped_root:
        return input_path

    input_dir = scoped_root / "input"
    pages_dir = input_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    scoped_chapter = dict(chapter)
    scoped_pages: list[dict[str, Any]] = []
    for page in chapter.get("pages", []):
        page_copy = dict(page)
        source_image = resolve_project_path(project_root, page["image_path"]).resolve()
        dest_name = _unique_page_name(page_copy, source_image.name)
        dest_path = pages_dir / dest_name
        if source_image != dest_path.resolve():
            shutil.copy2(source_image, dest_path)
        page_copy["image_path"] = as_project_path(project_root, dest_path)
        scoped_pages.append(page_copy)
    scoped_chapter["pages"] = scoped_pages

    scoped_input_path = input_dir / input_path.name
    write_json(scoped_input_path, scoped_chapter)
    return scoped_input_path


def _unique_page_name(page: dict[str, Any], original_name: str) -> str:
    page_id = _safe_path_part(str(page.get("page_id", "page")))
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix or ".png"
    safe_stem = _safe_path_part(stem)
    return f"{page_id}_{safe_stem}{suffix}"


def _migrate_legacy_outputs(base_runtime_root: Path, scoped_root: Path, series_id: str) -> None:
    safe_series_id = _safe_path_part(series_id)
    for stage_dir in MIGRATABLE_STAGE_DIRS:
        source = base_runtime_root / stage_dir / safe_series_id
        target = scoped_root / stage_dir / safe_series_id
        if not source.exists() or source.resolve() == target.resolve():
            continue
        _merge_move(source, target)


def _merge_move(source: Path, target: Path) -> None:
    if source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in list(source.iterdir()):
            _merge_move(child, target / child.name)
        if source.exists() and not any(source.iterdir()):
            source.rmdir()
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        source.unlink()
        return
    shutil.move(str(source), str(target))


def _relocated_legacy_path(base_runtime_root: Path, scoped_root: Path, path: Path) -> Path | None:
    try:
        relative = path.resolve().relative_to(base_runtime_root.resolve())
    except ValueError:
        return None
    if not relative.parts or relative.parts[0] not in MIGRATABLE_STAGE_DIRS:
        return None
    return scoped_root.joinpath(*relative.parts)


def _write_scope_metadata(scoped_root: Path, series_id: str, chapter_id: str) -> None:
    metadata_path = scoped_root / SCOPE_METADATA_NAME
    metadata = {
        "series_id": series_id,
        "safe_series_id": _safe_path_part(series_id),
        "latest_chapter_id": chapter_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if metadata_path.exists():
        existing = read_json(metadata_path)
        if isinstance(existing, dict):
            metadata = {**existing, **metadata}
    write_json(metadata_path, metadata)


def _series_label(payload: dict[str, Any]) -> str:
    for key in ("series_name", "series_title", "title", "name", "series_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "unknown_series"


def _safe_path_part(value: str) -> str:
    return "".join(char if char.isalnum() or char in "_-" else "_" for char in value).strip("_") or "item"