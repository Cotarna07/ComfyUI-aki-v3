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

    def test_grounded_sam2_quality_allows_next_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            _, chapter = _prepare_project(project_root)
            packet_path = project_root / "runtime" / "structured" / "series" / "chapter" / "packets" / "w001.json"
            write_json(
                packet_path,
                {
                    "window_id": "w001",
                    "page_id": "p001",
                    "source_box": [0, 0, 160, 320],
                    "width": 160,
                    "height": 320,
                    "object_boxes": [
                        {
                            "object_id": "obj_0001",
                            "label": "person",
                            "box": [20, 40, 120, 260],
                            "confidence": 0.9,
                            "provider": "grounded_sam2",
                        }
                    ],
                    "object_masks": [
                        {
                            "mask_id": "mask_0001",
                            "source_object_id": "obj_0001",
                            "mask_path": "runtime/windows/series/chapter/p001/w001_masks/mask_0001.png",
                            "provider": "grounded_sam2",
                        }
                    ],
                    "crop_candidates": [
                        {
                            "crop_id": "crop_0001",
                            "box": [0, 0, 150, 300],
                            "reason": "main_subject",
                            "score": 0.88,
                            "provider": "grounded_sam2",
                        }
                    ],
                    "focus_subjects": [],
                    "scene_density": {"value": 0.4, "level": "medium", "provider": "grounded_sam2"},
                },
            )
            write_json(
                project_root / "runtime" / "structured" / "series" / "chapter" / "structured_packets.json",
                {
                    "series_id": "series",
                    "chapter_id": "chapter",
                    "packet_refs": [str(packet_path.relative_to(project_root))],
                },
            )
            write_json(
                project_root / "runtime" / "windows" / "series" / "chapter" / "window_manifest.json",
                {
                    "series_id": "series",
                    "chapter_id": "chapter",
                    "windows": [
                        {
                            "window_id": "w001",
                            "page_id": "p001",
                            "source_page": "runtime/input/page.png",
                            "image_path": "runtime/input/page.png",
                            "source_box": [0, 0, 160, 320],
                            "width": 160,
                            "height": 320,
                            "index": 0,
                        }
                    ],
                },
            )
            write_json(project_root / "runtime" / "manifests" / "series" / "chapter" / "shot_manifest.json", {"shots": []})
            write_json(project_root / "runtime" / "qc" / "series" / "chapter" / "stage1_status.json", {"statuses": []})
            result = evaluate_detection_acceptance(
                project_root=project_root,
                runtime_root=project_root / "runtime",
                config={"providers": {"detection": "grounded_sam2", "director": "mock"}},
                chapter=chapter,
                stage_report=None,
            )
        self.assertEqual(result["pipeline_status"], "warning")
        self.assertTrue(result["next_stage_allowed"])
        self.assertFalse(result["detection_quality"]["is_mock_detection"])


if __name__ == "__main__":
    unittest.main()
