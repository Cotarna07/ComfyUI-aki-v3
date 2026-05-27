from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.common.io import as_project_path, write_json  # noqa: E402


def main() -> int:
    input_dir = PROJECT_ROOT / "runtime" / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    image_path = input_dir / "example_page.png"
    manifest_path = input_dir / "example_chapter.json"
    width, height = 720, 2200
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for index, top in enumerate([40, 540, 1060, 1580]):
        bottom = min(top + 430, height - 40)
        draw.rounded_rectangle([40, top, width - 40, bottom], radius=12, outline=(30, 30, 30), width=4)
        draw.ellipse([95, top + 45, 395, top + 150], outline=(40, 40, 40), width=3)
        draw.text((120, top + 82), f"Mock dialogue {index + 1}", fill=(20, 20, 20))
        draw.rectangle([430, top + 90, 590, bottom - 40], outline=(50, 80, 120), width=4)
        draw.text((455, top + 160), "CHAR", fill=(50, 80, 120))
    image.save(image_path)
    write_json(
        manifest_path,
        {
            "series_id": "example_series",
            "chapter_id": "ep001",
            "input_type": "webtoon",
            "pages": [
                {
                    "page_id": "p001",
                    "image_path": as_project_path(PROJECT_ROOT, image_path),
                    "width": width,
                    "height": height,
                }
            ],
        },
    )
    print(f"created {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
