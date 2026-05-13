from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.common.io import write_json
from pipeline.common.schemas import WORKFLOW_ROUTES
from pipeline.ingest.slicer import SliceConfig
from pipeline.stage1 import run_stage1


class Stage1EndToEndTests(unittest.TestCase):
    def test_run_stage1_writes_manifest_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
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
                    "pages": [
                        {
                            "page_id": "p001",
                            "image_path": "runtime/input/page.png",
                            "width": 128,
                            "height": 260,
                        }
                    ],
                },
            )

            report = run_stage1(
                input_path=chapter_path,
                project_root=project_root,
                runtime_root=project_root / "runtime",
                slice_config=SliceConfig(window_height=120, overlap=20),
            )

            shot_manifest_path = project_root / report["outputs"]["shot_manifest"]
            status_path = project_root / report["outputs"]["status_report"]
            self.assertTrue(shot_manifest_path.exists())
            self.assertTrue(status_path.exists())
            with shot_manifest_path.open("r", encoding="utf-8") as file:
                manifest = json.load(file)
            self.assertGreaterEqual(len(manifest["shots"]), 1)
            self.assertIn(manifest["shots"][0]["workflow_route"], WORKFLOW_ROUTES)
            self.assertEqual(report["overall_status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
