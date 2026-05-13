from __future__ import annotations

import unittest

from pipeline.ocr.provider_factory import create_ocr_provider


class OCRProviderFactoryTests(unittest.TestCase):
    def test_mock_ocr_can_load(self) -> None:
        provider = create_ocr_provider("mock")
        self.assertEqual(provider.provider_name, "mock_ocr")

    def test_paddleocr_provider_name_is_recognized(self) -> None:
        provider = create_ocr_provider("paddleocr")
        self.assertEqual(provider.provider_name, "paddleocr")

    def test_paddle_alias_is_recognized(self) -> None:
        provider = create_ocr_provider("paddle")
        self.assertEqual(provider.provider_name, "paddleocr")

    def test_unknown_provider_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown OCR provider: .*Available providers: mock, paddleocr"):
            create_ocr_provider("unknown")


if __name__ == "__main__":
    unittest.main()
