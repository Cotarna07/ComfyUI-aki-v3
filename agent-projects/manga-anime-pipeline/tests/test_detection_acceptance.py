from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.common.io import write_json
from pipeline.ingest.slicer import SliceConfig
from pipeline.qc.detection_acceptance import evaluate_detection_acceptance
from pipeline.stage1 import run_stage1


def _prepare_project(tmp: Path) -> tuple[Path, dict]:
    image_path = tmp / "runtime" / "input" / "page.png"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (160, 320), "white").save(image_path)
    chapter_path = tmp / "runtime" / "input" / "chapter.json"
    chapter = {
        "series_id": "series",
        "chapter_id": "chapter",
        "input_type": "webtoon",
        "pages": [
            {
                "page_id": "p001",
                "image_path": "runtime/input/page.png",
                "width": 160,
                "height": 320,
            }
        ],
    }
    write_json(chapter_path, chapter)
    return chapter_path, chapter


class DetectionAcceptanceTests(unittest.TestCase):
    def test_lightweight_pipeline_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            chapter_path, chapter = _prepare_project(project_root)
            config = {"providers": {"ocr": "mock", "dialogue": "mock", "detection": "lightweight", "director": "mock"}}
            stage_report = run_stage1(
                input_path=chapter_path,
                project_root=project_root,
                runtime_root=project_root / "runtime",
                slice_config=SliceConfig(window_height=160, overlap=20),
                config=config,
            )
            result = evaluate_detection_acceptance(
                project_root=project_root,
                runtime_root=project_root / "runtime",
                config=config,
                chapter=chapter,
                stage_report=stage_report,
            )
        self.assertEqual(result["pipeline_status"], "warning")
        self.assertTrue(result["next_stage_allowed"])
        self.assertFalse(result["detection_quality"]["is_mock_detection"])
        self.assertGreater(result["detection_quality"]["windows_with_crops"], 0)

    def test_mock_detection_fails_when_lightweight_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            chapter_path, chapter = _prepare_project(project_root)
            config_used = {"providers": {"ocr": "mock", "dialogue": "mock", "detection": "mock", "director": "mock"}}
            stage_report = run_stage1(
                input_path=chapter_path,
                project_root=project_root,
                runtime_root=project_root / "runtime",
                slice_config=SliceConfig(window_height=160, overlap=20),
                config=config_used,
            )
            expected_config = {"providers": {"ocr": "mock", "dialogue": "mock", "detection": "lightweight", "director": "mock"}}
            result = evaluate_detection_acceptance(
                project_root=project_root,
                runtime_root=project_root / "runtime",
                config=expected_config,
                chapter=chapter,
                stage_report=stage_report,
            )
        self.assertEqual(result["pipeline_status"], "fail")
        self.assertFalse(result["next_stage_allowed"])


if __name__ == "__main__":
    unittest.main()
