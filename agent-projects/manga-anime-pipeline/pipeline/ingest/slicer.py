from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from pipeline.common.io import as_project_path, write_json
from pipeline.common.schemas import WINDOW_MANIFEST_SCHEMA
from pipeline.common.status import utc_now_iso
from pipeline.common.validation import validate_json_schema
from pipeline.manifest.integrity import validate_window_manifest


@dataclass(frozen=True)
class SliceConfig:
    window_height: int = 1200
    overlap: int = 160
    image_format: str = "png"

    def validate(self) -> None:
        if self.window_height <= 0:
            raise ValueError("window_height must be greater than 0")
        if self.overlap < 0:
            raise ValueError("overlap must be greater than or equal to 0")
        if self.overlap >= self.window_height:
            raise ValueError("overlap must be smaller than window_height")


def slice_chapter(
    chapter: dict[str, Any],
    project_root: Path,
    runtime_root: Path,
    config: SliceConfig,
) -> tuple[dict[str, Any], Path]:
    config.validate()
    series_id = chapter["series_id"]
    chapter_id = chapter["chapter_id"]
    output_dir = runtime_root / "windows" / _safe_path_part(series_id) / _safe_path_part(chapter_id)
    windows: list[dict[str, Any]] = []

    for page in chapter["pages"]:
        page_id = page["page_id"]
        image_path = Path(page["resolved_image_path"])
        page_dir = output_dir / _safe_path_part(page_id)
        page_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as source_image:
            source_image.load()
            boxes = compute_window_boxes(source_image.width, source_image.height, config.window_height, config.overlap)
            for index, box in enumerate(boxes):
                left, top, right, bottom = box
                window_id = f"{_safe_id(chapter_id)}_{_safe_id(page_id)}_w{index:04d}"
                output_path = page_dir / f"w{index:04d}.{config.image_format}"
                source_image.crop(box).save(output_path)
                windows.append(
                    {
                        "window_id": window_id,
                        "page_id": page_id,
                        "source_page": page_id,
                        "image_path": as_project_path(project_root, output_path),
                        "source_box": [left, top, right, bottom],
                        "overlap_prev": config.overlap if index > 0 else 0,
                        "overlap_next": config.overlap if index < len(boxes) - 1 else 0,
                        "width": right - left,
                        "height": bottom - top,
                        "index": index,
                    }
                )

    manifest = {
        "series_id": series_id,
        "chapter_id": chapter_id,
        "generated_at": utc_now_iso(),
        "window_height": config.window_height,
        "overlap": config.overlap,
        "windows": windows,
    }
    validate_json_schema(manifest, WINDOW_MANIFEST_SCHEMA, "window_manifest")
    validate_window_manifest(chapter, manifest, project_root)
    manifest_path = output_dir / "window_manifest.json"
    write_json(manifest_path, manifest)
    return manifest, manifest_path


def compute_window_boxes(width: int, height: int, window_height: int, overlap: int) -> list[tuple[int, int, int, int]]:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than 0")
    if window_height <= 0:
        raise ValueError("window_height must be greater than 0")
    if overlap < 0 or overlap >= window_height:
        raise ValueError("overlap must be greater than or equal to 0 and smaller than window_height")

    boxes: list[tuple[int, int, int, int]] = []
    step = window_height - overlap
    top = 0
    while top < height:
        bottom = min(top + window_height, height)
        boxes.append((0, top, width, bottom))
        if bottom == height:
            break
        top += step
    return boxes


def _safe_id(value: str) -> str:
    return re.sub(r"[<>:\"/\\|?*\s]+", "_", value.strip()).strip("_") or "item"


def _safe_path_part(value: str) -> str:
    return _safe_id(value)
