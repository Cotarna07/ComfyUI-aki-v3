from __future__ import annotations

import unittest

from pipeline.detection.provider_factory import create_detection_provider
from pipeline.dialogue.provider_factory import create_dialogue_provider
from pipeline.director.provider_factory import create_director_provider
from pipeline.ocr.provider_factory import create_ocr_provider


class ProviderFactoryTests(unittest.TestCase):
    def test_mock_providers_are_loaded(self) -> None:
        self.assertEqual(create_ocr_provider("mock").provider_name, "mock_ocr")
        self.assertEqual(create_dialogue_provider("mock").provider_name, "mock_dialogue")
        self.assertEqual(create_detection_provider("mock").provider_name, "mock_detection")
        self.assertEqual(create_director_provider("mock").provider_name, "mock_director")

    def test_legacy_mock_provider_aliases_are_loaded(self) -> None:
        self.assertEqual(create_ocr_provider("mock_ocr").provider_name, "mock_ocr")
        self.assertEqual(create_dialogue_provider("mock_dialogue").provider_name, "mock_dialogue")
        self.assertEqual(create_detection_provider("mock_detection").provider_name, "mock_detection")
        self.assertEqual(create_director_provider("mock_director").provider_name, "mock_director")

    def test_ocr_and_dialogue_real_provider_aliases_are_loaded(self) -> None:
        self.assertEqual(create_ocr_provider("paddleocr").provider_name, "paddleocr")
        self.assertEqual(create_ocr_provider("paddle").provider_name, "paddleocr")
        self.assertEqual(create_dialogue_provider("ocr_based").provider_name, "ocr_based")
        self.assertEqual(create_dialogue_provider("ocr-based").provider_name, "ocr_based")
        self.assertEqual(create_dialogue_provider("ocrbased").provider_name, "ocr_based")
        self.assertEqual(create_detection_provider("grounded_sam2").provider_name, "grounded_sam2")

    def test_unknown_provider_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown OCR provider"):
            create_ocr_provider("missing")
        with self.assertRaisesRegex(ValueError, "Unknown dialogue provider"):
            create_dialogue_provider("missing")
        with self.assertRaisesRegex(ValueError, "Unknown detection provider"):
            create_detection_provider("missing")
        with self.assertRaisesRegex(ValueError, "Unknown director provider"):
            create_director_provider("missing")


if __name__ == "__main__":
    unittest.main()
