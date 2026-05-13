from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.common.io import write_json
from pipeline.ingest.slicer import SliceConfig
from pipeline.stage1 import run_stage1


class StatusFailureTests(unittest.TestCase):
    def test_failure_writes_status_report_with_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            chapter_path = _make_chapter(project_root)
            with self.assertRaisesRegex(ValueError, "Unknown OCR provider"):
                run_stage1(
                    chapter_path,
                    project_root,
                    project_root / "runtime",
                    SliceConfig(window_height=120, overlap=20),
                    config={"providers": {"ocr": "missing", "dialogue": "mock", "detection": "mock", "director": "mock"}},
                )

            status_path = project_root / "runtime" / "qc" / "series" / "chapter" / "stage1_status.json"
            self.assertTrue(status_path.exists())
            status_report = _read_json(status_path)
            self.assertEqual(status_report["overall_status"], "failed")
            self.assertIn("Unknown OCR provider", status_report["error_message"])
            provider_status = next(status for status in status_report["statuses"] if status["stage"] == "load_providers")
            self.assertEqual(provider_status["status"], "failed")
            self.assertIn("Unknown OCR provider", provider_status["error_message"])


def _make_chapter(project_root: Path) -> Path:
    image_path = project_root / "runtime" / "input" / "page.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (128, 260), "white").save(image_path)
    chapter_path = project_root / "runtime" / "input" / "chapter.json"
    write_json(
        chapter_path,
        {
            "series_id": "series",
            "chapter_id": "chapter",
            "input_type": "webtoon",
            "pages": [{"page_id": "p001", "image_path": "runtime/input/page.png", "width": 128, "height": 260}],
        },
    )
    return chapter_path


def _read_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


if __name__ == "__main__":
    unittest.main()
