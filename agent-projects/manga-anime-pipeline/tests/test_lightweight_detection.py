from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

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


if __name__ == "__main__":
    unittest.main()
