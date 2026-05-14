from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from pipeline.detection.grounded_sam2_provider import GroundedSAM2DetectionProvider
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
    def test_mock_provider_keeps_grounded_sam2_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "page.png"
            Image.new("RGB", (240, 320), "white").save(image_path)
            provider = GroundedSAM2DetectionProvider()
            result = provider.analyze(_make_packet(image_path, 240, 320))
        self.assertEqual(result["provider"], "grounded_sam2_mock")
        self.assertEqual(result["mock_replacement_for"], "Grounded-SAM-2")
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

    def test_real_mode_fails_with_replacement_point(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Grounded-SAM-2 real mode is not available yet"):
            GroundedSAM2DetectionProvider({"detection": {"grounded_sam2": {"mode": "real"}}})


if __name__ == "__main__":
    unittest.main()
