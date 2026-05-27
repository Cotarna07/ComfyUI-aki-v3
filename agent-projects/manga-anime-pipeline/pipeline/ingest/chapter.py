from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from PIL import Image

from pipeline.common.io import read_json, resolve_project_path
from pipeline.common.schemas import CHAPTER_SCHEMA
from pipeline.common.validation import validate_json_schema


def load_chapter_manifest(input_path: Path, project_root: Path) -> dict[str, Any]:
    data = read_json(input_path)
    validate_json_schema(data, CHAPTER_SCHEMA, "chapter_manifest")
    chapter = deepcopy(data)
    for page in chapter["pages"]:
        image_path = resolve_project_path(project_root, page["image_path"])
        if not image_path.exists():
            raise FileNotFoundError(f"Input image not found for page {page['page_id']}: {image_path}")
        with Image.open(image_path) as image:
            actual_width, actual_height = image.size
        if actual_width != page["width"] or actual_height != page["height"]:
            raise ValueError(
                "Image dimensions do not match chapter manifest for "
                f"{page['page_id']}: manifest={page['width']}x{page['height']}, "
                f"actual={actual_width}x{actual_height}"
            )
        page["resolved_image_path"] = str(image_path)
    return chapter
