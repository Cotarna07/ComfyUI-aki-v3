from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from pipeline.detection.grounded_sam2_provider import GroundedSAM2DetectionProvider, GroundedSAM2RuntimeUnavailable
from pipeline.detection.lightweight_provider import LightweightDetectionProvider
from pipeline.detection.provider_factory import create_detection_provider


def _make_packet(image_path: Path, width: int, height: int, ocr_blocks=None, bubble_boxes=None) -> dict:
    ocr_blocks = ocr_blocks or []
    bubble_boxes = bubble_boxes or []
    return {
        "window_id": "w001",
        "page_id": "p001",
        "width": width,
        "height": height,
        "source_box": [0, 0, width, height],
        "resolved_image_path": str(image_path),
        "ocr_result": {"ocr_blocks": ocr_blocks},
        "dialogue_result": {"dialogue_blocks": [], "bubble_boxes": bubble_boxes},
    }


class LightweightDetectionShapeTests(unittest.TestCase):
    def test_output_has_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "page.png"
            Image.new("RGB", (256, 256), "white").save(image_path)
            provider = LightweightDetectionProvider()
            result = provider.analyze(_make_packet(image_path, 256, 256))
        for field in ("object_boxes", "object_masks", "crop_candidates", "focus_subjects", "scene_density", "provider"):
            self.assertIn(field, result)
        self.assertEqual(result["provider"], "lightweight")
        self.assertEqual(result["object_masks"], [])
        self.assertIsInstance(result["scene_density"], dict)
        self.assertIn(result["scene_density"]["level"], {"low", "medium", "high"})

    def test_crops_within_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "page.png"
            Image.new("RGB", (200, 300), "white").save(image_path)
            provider = LightweightDetectionProvider()
            result = provider.analyze(_make_packet(image_path, 200, 300))
        for crop in result["crop_candidates"]:
            x1, y1, x2, y2 = crop["box"]
            self.assertGreaterEqual(x1, 0)
            self.assertGreaterEqual(y1, 0)
            self.assertLessEqual(x2, 200)
            self.assertLessEqual(y2, 300)
            self.assertGreater(x2, x1)
            self.assertGreater(y2, y1)

    def test_missing_image_returns_empty_stable_result(self) -> None:
        provider = LightweightDetectionProvider()
        result = provider.analyze(_make_packet(Path("/nonexistent/page.png"), 100, 100))
        self.assertEqual(result["provider"], "lightweight")
        self.assertEqual(result["scene_density"]["value"], 0.0)
        self.assertEqual(result["scene_density"]["level"], "low")

    def test_factory_aliases(self) -> None:
        for alias in ("lightweight", "light", "rule_based", "rule-based"):
            provider = create_detection_provider(alias)
            self.assertIsInstance(provider, LightweightDetectionProvider)


class GroundedSAM2MockDetectionTests(unittest.TestCase):
    def test_ultralytics_backend_saves_masks_and_returns_grounded_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            image_path = project_root / "runtime" / "windows" / "series" / "chapter" / "p001" / "w001.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (240, 320), "white").save(image_path)
            packet = {
                **_make_packet(image_path, 240, 320),
                "window_image_path": str(image_path.relative_to(project_root)),
                "project_root": str(project_root),
            }
            provider = GroundedSAM2DetectionProvider(
                {"detection": {"grounded_sam2": {"mode": "ultralytics", "confidence_threshold": 0.2}}}
            )
            with patch.object(provider, "_load_ultralytics_models", return_value=(_FakeYolo(), _FakeSam())):
                result = provider.analyze(packet)
            self.assertEqual(result["provider"], "grounded_sam2")
            self.assertEqual(result["object_boxes"][0]["label"], "person")
            self.assertEqual(result["object_boxes"][0]["box"], [24, 32, 160, 260])
            self.assertEqual(len(result["object_masks"]), 1)
            mask_path = project_root / result["object_masks"][0]["mask_path"]
            self.assertTrue(mask_path.exists())
            with Image.open(mask_path) as mask_image:
                self.assertEqual(mask_image.mode, "L")
            self.assertTrue(result["crop_candidates"])
            self.assertEqual(result["focus_subjects"][0]["source_object_id"], result["object_boxes"][0]["object_id"])

    def test_auto_mode_falls_back_to_runnable_mock_when_runtime_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "page.png"
            Image.new("RGB", (240, 320), "white").save(image_path)
            provider = GroundedSAM2DetectionProvider({"detection": {"grounded_sam2": {"mode": "auto"}}})
            with patch.object(provider, "_run_ultralytics", side_effect=GroundedSAM2RuntimeUnavailable("ultralytics missing")):
                result = provider.analyze(_make_packet(image_path, 240, 320))
        self.assertEqual(result["provider"], "mock_grounded_sam2")
        self.assertEqual(result["mock_replacement_for"], "Grounded-SAM-2")
        self.assertIn("ultralytics missing", result["runtime_warning"])
        labels = {box["label"] for box in result["object_boxes"]}
        self.assertIn("main_character", labels)
        self.assertIn("face", labels)
        self.assertIn("hand", labels)
        self.assertTrue(result["crop_candidates"])
        self.assertIn(result["crop_candidates"][0]["framing"], {"close_up", "medium_shot", "wide_shot"})

    def test_grounded_sam2_factory_aliases(self) -> None:
        for alias in ("grounded_sam2", "grounded-sam-2", "grounded_sam_2", "groundedsam2"):
            provider = create_detection_provider(alias)
            self.assertIsInstance(provider, GroundedSAM2DetectionProvider)

    def test_real_mode_without_fallback_fails_with_replacement_point(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "page.png"
            Image.new("RGB", (240, 320), "white").save(image_path)
            provider = GroundedSAM2DetectionProvider(
                {"detection": {"grounded_sam2": {"mode": "real", "allow_fallback": False}}}
            )
            with patch.object(provider, "_run_ultralytics", side_effect=GroundedSAM2RuntimeUnavailable("ultralytics missing")):
                with self.assertRaisesRegex(GroundedSAM2RuntimeUnavailable, "pipeline/detection/grounded_sam2_provider.py"):
                    provider.analyze(_make_packet(image_path, 240, 320))


class _FakeYolo:
    names = {0: "person"}

    def predict(self, source, conf=0.25, verbose=False, **kwargs):
        return [_FakeYoloResult()]


class _FakeYoloResult:
    names = {0: "person"}
    boxes = [
        {
            "xyxy": [24, 32, 160, 260],
            "confidence": 0.93,
            "class_id": 0,
            "label": "person",
        }
    ]


class _FakeSam:
    def predict(self, source, bboxes=None, verbose=False, **kwargs):
        mask = np.zeros((320, 240), dtype=np.uint8)
        mask[40:250, 30:150] = 1
        return [{"masks": [mask]}]


if __name__ == "__main__":
    unittest.main()
